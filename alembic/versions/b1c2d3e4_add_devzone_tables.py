"""add devzone tables

Revision ID: b1c2d3e4
Revises: a2c3d4e5
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4'
down_revision: Union[str, None] = 'a2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'devzone_scenes',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('seqlen', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('created_by_email', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_published', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'devzone_curves',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('scene_id', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('hardware', sa.Text(), nullable=False),
        sa.Column('framework', sa.Text(), nullable=True),
        sa.Column('precision', sa.Text(), nullable=True),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('ibdb_source', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('points', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['devzone_scenes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('devzone_curves')
    op.drop_table('devzone_scenes')
