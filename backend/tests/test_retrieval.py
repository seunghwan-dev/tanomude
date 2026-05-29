import hashlib
import re

from sqlalchemy import func, select

from backend.ingest import ingest_manual
from backend.models import EMBEDDING_DIM, KnowledgeChunk, OperationDoc
from backend.retrieval import RRF_K, hybrid_search, rrf_fuse

SYNTH = """## 1. alpha topic
unique_alpha apples orchard
## 2. beta topic
unique_beta bananas grove
## 3. gamma topic
unique_gamma cherries
"""


def _fake_embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        index = int(hashlib.md5(token.encode()).hexdigest(), 16) % EMBEDDING_DIM
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


def _fake_passages(texts: list[str]) -> list[list[float]]:
    return [_fake_embed(text) for text in texts]


def test_rrf_fuse_rewards_agreement():
    fused = rrf_fuse([[10, 20, 30], [20, 40]])
    scores = dict(fused)
    assert fused[0][0] == 20
    assert scores[20] == 1.0 / (RRF_K + 2) + 1.0 / (RRF_K + 1)
    assert scores[10] == 1.0 / (RRF_K + 1)


def test_hybrid_search_ranks_expected_chunk(db):
    ingest_manual(db, workflow="synth", title="synth", source="synth.md",
                  markdown=SYNTH, embed_fn=_fake_passages)
    results = hybrid_search(db, "unique_beta bananas", top_k=3, embed_query_fn=_fake_embed)
    assert results
    top = results[0]
    assert top.section == "2"
    assert "beta" in top.heading
    assert top.rank == 1
    assert top.score > 0
    assert top.chunk_id is not None
    assert top.doc_id is not None
    assert top.text


def test_hybrid_search_structured_output_shape(db):
    ingest_manual(db, workflow="synth", title="synth", source="synth.md",
                  markdown=SYNTH, embed_fn=_fake_passages)
    results = hybrid_search(db, "unique_gamma cherries", top_k=3, embed_query_fn=_fake_embed)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    assert "3" in [r.section for r in results]


def _chunk_count(db, doc_id):
    return db.scalar(select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))


def test_ingest_is_idempotent_by_source(db):
    first = ingest_manual(db, workflow="synth", title="synth", source="synth.md",
                          markdown=SYNTH, embed_fn=_fake_passages)
    expected = _chunk_count(db, first.id)
    second = ingest_manual(db, workflow="synth", title="synth", source="synth.md",
                           markdown=SYNTH, embed_fn=_fake_passages)
    assert db.scalar(select(func.count()).select_from(OperationDoc)) == 1
    assert _chunk_count(db, second.id) == expected
    assert first.id != second.id


def test_doc_delete_cascades_chunks(db):
    doc = ingest_manual(db, workflow="synth", title="synth", source="synth.md",
                        markdown=SYNTH, embed_fn=_fake_passages)
    assert _chunk_count(db, doc.id) > 0
    db.delete(doc)
    db.commit()
    assert db.scalar(select(func.count()).select_from(KnowledgeChunk)) == 0
