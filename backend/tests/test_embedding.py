import pytest

from backend import embedding
from backend.embedding import PASSAGE_PREFIX, QUERY_PREFIX, embed_passages, embed_query
from backend.models import EMBEDDING_DIM

requires_tei = pytest.mark.skipif(not embedding.health(), reason="embedding service (TEI) not reachable")


def test_passage_prefixes_are_asymmetric():
    assert PASSAGE_PREFIX != QUERY_PREFIX
    assert PASSAGE_PREFIX.startswith("passage:")
    assert QUERY_PREFIX.startswith("query:")


@requires_tei
def test_embed_passages_returns_1024d():
    vectors = embed_passages(["出張申請の標準手順", "案件コードは F4 で選択する"])
    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)


@requires_tei
def test_embed_query_returns_1024d():
    vector = embed_query("出張先はどう入力しますか")
    assert len(vector) == EMBEDDING_DIM
