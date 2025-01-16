"""Add integrations table

Revision ID: a791bdcb97fc
Revises: 1d6f40f1cadc
Create Date: 2024-12-16 14:37:09.553718

"""

pass
from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a791bdcb97fc"
down_revision: Union[str, None] = "1d6f40f1cadc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "integrations",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "type",
            pg.ENUM(
                "openai", "self_hosted", "anthropic", "cohere", name="integrationtype"
            ),
            nullable=False,
        ),
        sa.Column("data", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_table("integrations")
