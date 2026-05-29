from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "trip_application",
        "proj",
        existing_type=sa.String(length=8),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
    op.create_table(
        "mock_session",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("screen", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("mock_session")
    op.alter_column(
        "trip_application",
        "proj",
        existing_type=sa.String(length=5),
        type_=sa.String(length=8),
        existing_nullable=False,
    )
