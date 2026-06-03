import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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

    steps: Mapped[list["TaskStep"]] = relationship(
        order_by="TaskStep.ordinal", passive_deletes=True
    )


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


class PersonalCorrection(Base):
    __tablename__ = "personal_corrections"
    __table_args__ = (
        Index("ix_personal_corrections_workflow_status", "workflow", "status"),
        Index(
            "uq_personal_corrections_active_lineage",
            "workflow",
            "trigger",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correction_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("personal_corrections.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    approver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskStep(Base):
    __tablename__ = "task_steps"
    __table_args__ = (UniqueConstraint("execution_id", "ordinal", name="uq_task_steps_execution_ordinal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    intent: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[dict] = mapped_column(JSONB, nullable=False)
    screen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    screen_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_docs: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    results: Mapped[list["EvalResult"]] = relationship(back_populates="case", passive_deletes=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    routing_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    verify_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_steps: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_at_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_at_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_at_expected: Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_delta: Mapped[float | None] = mapped_column(Float, nullable=True)

    results: Mapped[list["EvalResult"]] = relationship(back_populates="run", passive_deletes=True)


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (UniqueConstraint("run_id", "case_id", name="uq_eval_results_run_case"),)

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_runs.run_id", ondelete="CASCADE"), index=True, nullable=False
    )
    case_id: Mapped[str] = mapped_column(
        ForeignKey("eval_cases.case_id", ondelete="CASCADE"), index=True, nullable=False
    )
    actual_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    field_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    step_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replan_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_hits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["EvalRun"] = relationship(back_populates="results")
    case: Mapped["EvalCase"] = relationship(back_populates="results")
