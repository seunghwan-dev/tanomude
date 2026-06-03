from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_runs", sa.Column("boundary_respect_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_runs", "boundary_respect_rate")
