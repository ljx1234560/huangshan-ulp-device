"""Add persisted AI coaching generations.

Revision ID: 20261124_0004
Revises: 20261119_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0004"
down_revision = "20261119_0003"
branch_labels = None
depends_on = None


def has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def has_index(table: str, name: str) -> bool:
    return any(index["name"] == name for index in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    # 0001 is metadata-driven, so a fresh install may already contain a model
    # added by a later revision. Guards preserve both fresh and incremental upgrades.
    if not has_table("coaching_generations"):
        op.create_table(
            "coaching_generations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("advice_json", sa.JSON(), nullable=False),
            sa.Column("insight_json", sa.JSON(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    for name, columns in (
        ("ix_coaching_generations_user_id", ["user_id"]),
        ("ix_coaching_generations_provider", ["provider"]),
        ("ix_coaching_generations_is_demo", ["is_demo"]),
        ("ix_coaching_generations_created_at", ["created_at"]),
    ):
        if not has_index("coaching_generations", name):
            op.create_index(name, "coaching_generations", columns)


def downgrade() -> None:
    op.drop_table("coaching_generations")
