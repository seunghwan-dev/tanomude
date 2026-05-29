import datetime as dt
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import ollama_client
from backend.retrieval import hybrid_search

PURPOSE_MAX = 20


class RequestInput(BaseModel):
    workflow: str
    instruction: str
    fields: dict[str, str | bool]


class Slots(BaseModel):
    dest_code: str
    dept_date: str
    ret_date: str
    purpose: str
    proj_code: str | None = None
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


SlotExtractor = Callable[[RequestInput, str], Slots]

SLOT_SYSTEM = (
    "あなたは自社AS-400出張申請の入力支援エージェントである。"
    "キーシーケンスの骨格・文字数規則・日数計算・必須項目の検証はシステムが行う。"
    "あなたは present なフィールドの値の正規化と分岐判断のみをJSONで返す。"
    "出力は厳格なJSONのみ。"
    '返すJSON: {"dest_code":str, "dept_date":"YYYYMMDD", "ret_date":"YYYYMMDD", '
    '"purpose":str, "proj_code":str_or_null, "overseas":bool, "reuse_prev_proj":bool}。'
    "dest_codeは半角英大文字の都市romaji。日付はYYYYMMDD8桁。"
    "海外出張ならoverseas=true。前回案件コードを再利用するならreuse_prev_proj=true。"
    "purposeは元の文言のまま、文字数調整はしない。値の捏造はしない。"
)


def _present(value) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def required_missing(fields: dict) -> list[str]:
    missing = []
    if not _present(fields.get("dest")):
        missing.append("DEST")
    if not _present(fields.get("dept_date")):
        missing.append("DEPTDATE")
    if not _present(fields.get("ret_date")):
        missing.append("RETDATE")
    proj = (
        _present(fields.get("proj_hint"))
        or _present(fields.get("proj_resolved"))
        or bool(fields.get("proj_reuse"))
    )
    if not proj:
        missing.append("PROJ")
    return missing


def recalc_days(dept: str, ret: str) -> str:
    start = dt.date(int(dept[0:4]), int(dept[4:6]), int(dept[6:8]))
    end = dt.date(int(ret[0:4]), int(ret[4:6]), int(ret[6:8]))
    return str((end - start).days + 1)


def assemble(slots: Slots) -> list[Step]:
    steps: list[Step] = []

    def add(type_: str, target=None, value=None, key=None) -> None:
        steps.append(Step(seq=len(steps) + 1, type=type_, target=target, value=value, key=key))

    add("nav", key="Enter")
    add("field", target="DEST", value=slots.dest_code)
    add("field", target="DEPTDATE", value=slots.dept_date)
    add("field", target="RETDATE", value=slots.ret_date)
    add("field", target="DAYS", value=recalc_days(slots.dept_date, slots.ret_date))
    if slots.reuse_prev_proj:
        add("fkey", key="FieldExit")
    add("field", target="PURPOSE", value=slots.purpose[:PURPOSE_MAX])
    if slots.overseas:
        add("fkey", key="Tab")
        add("field", target="OVRSEA", value="Y")
    add("fkey", key="F9" if slots.reuse_prev_proj else "F4")
    add("field", target="PROJ", value=slots.proj_code)
    add("fkey", key="Enter")
    add("fkey", key="Enter")
    return steps


def fill(request: RequestInput, slot_fn: SlotExtractor, context: str = "") -> FilledKeysequence | Refusal:
    missing = required_missing(request.fields)
    if missing:
        return Refusal(reason="required fields missing in request", missing_fields=missing)

    slots = slot_fn(request, context)
    slots.dest_code = slots.dest_code.upper()
    slots.purpose = slots.purpose[:PURPOSE_MAX]
    return FilledKeysequence(workflow=request.workflow, steps=assemble(slots), slots=slots)


def ground(db: Session, query: str, top_k: int = 6) -> str:
    chunks = hybrid_search(db, query, top_k=top_k)
    return "\n\n".join(chunk.text for chunk in chunks)


def extract_slots(request: RequestInput, context: str = "") -> Slots:
    import json

    prompt = (
        "# 手順書・指針 (RAG)\n" + context + "\n\n"
        "# 指示\n" + request.instruction + "\n\n"
        "# フィールド値\n" + json.dumps(request.fields, ensure_ascii=False)
    )
    data = ollama_client.generate_json(SLOT_SYSTEM, prompt)
    return Slots(**data)
