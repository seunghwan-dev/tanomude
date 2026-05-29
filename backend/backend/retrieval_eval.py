from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.embedding import embed_query
from backend.models import KnowledgeChunk
from backend.retrieval import QueryEmbedder, fts_search_ids, rrf_fuse, vector_search_ids


@dataclass
class EvalQuery:
    query: str
    expected_sections: set[str]


QUERYSET: list[EvalQuery] = [
    EvalQuery("出張申請の手順", {"4", "1"}),
    EvalQuery("DEST", {"2.1"}),
    EvalQuery("P-### 再利用", {"3.4", "2.5"}),
    EvalQuery("却下", {"3.2"}),
]


@dataclass
class QueryResult:
    query: str
    expected: set[str]
    vector_sections: list[str] = field(default_factory=list)
    fts_sections: list[str] = field(default_factory=list)
    hybrid_sections: list[str] = field(default_factory=list)

    def hit(self, sections: list[str]) -> bool:
        return bool(self.expected.intersection(sections))


def _sections_for(db: Session, ids: list[int]) -> list[str]:
    if not ids:
        return []
    rows = {
        chunk.id: chunk.section
        for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))).all()
    }
    return [rows[chunk_id] for chunk_id in ids if chunk_id in rows]


def run_eval(
    db: Session,
    top_k: int = 3,
    top_n: int = 20,
    embed_query_fn: QueryEmbedder = embed_query,
) -> list[QueryResult]:
    results: list[QueryResult] = []
    for case in QUERYSET:
        query_vector = embed_query_fn(case.query)
        vector_ids = vector_search_ids(db, query_vector, top_n)
        fts_ids = fts_search_ids(db, case.query, top_n)
        fused = [chunk_id for chunk_id, _ in rrf_fuse([vector_ids, fts_ids])][:top_k]

        results.append(
            QueryResult(
                query=case.query,
                expected=case.expected_sections,
                vector_sections=_sections_for(db, vector_ids[:top_k]),
                fts_sections=_sections_for(db, fts_ids[:top_k]),
                hybrid_sections=_sections_for(db, fused),
            )
        )
    return results
