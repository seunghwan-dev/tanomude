import datetime as dt
import json
from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from backend import ollama_client
from backend.retrieval import hybrid_search

PURPOSE_MAX = 20
DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d")
MAX_PARSE_RETRY = 2
RETRY_TEMP_STEP = 0.3
DOMESTIC_CUE = "国内"
OVERSEAS_CUE = "海外"
DOMAIN_CUES = ("出張",)
OUT_OF_DOMAIN_REASON = "すみません、このご依頼はまだ分かりません。今は出張申請の操作のみお手伝いできます。"
REQUIRED_FIELDS_REASON = "必須項目が入力されていません。不足している項目をご入力のうえ、再度お試しください。"
MALFORMED_DATE_REASON = "日付の形式が正しくありません。出発日・帰着日をご確認のうえ、修正して再入力してください。"
EXTRACTION_MISSING_REASON = "必須項目の値を取得できませんでした。入力内容をご確認のうえ、修正して再度お試しください。"


class SlotParseError(Exception):
    def __init__(self, retry_count: int, errors: list[str]):
        self.retry_count = retry_count
        self.errors = errors
        super().__init__(f"slot extraction failed after {retry_count} retries")


class RequestInput(BaseModel):
    workflow: str
    instruction: str
    fields: dict[str, str | bool]
    task_id: str | None = None


class Slots(BaseModel):
    dest_code: str
    purpose: str
    overseas: bool = False
    reuse_prev_proj: bool = False


class Step(BaseModel):
    seq: int
    type: Literal["field", "fkey", "nav"]
    target: str | None = None
    value: str | None = None
    key: str | None = None


class FilledKeysequence(BaseModel):
    kind: Literal["filled"] = "filled"
    workflow: str
    steps: list[Step]
    slots: Slots


class Refusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: str
    missing_fields: list[str]


SlotFillResult = Annotated[FilledKeysequence | Refusal, Field(discriminator="kind")]
RESULT_ADAPTER: TypeAdapter = TypeAdapter(SlotFillResult)

SlotExtractor = Callable[["RequestInput", str], Slots]

SLOT_SYSTEM = (
    "あなたは自社AS-400出張申請の入力支援エージェントである。"
    "キーシーケンスの骨格・日付・日数・案件コード・文字数規則・必須項目の検証はシステムが行う。"
    "あなたは present なフィールドの値の正規化と分岐判断のみをJSONで返す。"
    "出力は厳格なJSONのみ。"
    '返すJSON: {"dest_code":str, "purpose":str, "overseas":bool, "reuse_prev_proj":bool}。'
    "dest_codeは半角英大文字の都市romaji。海外出張ならoverseas=true。"
    "前回案件コードを再利用するならreuse_prev_proj=true。purposeは元の文言のまま。値の捏造はしない。"
)


def _present(value) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def parse_date(value) -> str | None:
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return None


def resolve_proj(fields: dict) -> str | None:
    for key in ("proj_resolved", "proj_hint"):
        if _present(fields.get(key)):
            return str(fields[key])
    return None


def required_missing(fields: dict) -> list[str]:
    missing = []
    if not _present(fields.get("dest")):
        missing.append("DEST")
    if not _present(fields.get("dept_date")):
        missing.append("DEPTDATE")
    if not _present(fields.get("ret_date")):
        missing.append("RETDATE")
    proj = _present(fields.get("proj_hint")) or _present(fields.get("proj_resolved")) or bool(fields.get("proj_reuse"))
    if not proj:
        missing.append("PROJ")
    return missing


def recalc_days(dept: str, ret: str) -> str:
    start = dt.datetime.strptime(dept, "%Y%m%d").date()
    end = dt.datetime.strptime(ret, "%Y%m%d").date()
    return str((end - start).days + 1)


