from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_cases",
        sa.Column("case_id", sa.String(length=64), primary_key=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("input", JSONB(), nullable=False),
        sa.Column("expected_outcome", sa.String(length=16), nullable=False),
        sa.Column("expected_docs", JSONB(), nullable=True),
    )
    op.create_table(
        "eval_runs",
        sa.Column("run_id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("field_accuracy", sa.Float(), nullable=True),
        sa.Column("routing_accuracy", sa.Float(), nullable=True),
        sa.Column("recovery_rate", sa.Float(), nullable=True),
        sa.Column("verify_pass_rate", sa.Float(), nullable=True),
        sa.Column("avg_steps", sa.Float(), nullable=True),
        sa.Column("precision_at_k", sa.Float(), nullable=True),
        sa.Column("recall_at_k", sa.Float(), nullable=True),
        sa.Column("growth_delta", sa.Float(), nullable=True),
    )
    op.create_table(
        "eval_results",
        sa.Column("result_id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("eval_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.String(length=64), sa.ForeignKey("eval_cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("actual_outcome", sa.String(length=16), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("field_accuracy", sa.Float(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=True),
        sa.Column("replan_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retrieval_hits", JSONB(), nullable=True),
        sa.UniqueConstraint("run_id", "case_id", name="uq_eval_results_run_case"),
    )
    op.create_index("ix_eval_results_run_id", "eval_results", ["run_id"])
    op.create_index("ix_eval_results_case_id", "eval_results", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_results_case_id", table_name="eval_results")
    op.drop_index("ix_eval_results_run_id", table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_table("eval_cases")
