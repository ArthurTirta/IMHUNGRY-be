"""create recipe_local table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_local",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipe", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipe_local_session_id", "recipe_local", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_local_session_id", table_name="recipe_local")
    op.drop_table("recipe_local")
