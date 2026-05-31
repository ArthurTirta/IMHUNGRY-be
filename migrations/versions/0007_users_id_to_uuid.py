"""replace users.id integer with uuid

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-31

Migrates users.id from Integer to UUID and updates all FK references.
Also creates tutorial_stars table (was referenced in code but never migrated).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- users: add UUID column and map existing rows ---
    op.add_column("users", sa.Column("id_uuid", UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE users SET id_uuid = gen_random_uuid()")
    op.alter_column("users", "id_uuid", nullable=False)

    # --- chat: migrate user_id ---
    op.add_column("chat", sa.Column("user_id_uuid", UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE chat
        SET user_id_uuid = users.id_uuid
        FROM users
        WHERE chat.user_id = users.id
    """)
    op.alter_column("chat", "user_id_uuid", nullable=False)
    op.drop_constraint("chat_user_id_fkey", "chat", type_="foreignkey")
    op.drop_index("ix_chat_user_id", table_name="chat")
    op.drop_column("chat", "user_id")
    op.alter_column("chat", "user_id_uuid", new_column_name="user_id")
    op.create_index("ix_chat_user_id", "chat", ["user_id"])

    # --- library: migrate user_id ---
    op.add_column("library", sa.Column("user_id_uuid", UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE library
        SET user_id_uuid = users.id_uuid
        FROM users
        WHERE library.user_id = users.id
    """)
    op.alter_column("library", "user_id_uuid", nullable=False)
    op.drop_constraint("library_user_id_fkey", "library", type_="foreignkey")
    op.drop_index("ix_library_user_id", table_name="library")
    op.drop_column("library", "user_id")
    op.alter_column("library", "user_id_uuid", new_column_name="user_id")
    op.create_index("ix_library_user_id", "library", ["user_id"])

    # --- users: swap PK to UUID ---
    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_column("users", "id")
    op.alter_column("users", "id_uuid", new_column_name="id")
    op.create_primary_key("users_pkey", "users", ["id"])
    op.create_index("ix_users_id", "users", ["id"])

    # --- re-add FK constraints ---
    op.create_foreign_key("chat_user_id_fkey", "chat", "users", ["user_id"], ["id"])
    op.create_foreign_key("library_user_id_fkey", "library", "users", ["user_id"], ["id"])

    # --- tutorial_stars ---
    op.create_table(
        "tutorial_stars",
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipe_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["library.id"]),
        sa.PrimaryKeyConstraint("user_id", "recipe_id"),
    )


def downgrade() -> None:
    op.drop_table("tutorial_stars")

    op.drop_constraint("library_user_id_fkey", "library", type_="foreignkey")
    op.drop_constraint("chat_user_id_fkey", "chat", type_="foreignkey")

    op.add_column("users", sa.Column("id_int", sa.Integer(), autoincrement=True, nullable=True))
    op.execute("""
        UPDATE users SET id_int = sub.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, username) AS rn
            FROM users
        ) sub
        WHERE users.id = sub.id
    """)
    op.alter_column("users", "id_int", nullable=False)

    op.add_column("chat", sa.Column("user_id_int", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE chat SET user_id_int = users.id_int
        FROM users WHERE chat.user_id = users.id
    """)
    op.alter_column("chat", "user_id_int", nullable=False)
    op.drop_index("ix_chat_user_id", table_name="chat")
    op.drop_column("chat", "user_id")
    op.alter_column("chat", "user_id_int", new_column_name="user_id")
    op.create_index("ix_chat_user_id", "chat", ["user_id"])

    op.add_column("library", sa.Column("user_id_int", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE library SET user_id_int = users.id_int
        FROM users WHERE library.user_id = users.id
    """)
    op.alter_column("library", "user_id_int", nullable=False)
    op.drop_index("ix_library_user_id", table_name="library")
    op.drop_column("library", "user_id")
    op.alter_column("library", "user_id_int", new_column_name="user_id")
    op.create_index("ix_library_user_id", "library", ["user_id"])

    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_column("users", "id")
    op.alter_column("users", "id_int", new_column_name="id")
    op.create_primary_key("users_pkey", "users", ["id"])
    op.create_index("ix_users_id", "users", ["id"])

    op.create_foreign_key("chat_user_id_fkey", "chat", "users", ["user_id"], ["id"])
    op.create_foreign_key("library_user_id_fkey", "library", "users", ["user_id"], ["id"])
