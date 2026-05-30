from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip_application",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_trip_application_idempotency_key", "trip_application", ["idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_trip_application_idempotency_key", "trip_application", type_="unique"
    )
    op.drop_column("trip_application", "idempotency_key")