def assemble(slots: Slots, dept: str, ret: str, proj: str | None) -> list[Step]:
    steps: list[Step] = []

    def add(type_: str, target=None, value=None, key=None) -> None:
        steps.append(Step(seq=len(steps) + 1, type=type_, target=target, value=value, key=key))

    add("nav", key="Enter")
    add("field", target="DEST", value=slots.dest_code)
    add("field", target="DEPTDATE", value=dept)
    add("field", target="RETDATE", value=ret)
    add("field", target="DAYS", value=recalc_days(dept, ret))
    if slots.reuse_prev_proj:
        add("fkey", key="FieldExit")
    add("field", target="PURPOSE", value=slots.purpose)
    if slots.overseas:
        add("fkey", key="Tab")
        add("field", target="OVRSEA", value="Y")
    add("fkey", key="F9" if slots.reuse_prev_proj else "F4")
    add("field", target="PROJ", value=proj)
    add("fkey", key="Enter")
    add("fkey", key="Enter")
    return steps


def instruction_out_of_domain(instruction: str) -> bool:
    return not any(cue in instruction for cue in DOMAIN_CUES)


def fill(request: RequestInput, slot_fn: SlotExtractor, context: str = "") -> FilledKeysequence | Refusal:
    if instruction_out_of_domain(request.instruction):
        return Refusal(reason=OUT_OF_DOMAIN_REASON, missing_fields=[])

    missing = required_missing(request.fields)
    if missing:
        return Refusal(reason=REQUIRED_FIELDS_REASON, missing_fields=missing)

    dept = parse_date(request.fields["dept_date"])
    ret = parse_date(request.fields["ret_date"])
    if dept is None or ret is None:
        bad = [name for name, value in (("DEPTDATE", dept), ("RETDATE", ret)) if value is None]
        return Refusal(reason=MALFORMED_DATE_REASON, missing_fields=bad)

    proj = resolve_proj(request.fields)
    slots = slot_fn(request, context)
    slots.dest_code = slots.dest_code.upper()
    slots.purpose = slots.purpose[:PURPOSE_MAX]
    if not _present(slots.dest_code):
        return Refusal(reason=EXTRACTION_MISSING_REASON, missing_fields=["DEST"])
    if not _present(slots.purpose):
        return Refusal(reason=EXTRACTION_MISSING_REASON, missing_fields=["PURPOSE"])
    return FilledKeysequence(workflow=request.workflow, steps=assemble(slots, dept, ret, proj), slots=slots)


def ground(db: Session, query: str, top_k: int = 6) -> str:
    chunks = hybrid_search(db, query, top_k=top_k)
    return "\n\n".join(chunk.text for chunk in chunks)


def extract_slots(request: RequestInput, context: str = "") -> Slots:
    prompt = (
        "# 手順書・指針 (RAG)\n" + context + "\n\n"
        "# 指示\n" + request.instruction + "\n\n"
        "# フィールド値\n" + json.dumps(request.fields, ensure_ascii=False)
    )
    errors: list[str] = []
    for attempt in range(MAX_PARSE_RETRY + 1):
        try:
            data = ollama_client.generate_json(
                SLOT_SYSTEM,
                prompt,
                seed=ollama_client.DEFAULT_SEED + attempt,
                temperature=RETRY_TEMP_STEP * attempt,
            )
            return Slots(**data)
        except (ValueError, ValidationError) as exc:
            errors.append(str(exc))
    raise SlotParseError(retry_count=MAX_PARSE_RETRY, errors=errors)


def instruction_grounds_overseas(instruction: str) -> bool:
    return DOMESTIC_CUE in instruction or OVERSEAS_CUE in instruction


def enforce_immunity(grounded: Slots, corrected: Slots, instruction: str) -> Slots:
    overseas = grounded.overseas if instruction_grounds_overseas(instruction) else corrected.overseas
    return Slots(
        dest_code=grounded.dest_code,
        purpose=grounded.purpose,
        overseas=overseas,
        reuse_prev_proj=corrected.reuse_prev_proj,
    )


def immune_extractor(rag_context: str, extractor: SlotExtractor = extract_slots) -> SlotExtractor:
    def slot_fn(request: RequestInput, corrected_context: str) -> Slots:
        grounded = extractor(request, rag_context)
        if corrected_context == rag_context:
            return grounded
        corrected = extractor(request, corrected_context)
        return enforce_immunity(grounded, corrected, request.instruction)

    return slot_fn
