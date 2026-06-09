from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

OLD_WORKFLOW = "shukko"
NEW_WORKFLOW = "shutchou"
WORKFLOW_TABLES = ("tasks", "personal_corrections", "operation_docs")


def rewrite_workflow(bind, old: str, new: str) -> None:
    for name in WORKFLOW_TABLES:
        table = sa.table(name, sa.column("workflow", sa.String))
        bind.execute(sa.update(table).where(table.c.workflow == old).values(workflow=new))


def upgrade() -> None:
    rewrite_workflow(op.get_bind(), OLD_WORKFLOW, NEW_WORKFLOW)


def downgrade() -> None:
    rewrite_workflow(op.get_bind(), NEW_WORKFLOW, OLD_WORKFLOW)
