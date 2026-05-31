import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    pass


class OperationDoc(Base):
    __tablename__ = "operation_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("operation_docs.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    fts: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedup_key: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, nullable=True)
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (UniqueConstraint("task_id", "attempt_no", name="uq_executions_task_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    final_screen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_created: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    executed_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    correction_candidate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("task_id", "version", name="uq_plans_task_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis: Mapped[dict] = mapped_column(JSONB, nullable=False)
    keysequence: Mapped[list] = mapped_column(JSONB, nullable=False)
    grounding: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    approver: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    approver: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
