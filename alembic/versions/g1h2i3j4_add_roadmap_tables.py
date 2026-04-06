"""add benchmark_versions and benchmark_submissions tables

Revision ID: g1h2i3j4
Revises: f3a4b5c6
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g1h2i3j4'
down_revision: Union[str, None] = 'f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'benchmark_versions',
        sa.Column('benchmark_version', sa.Text(), nullable=False),
        sa.Column('benchmark_group', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=True),
        sa.Column('submission_date', sa.Text(), nullable=True),
        sa.Column('publication_date', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('benchmark_version'),
    )
    op.create_table(
        'benchmark_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('benchmark_version', sa.Text(), nullable=False),
        sa.Column('chip', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('seqlen', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['benchmark_version'], ['benchmark_versions.benchmark_version']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('benchmark_version', 'chip', 'model', 'seqlen', name='uq_submission'),
    )


def downgrade() -> None:
    op.drop_table('benchmark_submissions')
    op.drop_table('benchmark_versions')
