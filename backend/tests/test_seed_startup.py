import pytest
from sqlalchemy import delete, func, select

from backend import ingest
from backend.config import settings
from backend.ingest import ingest_manual, load_manual, run_startup_seed
from backend.models import EMBEDDING_DIM, KnowledgeChunk, OperationDoc

MANUAL = load_manual("shukko_manual.md")


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * EMBEDDING_DIM for _ in texts]


def _reset(db) -> None:
    db.execute(delete(KnowledgeChunk))
    db.execute(delete(OperationDoc))
    db.commit()


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(KnowledgeChunk))


def test_seed_runs_when_enabled_and_store_empty(db, monkeypatch):
    _reset(db)
    monkeypatch.setattr(settings, "seed_on_startup", True)
    monkeypatch.setattr(ingest, "embedding_health", lambda: True)
    seeded = run_startup_seed(db, embed_fn=_fake_embed)
    assert seeded > 0
    assert _count(db) == seeded


def test_seed_is_idempotent_when_store_populated(db, monkeypatch):
    _reset(db)
    monkeypatch.setattr(settings, "seed_on_startup", True)
    monkeypatch.setattr(ingest, "embedding_health", lambda: True)
    ingest_manual(db, workflow="shukko", title=ingest.SEED_TITLE,
                  source=ingest.SEED_SOURCE, markdown=MANUAL, embed_fn=_fake_embed)
    before = _count(db)
    assert before > 0
    seeded = run_startup_seed(db, embed_fn=_fake_embed)
    assert seeded == 0
    assert _count(db) == before


def test_seed_skipped_when_flag_off(db, monkeypatch):
    _reset(db)
    monkeypatch.setattr(settings, "seed_on_startup", False)
    monkeypatch.setattr(ingest, "embedding_health", lambda: pytest.fail("embedding health checked while flag is off"))
    seeded = run_startup_seed(db, embed_fn=_fake_embed)
    assert seeded == 0
    assert _count(db) == 0
