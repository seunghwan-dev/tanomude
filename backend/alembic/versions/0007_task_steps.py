from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", sa.Integer(), sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("intent", sa.String(length=128), nullable=False),
        sa.Column("action", JSONB(), nullable=False),
        sa.Column("screen", sa.String(length=64), nullable=True),
        sa.Column("screen_fields", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("errors", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("execution_id", "ordinal", name="uq_task_steps_execution_ordinal"),
    )
    op.create_index("ix_task_steps_task_id", "task_steps", ["task_id"])
    op.create_index("ix_task_steps_execution_id", "task_steps", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_task_steps_execution_id", table_name="task_steps")
    op.drop_index("ix_task_steps_task_id", table_name="task_steps")
    op.drop_table("task_steps")
