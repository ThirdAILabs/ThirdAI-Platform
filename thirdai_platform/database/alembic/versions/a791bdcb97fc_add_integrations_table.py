"""Add integrations table

Revision ID: a791bdcb97fc
Revises: 1d6f40f1cadc
Create Date: 2024-12-16 14:37:09.553718

"""

import enum
from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a791bdcb97fc"
down_revision: Union[str, None] = "1d6f40f1cadc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class IntegrationType(str, enum.Enum):
    openai = "openai"
    self_hosted = "self_hosted"
    anthropic = "anthropic"
    cohere = "cohere"


def upgrade():
    integration_type_enum = pg.ENUM(IntegrationType, name="integrationtype")
    integration_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "integrations",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("type", integration_type_enum, nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_table("integrations")

    integration_type_enum = pg.ENUM(IntegrationType, name="integrationtype")
    integration_type_enum.drop(op.get_bind(), checkfirst=True)
