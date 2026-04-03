"""add eta to requests

Revision ID: e2f3a4b5
Revises: 7786eec81f8f
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e2f3a4b5'
down_revision: Union[str, None] = '7786eec81f8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('eta', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('requests', 'eta')
