from collections.abc import Callable

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.embedding import embed_query
from backend.models import KnowledgeChunk

RRF_K = 60

QueryEmbedder = Callable[[str], list[float]]


class RetrievedChunk(BaseModel):
    chunk_id: int
    doc_id: int
    section: str
    heading: str
    text: str
    score: float
    rank: int


def vector_search_ids(db: Session, query_vector: list[float], top_n: int) -> list[int]:
    stmt = (
        select(KnowledgeChunk.id)
        .order_by(KnowledgeChunk.embedding.cosine_distance(query_vector))
        .limit(top_n)
    )
    return list(db.scalars(stmt).all())


def fts_search_ids(db: Session, query: str, top_n: int) -> list[int]:
    tsquery = func.plainto_tsquery("simple", query)
    stmt = (
        select(KnowledgeChunk.id)
        .where(KnowledgeChunk.fts.op("@@")(tsquery))
        .order_by(func.ts_rank(KnowledgeChunk.fts, tsquery).desc())
        .limit(top_n)
    )
    return list(db.scalars(stmt).all())


def rrf_fuse(ranked_lists: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ids in ranked_lists:
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def hybrid_search(
    db: Session,
    query: str,
    top_k: int = 5,
    top_n: int = 20,
    embed_query_fn: QueryEmbedder = embed_query,
    k: int = RRF_K,
) -> list[RetrievedChunk]:
    query_vector = embed_query_fn(query)
    vector_ids = vector_search_ids(db, query_vector, top_n)
    fts_ids = fts_search_ids(db, query, top_n)
    fused = rrf_fuse([vector_ids, fts_ids], k)[:top_k]

    chunk_ids = [chunk_id for chunk_id, _ in fused]
    chunks = {
        chunk.id: chunk
        for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids))).all()
    }

    results: list[RetrievedChunk] = []
    for rank, (chunk_id, score) in enumerate(fused, start=1):
        chunk = chunks[chunk_id]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                doc_id=chunk.doc_id,
                section=chunk.section,
                heading=chunk.heading,
                text=chunk.text,
                score=score,
                rank=rank,
            )
        )
    return results
