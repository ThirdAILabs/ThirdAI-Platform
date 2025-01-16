"""add cache status column

Revision ID: e2010b91a422
Revises: a791bdcb97fc
Create Date: 2025-01-14 20:54:09.974686

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2010b91a422"
down_revision: Union[str, None] = "a791bdcb97fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column(
            "cache_refresh_status",
            postgresql.ENUM(
                "not_started",
                "starting",
                "in_progress",
                "stopped",
                "complete",
                "failed",
                name="status",
            ),
            nullable=False,
            server_default=sa.text("'not_started'::status"),
        ),
    )


def downgrade() -> None:
    op.drop_column("models", "cache_refresh_status")
