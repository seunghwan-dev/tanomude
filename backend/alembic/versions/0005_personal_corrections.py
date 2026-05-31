from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personal_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow", sa.String(length=64), nullable=False),
        sa.Column("trigger", JSONB(), nullable=False),
        sa.Column("correction_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("personal_corrections.id"), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("approver", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_personal_corrections_workflow_status", "personal_corrections", ["workflow", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_personal_corrections_workflow_status", table_name="personal_corrections")
    op.drop_table("personal_corrections")
