"""Add durable image generation metadata and local storage fields.

Revision ID: 20261124_0005
Revises: 20261124_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0005"
down_revision = "20261124_0004"
branch_labels = None
depends_on = None


def has_column(table: str, name: str) -> bool:
    return any(column["name"] == name for column in sa.inspect(op.get_bind()).get_columns(table))


def has_index(table: str, name: str) -> bool:
    return any(index["name"] == name for index in sa.inspect(op.get_bind()).get_indexes(table))


def add_column(table: str, column: sa.Column) -> None:
    if not has_column(table, column.name):
        op.add_column(table, column)


def upgrade() -> None:
    add_column("pet_generation_jobs", sa.Column("model", sa.String(100), nullable=False, server_default="mock-image-v1"))
    add_column("pet_generation_jobs", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    add_column("pet_generation_jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    add_column("pet_generation_jobs", sa.Column("error_code", sa.String(80), nullable=True))
    add_column("pet_generation_jobs", sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"))
    add_column("pet_generation_jobs", sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"))
    add_column("pet_generation_jobs", sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"))
    add_column("pet_generation_jobs", sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"))
    add_column("pet_generation_jobs", sa.Column("cost_microusd", sa.Integer(), nullable=True))
    add_column("pet_generation_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    add_column("pet_assets", sa.Column("storage_key", sa.Text(), nullable=True))
    add_column("pet_assets", sa.Column("model", sa.String(100), nullable=False, server_default="mock-image-v1"))
    add_column("pet_assets", sa.Column("width", sa.Integer(), nullable=True))
    add_column("pet_assets", sa.Column("height", sa.Integer(), nullable=True))
    for table, name, columns in (
        ("pet_generation_jobs", "ix_pet_generation_jobs_model", ["model"]),
        ("pet_generation_jobs", "ix_pet_generation_jobs_request_fingerprint", ["request_fingerprint"]),
    ):
        if not has_index(table, name):
            op.create_index(name, table, columns)


def downgrade() -> None:
    op.drop_index("ix_pet_generation_jobs_request_fingerprint", table_name="pet_generation_jobs")
    op.drop_index("ix_pet_generation_jobs_model", table_name="pet_generation_jobs")
    for column in ("height", "width", "model", "storage_key"):
        op.drop_column("pet_assets", column)
    for column in (
        "started_at", "cost_microusd", "total_tokens", "output_tokens", "input_tokens",
        "duration_ms", "error_code", "attempt_count", "request_fingerprint", "model",
    ):
        op.drop_column("pet_generation_jobs", column)
