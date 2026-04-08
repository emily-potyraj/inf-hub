"""add s_record_id to workloads

Revision ID: h1i2j3k4
Revises: g1h2i3j4
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = 'h1i2j3k4'
down_revision = 'g1h2i3j4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workloads') as batch_op:
        batch_op.add_column(sa.Column('s_record_id', sa.Text(), nullable=True))


def downgrade():
    pass  # never downgrade in production
