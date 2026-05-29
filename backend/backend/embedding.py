import httpx

from backend.config import settings

PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def _embed(inputs: list[str], client: httpx.Client | None = None) -> list[list[float]]:
    owns_client = client is None
    active = client or httpx.Client(base_url=settings.embedding_url, timeout=60.0)
    try:
        response = active.post("/embed", json={"inputs": inputs})
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            active.close()


def embed_passages(texts: list[str], client: httpx.Client | None = None) -> list[list[float]]:
    return _embed([PASSAGE_PREFIX + text for text in texts], client)


def embed_query(text: str, client: httpx.Client | None = None) -> list[float]:
    return _embed([QUERY_PREFIX + text], client)[0]


def health(timeout: float = 3.0) -> bool:
    try:
        with httpx.Client(base_url=settings.embedding_url, timeout=timeout) as client:
            return client.get("/health").status_code == 200
    except Exception:
        return False
