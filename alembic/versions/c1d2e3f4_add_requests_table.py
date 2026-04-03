"""add requests table

Revision ID: c1d2e3f4
Revises: b1c2d3e4
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4'
down_revision: Union[str, None] = 'b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('hardware', sa.Text(), nullable=False),
        sa.Column('framework', sa.Text(), nullable=False),
        sa.Column('precision', sa.Text(), nullable=False),
        sa.Column('scenario', sa.Text(), nullable=False),
        sa.Column('seqlens', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='new'),
        sa.Column('pic', sa.Text(), nullable=True),
        sa.Column('submitted_by', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('requests')
