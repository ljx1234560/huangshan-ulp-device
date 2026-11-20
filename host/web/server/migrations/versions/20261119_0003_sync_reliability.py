"""Separate device cursors, HTTP offsets, and bridge liveness.

Revision ID: 20261119_0003
Revises: 20261118_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20261119_0003"
down_revision = "20261118_0002"
branch_labels = None
depends_on = None


def has_column(table: str, name: str) -> bool:
    return any(column["name"] == name for column in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not has_column("devices", "activity_cursor"):
        op.add_column("devices", sa.Column("activity_cursor", sa.Integer(), nullable=True))
    if not has_column("activity_records", "rtc_trusted"):
        op.add_column(
            "activity_records",
            sa.Column("rtc_trusted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not has_column("bridge_sessions", "running"):
        op.add_column(
            "bridge_sessions",
            sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not has_column("bridge_sessions", "last_sync_status"):
        op.add_column("bridge_sessions", sa.Column("last_sync_status", sa.String(length=20), nullable=True))
    if not has_column("bridge_sessions", "last_sync_at"):
        op.add_column("bridge_sessions", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    if not has_column("bridge_sessions", "last_sync_message"):
        op.add_column("bridge_sessions", sa.Column("last_sync_message", sa.String(length=240), nullable=True))
    if not has_column("sync_logs", "device_cursor_start"):
        op.add_column("sync_logs", sa.Column("device_cursor_start", sa.Integer(), nullable=True))
    if not has_column("sync_logs", "device_cursor_end"):
        op.add_column("sync_logs", sa.Column("device_cursor_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("sync_logs", "device_cursor_end")
    op.drop_column("sync_logs", "device_cursor_start")
    op.drop_column("bridge_sessions", "last_sync_message")
    op.drop_column("bridge_sessions", "last_sync_at")
    op.drop_column("bridge_sessions", "last_sync_status")
    op.drop_column("bridge_sessions", "running")
    op.drop_column("devices", "activity_cursor")
    op.drop_column("activity_records", "rtc_trusted")
