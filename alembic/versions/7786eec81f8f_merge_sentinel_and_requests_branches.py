"""merge sentinel and requests branches

Revision ID: 7786eec81f8f
Revises: 68b4a8ce5e1d, d1e2f3a4
Create Date: 2026-04-03 14:03:15.560997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7786eec81f8f'
down_revision: Union[str, None] = ('68b4a8ce5e1d', 'd1e2f3a4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
