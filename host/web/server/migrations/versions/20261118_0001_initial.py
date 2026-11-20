"""Create the VelaPet phase-two schema.

Revision ID: 20261118_0001
Revises:
"""

from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "20261118_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
