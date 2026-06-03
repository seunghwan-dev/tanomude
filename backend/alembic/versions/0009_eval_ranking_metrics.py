from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_runs", sa.Column("precision_at_expected", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mrr", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_runs", "mrr")
    op.drop_column("eval_runs", "precision_at_expected")
