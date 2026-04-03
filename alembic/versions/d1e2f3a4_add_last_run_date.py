"""add last_run_date to workloads

Revision ID: d1e2f3a4
Revises: c1d2e3f4
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4'
down_revision: Union[str, None] = 'c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workloads', sa.Column('last_run_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('workloads', 'last_run_date')
