"""add_sentinel_columns

Revision ID: 68b4a8ce5e1d
Revises: b1c2d3e4
Create Date: 2026-03-27 10:26:22.615850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68b4a8ce5e1d'
down_revision: Union[str, None] = 'b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sentinel columns on workloads
    op.add_column('workloads', sa.Column('amd_tps_source', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('amd_tps_sentinel_value', sa.Float(), nullable=True))
    op.add_column('workloads', sa.Column('amd_tps_synced_at', sa.DateTime(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_threat_level', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_summary', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_image_url', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_synced_at', sa.DateTime(), nullable=True))
    # Workload linkage on devzone_curves
    op.add_column('devzone_curves', sa.Column('inf_hub_workload_id', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('devzone_curves', 'inf_hub_workload_id')
    op.drop_column('workloads', 'sentinel_synced_at')
    op.drop_column('workloads', 'sentinel_image_url')
    op.drop_column('workloads', 'sentinel_summary')
    op.drop_column('workloads', 'sentinel_threat_level')
    op.drop_column('workloads', 'amd_tps_synced_at')
    op.drop_column('workloads', 'amd_tps_sentinel_value')
    op.drop_column('workloads', 'amd_tps_source')
