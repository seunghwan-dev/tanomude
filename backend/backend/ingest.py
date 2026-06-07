import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.chunker import chunk_by_structure
from backend.config import settings
from backend.embedding import embed_passages, health as embedding_health
from backend.models import KnowledgeChunk, OperationDoc

Embedder = Callable[[list[str]], list[list[float]]]

MANUALS_DIR = Path(__file__).resolve().parent / "manuals"

SEED_TITLE = "出張申請 操作マニュアル"
SEED_SOURCE = "shukko_manual.md"

logger = logging.getLogger(__name__)


def load_manual(name: str) -> str:
    return (MANUALS_DIR / name).read_text(encoding="utf-8")


def ingest_manual(
    db: Session,
    workflow: str,
    title: str,
    source: str,
    markdown: str,
    embed_fn: Embedder = embed_passages,
) -> OperationDoc:
    db.execute(
        delete(OperationDoc).where(OperationDoc.workflow == workflow, OperationDoc.source == source)
    )
    db.flush()

    doc = OperationDoc(workflow=workflow, title=title, source=source)
    db.add(doc)
    db.flush()

    chunks = chunk_by_structure(markdown)
    vectors = embed_fn([chunk.text for chunk in chunks])

    for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors)):
        db.add(
            KnowledgeChunk(
                doc_id=doc.id,
                ordinal=ordinal,
                section=chunk.section,
                heading=chunk.heading,
                text=chunk.text,
                embedding=vector,
            )
        )
    db.commit()
    return doc


def run_startup_seed(db: Session, embed_fn: Embedder = embed_passages) -> int:
    if not settings.seed_on_startup:
        return 0
    if db.scalar(select(func.count()).select_from(KnowledgeChunk)):
        return 0
    if not embedding_health():
        logger.warning("seed_on_startup is set but the embedding service is unreachable; skipping manual seed")
        return 0
    ingest_manual(
        db,
        workflow="shukko",
        title=SEED_TITLE,
        source=SEED_SOURCE,
        markdown=load_manual(SEED_SOURCE),
        embed_fn=embed_fn,
    )
    seeded = db.scalar(select(func.count()).select_from(KnowledgeChunk))
    logger.info("seed_on_startup: ingested %d manual chunks into the platform store", seeded)
    return seeded
