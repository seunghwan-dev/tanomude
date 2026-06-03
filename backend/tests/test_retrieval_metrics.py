import pytest

from backend import retrieval_eval
from backend.chunker import chunk_by_structure
from backend.ingest import load_manual
from backend.models import EvalRun
from backend.retrieval_eval import (
    QUERYSET,
    QueryResult,
    RetrievalScore,
    aggregate_retrieval,
    run_retrieval_eval,
    score_query,
)


def _result(expected, hybrid) -> QueryResult:
    return QueryResult(query="q", expected=set(expected), hybrid_sections=list(hybrid))


def test_score_query_full_precision_and_recall():
    score = score_query(_result({"4", "1"}, ["4", "1", "9"]), k=3)
    assert score.precision_at_k == pytest.approx(2 / 3)
    assert score.recall_at_k == 1.0


def test_score_query_partial():
    score = score_query(_result({"4", "1"}, ["4", "9", "8"]), k=3)
    assert score.precision_at_k == pytest.approx(1 / 3)
    assert score.recall_at_k == 0.5


def test_score_query_counts_duplicate_relevant_chunks():
    score = score_query(_result({"4"}, ["4", "4", "9"]), k=3)
    assert score.precision_at_k == pytest.approx(2 / 3)
    assert score.recall_at_k == 1.0


def test_score_query_no_relevant():
    score = score_query(_result({"2.1"}, ["9", "8", "7"]), k=3)
    assert score.precision_at_k == 0.0
    assert score.recall_at_k == 0.0


def test_aggregate_retrieval_means():
    scores = [
        RetrievalScore(query="a", precision_at_k=2 / 3, recall_at_k=1.0),
        RetrievalScore(query="b", precision_at_k=1 / 3, recall_at_k=0.5),
    ]
    metrics = aggregate_retrieval(scores)
    assert metrics["precision_at_k"] == pytest.approx(0.5)
    assert metrics["recall_at_k"] == pytest.approx(0.75)


def test_aggregate_retrieval_empty_is_null():
    metrics = aggregate_retrieval([])
    assert metrics["precision_at_k"] is None
    assert metrics["recall_at_k"] is None


def test_queryset_labels_exist_in_manual():
    sections = {chunk.section for chunk in chunk_by_structure(load_manual("shukko_manual.md"))}
    labeled = set().union(*(query.expected_sections for query in QUERYSET))
    assert labeled
    assert labeled <= sections


def test_run_retrieval_eval_persists_precision_recall(db, monkeypatch):
    fake_results = [
        _result({"4"}, ["4", "9", "8"]),
        _result({"1"}, ["1", "2", "3"]),
    ]
    monkeypatch.setattr(retrieval_eval, "run_eval", lambda db, top_k=3: fake_results)
    run_id, scores = run_retrieval_eval(db, k=3)
    assert len(scores) == 2
    run = db.get(EvalRun, run_id)
    assert run.config == {"k": 3}
    assert run.precision_at_k == pytest.approx(1 / 3)
    assert run.recall_at_k == 1.0
    db.delete(run)
    db.commit()
