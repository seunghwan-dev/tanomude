from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tasks", "status", type_=sa.String(length=24), existing_type=sa.String(length=16), existing_nullable=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.Column("keysequence", JSONB(), nullable=False),
        sa.Column("grounding", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("task_id", "version", name="uq_plans_task_version"),
    )
    op.create_index("ix_plans_task_id", "plans", ["task_id"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("approver", sa.String(length=64), nullable=False),
        sa.Column("decision_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_approvals_task_id", "approvals", ["task_id"])
    op.create_index("ix_approvals_plan_id", "approvals", ["plan_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("approver", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("decision_text", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_log_task_id", "audit_log", ["task_id"])
    op.create_index("ix_audit_log_plan_id", "audit_log", ["plan_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("plans")
