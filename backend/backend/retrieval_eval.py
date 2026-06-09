from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.embedding import embed_query
from backend.models import EvalRun, KnowledgeChunk
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


class RetrievalScore(BaseModel):
    query: str
    precision_at_k: float
    recall_at_k: float
    precision_at_expected: float
    mrr: float


def _reciprocal_rank(result: QueryResult) -> float:
    for rank, section in enumerate(result.hybrid_sections, start=1):
        if section in result.expected:
            return 1.0 / rank
    return 0.0


def score_query(result: QueryResult, k: int) -> RetrievalScore:
    relevant = sum(1 for section in result.hybrid_sections if section in result.expected)
    found = {section for section in result.hybrid_sections if section in result.expected}
    size = len(result.expected)
    at_expected = result.hybrid_sections[:size]
    precision = relevant / k if k else 0.0
    recall = len(found) / size if size else 0.0
    precision_at_expected = (
        sum(1 for section in at_expected if section in result.expected) / size if size else 0.0
    )
    return RetrievalScore(
        query=result.query,
        precision_at_k=precision,
        recall_at_k=recall,
        precision_at_expected=precision_at_expected,
        mrr=_reciprocal_rank(result),
    )


def aggregate_retrieval(scores: list[RetrievalScore]) -> dict[str, float | None]:
    if not scores:
        return {"precision_at_k": None, "recall_at_k": None, "precision_at_expected": None, "mrr": None}
    return {
        "precision_at_k": sum(score.precision_at_k for score in scores) / len(scores),
        "recall_at_k": sum(score.recall_at_k for score in scores) / len(scores),
        "precision_at_expected": sum(score.precision_at_expected for score in scores) / len(scores),
        "mrr": sum(score.mrr for score in scores) / len(scores),
    }


def run_retrieval_eval(db: Session, k: int = 3) -> tuple[int, list[RetrievalScore]]:
    scores = [score_query(result, k) for result in run_eval(db, top_k=k)]
    metrics = aggregate_retrieval(scores)
    run = EvalRun(
        config={"k": k},
        precision_at_k=metrics["precision_at_k"],
        recall_at_k=metrics["recall_at_k"],
        precision_at_expected=metrics["precision_at_expected"],
        mrr=metrics["mrr"],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.run_id, scores


def main(k: int = 3) -> int:
    import json

    from backend.db import SessionLocal
    from backend.embedding import health
    from backend.ingest import ingest_manual, load_manual

    if not health():
        print("embedding service unavailable; scoring logic verified, numbers deferred")
        return 0
    with SessionLocal() as db:
        ingest_manual(
            db,
            workflow="shutchou",
            title="出張申請 操作マニュアル",
            source="shukko_manual.md",
            markdown=load_manual("shukko_manual.md"),
        )
        run_id, scores = run_retrieval_eval(db, k=k)
        metrics = aggregate_retrieval(scores)
    print(json.dumps({"run_id": run_id, "k": k, **metrics}, ensure_ascii=False))
    for score in scores:
        print(json.dumps(score.model_dump(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
