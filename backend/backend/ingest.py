from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from backend.chunker import chunk_by_structure
from backend.embedding import embed_passages
from backend.models import KnowledgeChunk, OperationDoc

Embedder = Callable[[list[str]], list[list[float]]]

MANUALS_DIR = Path(__file__).resolve().parent / "manuals"


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
