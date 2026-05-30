from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dedup_key", sa.String(length=200), nullable=True),
        sa.Column("workflow", sa.String(length=64), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("fields", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tasks_dedup_key", "tasks", ["dedup_key"], unique=True)

    op.create_table(
        "executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("final_screen", sa.String(length=64), nullable=True),
        sa.Column("trip_id", sa.Integer(), nullable=True),
        sa.Column("trip_created", sa.Boolean(), nullable=True),
        sa.Column("executed_steps", sa.Integer(), nullable=False),
        sa.Column("errors", JSONB(), nullable=True),
        sa.Column("correction_candidate", JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_id", "attempt_no", name="uq_executions_task_attempt"),
    )
    op.create_index("ix_executions_task_id", "executions", ["task_id"])


def downgrade() -> None:
    op.drop_table("executions")
    op.drop_index("ix_tasks_dedup_key", table_name="tasks")
    op.drop_table("tasks")
