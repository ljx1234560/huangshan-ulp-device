"""Add BLE bridge sessions and motion provenance.

Revision ID: 20261118_0002
Revises: 20261118_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0002"
down_revision = "20261118_0001"
branch_labels = None
depends_on = None


def has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def has_column(table: str, name: str) -> bool:
    return any(column["name"] == name for column in sa.inspect(op.get_bind()).get_columns(table))


def has_index(table: str, name: str) -> bool:
    return any(index["name"] == name for index in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    # 0001 was originally metadata-driven. These guards make the migration
    # correct for both an existing phase-two database and a fresh install whose
    # metadata already contains the phase-three columns.
    if not has_column("devices", "sync_protocol_version"):
        op.add_column("devices", sa.Column("sync_protocol_version", sa.Integer(), nullable=True))
    if not has_column("activity_records", "source"):
        op.add_column("activity_records", sa.Column("source", sa.String(length=30), nullable=False, server_default="unknown"))
    if not has_index("activity_records", "ix_activity_records_source"):
        op.create_index("ix_activity_records_source", "activity_records", ["source"])
    if not has_column("activity_daily", "data_source"):
        op.add_column("activity_daily", sa.Column("data_source", sa.String(length=30), nullable=False, server_default="unknown"))
    if not has_index("activity_daily", "ix_activity_daily_data_source"):
        op.create_index("ix_activity_daily_data_source", "activity_daily", ["data_source"])
    if not has_column("sync_logs", "transport"):
        op.add_column("sync_logs", sa.Column("transport", sa.String(length=30), nullable=False, server_default="direct_api"))
    if not has_index("sync_logs", "ix_sync_logs_transport"):
        op.create_index("ix_sync_logs_transport", "sync_logs", ["transport"])
    if not has_table("bridge_sessions"):
        op.create_table(
        "bridge_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="authorized"),
        sa.Column("message", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        )
    for name, columns in (
        ("ix_bridge_sessions_device_id", ["device_id"]),
        ("ix_bridge_sessions_user_id", ["user_id"]),
        ("ix_bridge_sessions_token_hash", ["token_hash"]),
        ("ix_bridge_sessions_expires_at", ["expires_at"]),
        ("ix_bridge_sessions_state", ["state"]),
    ):
        if not has_index("bridge_sessions", name):
            op.create_index(name, "bridge_sessions", columns)


def downgrade() -> None:
    op.drop_table("bridge_sessions")
    op.drop_index("ix_sync_logs_transport", table_name="sync_logs")
    op.drop_column("sync_logs", "transport")
    op.drop_index("ix_activity_daily_data_source", table_name="activity_daily")
    op.drop_column("activity_daily", "data_source")
    op.drop_index("ix_activity_records_source", table_name="activity_records")
    op.drop_column("activity_records", "source")
    op.drop_column("devices", "sync_protocol_version")
