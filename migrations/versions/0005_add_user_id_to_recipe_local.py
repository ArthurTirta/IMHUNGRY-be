"""add user_id to recipe_local

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tambah kolom user_id (nullable dulu agar data lama tidak error)
    op.add_column("recipe_local", sa.Column("user_id", sa.Integer(), nullable=True))
    # Isi data lama dengan user_id dari tabel chat (via session_id)
    op.execute("""
        UPDATE recipe_local
        SET user_id = chat.user_id
        FROM chat
        WHERE recipe_local.session_id = chat.id
    """)
    # Set NOT NULL setelah data terisi
    op.alter_column("recipe_local", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_recipe_local_user_id", "recipe_local", "users", ["user_id"], ["id"]
    )
    op.create_index("ix_recipe_local_user_id", "recipe_local", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_local_user_id", table_name="recipe_local")
    op.drop_constraint("fk_recipe_local_user_id", "recipe_local", type_="foreignkey")
    op.drop_column("recipe_local", "user_id")
