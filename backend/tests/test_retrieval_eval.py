import pytest

from backend import embedding
from backend.ingest import ingest_manual, load_manual
from backend.retrieval_eval import run_eval

pytestmark = pytest.mark.skipif(not embedding.health(), reason="embedding service (TEI) not reachable")


def test_retrieval_eval_hybrid_hits_majority(db):
    ingest_manual(db, workflow="shukko", title="出張申請 操作マニュアル",
                  source="shukko_manual.md", markdown=load_manual("shukko_manual.md"))
    results = run_eval(db, top_k=3)
    hybrid_hits = sum(1 for result in results if result.hit(result.hybrid_sections))
    assert hybrid_hits >= 3
