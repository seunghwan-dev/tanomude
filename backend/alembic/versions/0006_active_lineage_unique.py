from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_personal_corrections_active_lineage",
        "personal_corrections",
        ["workflow", "trigger"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_personal_corrections_active_lineage", table_name="personal_corrections")
