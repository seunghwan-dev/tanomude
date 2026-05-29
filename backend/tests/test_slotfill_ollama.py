import json
from pathlib import Path

import pytest

from backend import embedding, ollama_client
from backend.ingest import ingest_manual, load_manual
from backend.slotfill import FilledKeysequence, Refusal, RequestInput, extract_slots, fill, ground

CASES = json.loads((Path(__file__).resolve().parent / "fixtures" / "cases.json").read_text(encoding="utf-8"))["cases"]

requires_models = pytest.mark.skipif(
    not (ollama_client.health() and embedding.health()),
    reason="ollama and/or embedding service not reachable",
)


@requires_models
@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_slotfill_matches_golden_or_refuses(case, db):
    ingest_manual(db, workflow="shukko", title="出張申請 操作マニュアル",
                  source="shukko_manual.md", markdown=load_manual("shukko_manual.md"))
    request = RequestInput(workflow="shukko", instruction=case["input"]["instruction"], fields=case["input"]["fields"])

    if case["case_id"] == "case_04_edge_empty_required":
        result = fill(request, extract_slots)
        assert isinstance(result, Refusal)
        assert "DEST" in result.missing_fields
        return

    context = ground(db, request.instruction)
    result = fill(request, extract_slots, context)
    assert isinstance(result, FilledKeysequence)

    golden = case["golden"]
    assert len(result.steps) == len(golden)
    for step, gold in zip(result.steps, golden):
        assert (step.type, step.target, step.key) == (gold["type"], gold["target"], gold["key"])
        if step.target == "PURPOSE":
            assert step.value and len(step.value) <= 20
        else:
            assert step.value == gold["value"]
