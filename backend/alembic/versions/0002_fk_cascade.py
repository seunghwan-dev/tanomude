from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FK = "knowledge_chunks_doc_id_fkey"


def upgrade() -> None:
    op.drop_constraint(FK, "knowledge_chunks", type_="foreignkey")
    op.create_foreign_key(
        FK, "knowledge_chunks", "operation_docs", ["doc_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(FK, "knowledge_chunks", type_="foreignkey")
    op.create_foreign_key(FK, "knowledge_chunks", "operation_docs", ["doc_id"], ["id"])
