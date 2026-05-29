import pytest
from sqlalchemy import func, select

from backend import embedding
from backend.chunker import chunk_by_structure
from backend.ingest import ingest_manual, load_manual
from backend.models import EMBEDDING_DIM, KnowledgeChunk, OperationDoc

MANUAL = load_manual("shukko_manual.md")

requires_tei = pytest.mark.skipif(not embedding.health(), reason="embedding service (TEI) not reachable")


def test_structure_chunking_splits_on_headings():
    chunks = chunk_by_structure(MANUAL)
    assert len(chunks) >= 8
    sections = {chunk.section for chunk in chunks}
    assert "2.1" in sections
    assert "2.5" in sections
    proj_chunk = next(c for c in chunks if c.section == "2.5")
    assert proj_chunk.heading.startswith("案件")
    assert "P-###" in proj_chunk.text


@requires_tei
def test_ingest_persists_doc_and_chunks_with_embeddings(db):
    doc = ingest_manual(db, workflow="shukko", title="出張申請 操作マニュアル",
                        source="shukko_manual.md", markdown=MANUAL)
    assert doc.id is not None

    rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id).order_by(KnowledgeChunk.ordinal)).all()
    expected = len(chunk_by_structure(MANUAL))
    assert len(rows) == expected

    for row in rows:
        assert row.section
        assert row.heading
        assert len(row.embedding) == EMBEDDING_DIM

    assert db.scalar(select(func.count()).select_from(OperationDoc)) == 1


@requires_tei
def test_fts_column_populated(db):
    doc = ingest_manual(db, workflow="shukko", title="t", source="shukko_manual.md", markdown=MANUAL)
    matched = db.scalar(
        select(func.count())
        .select_from(KnowledgeChunk)
        .where(KnowledgeChunk.doc_id == doc.id)
        .where(KnowledgeChunk.fts.op("@@")(func.to_tsquery("simple", "DEST")))
    )
    assert matched >= 1
