"""replace recipe_local with library

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31

Perubahan:
  - Buat tabel library (UUID PK, + kolom video_id, visibility, stars)
  - Migrasi data dari recipe_local ke library (video_id diambil dari JSONB recipe)
  - Drop tabel recipe_local
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Buat tabel library
    op.create_table(
        "library",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "session_id", UUID(as_uuid=True), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.String(), nullable=False, server_default=""),
        sa.Column("recipe", JSONB(), nullable=False, server_default="{}"),
        sa.Column("visibility", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_library_session_id", "library", ["session_id"])
    op.create_index("ix_library_user_id", "library", ["user_id"])

    # 2. Salin data dari recipe_local ke library
    #    video_id diambil dari kolom JSONB recipe->'video_id'
    op.execute("""
        INSERT INTO library (id, title, session_id, user_id, video_id, recipe, visibility, stars, created_at)
        SELECT
            id,
            title,
            session_id,
            user_id,
            COALESCE(recipe->>'video_id', '') AS video_id,
            recipe,
            0 AS visibility,
            0 AS stars,
            created_at
        FROM recipe_local
    """)

    # 3. Drop tabel recipe_local (index dan FK dihapus otomatis di PostgreSQL)
    op.drop_index("ix_recipe_local_user_id", table_name="recipe_local")
    op.drop_index("ix_recipe_local_session_id", table_name="recipe_local")
    op.drop_constraint("fk_recipe_local_user_id", "recipe_local", type_="foreignkey")
    op.drop_table("recipe_local")


def downgrade() -> None:
    # Buat ulang recipe_local
    op.create_table(
        "recipe_local",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipe_local_session_id", "recipe_local", ["session_id"])
    op.create_index("ix_recipe_local_user_id", "recipe_local", ["user_id"])
    op.create_foreign_key(
        "fk_recipe_local_user_id", "recipe_local", "users", ["user_id"], ["id"]
    )

    # Salin data balik dari library ke recipe_local
    op.execute("""
        INSERT INTO recipe_local (id, title, session_id, user_id, recipe, created_at)
        SELECT id, title, session_id, user_id, recipe, created_at
        FROM library
    """)

    # Drop library
    op.drop_index("ix_library_user_id", table_name="library")
    op.drop_index("ix_library_session_id", table_name="library")
    op.drop_table("library")
