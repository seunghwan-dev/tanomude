from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_application",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dest", sa.String(length=12), nullable=False),
        sa.Column("dept_date", sa.Date(), nullable=False),
        sa.Column("ret_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("proj", sa.String(length=8), nullable=False),
        sa.Column("overseas", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("trip_application")
