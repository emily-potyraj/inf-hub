"""add ibdb columns to workloads

Revision ID: f1g2h3i4
Revises: e2f3a4b5
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1g2h3i4'
down_revision = 'e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workloads') as batch_op:
        batch_op.add_column(sa.Column('ibdb_latest_run_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('ibdb_synced_at', sa.DateTime(), nullable=True))


def downgrade():
    pass  # never downgrade in production
