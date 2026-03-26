"""add breadth_studies and work_type

Revision ID: a2c3d4e5
Revises: 8b1180f2386c
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c3d4e5'
down_revision: Union[str, None] = '8b1180f2386c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'breadth_studies',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('created_by_email', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('workloads', sa.Column('work_type', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('study_id', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('workloads', 'study_id')
    op.drop_column('workloads', 'work_type')
    op.drop_table('breadth_studies')
