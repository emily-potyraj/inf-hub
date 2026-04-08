"""add s_study_id to workloads

Revision ID: i1j2k3l4
Revises: h1i2j3k4
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = 'i1j2k3l4'
down_revision = 'h1i2j3k4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workloads') as batch_op:
        batch_op.add_column(sa.Column('s_study_id', sa.Text(), nullable=True))


def downgrade():
    pass  # never downgrade in production
