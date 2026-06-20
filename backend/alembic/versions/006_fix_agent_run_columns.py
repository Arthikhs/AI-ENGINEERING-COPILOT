"""006_fix_agent_run_columns

Revision ID: 006
Revises: 005
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_runs table with correct column types
    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), server_default='0'),
        sa.Column('input_tokens', sa.Integer(), server_default='0'),
        sa.Column('output_tokens', sa.Integer(), server_default='0'),
        sa.Column('estimated_cost_usd', sa.Float(), server_default='0'),
        sa.Column('quality_score', sa.Float(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_agent_runs_user_id', 'agent_runs', ['user_id'])
    op.create_index('idx_agent_runs_model', 'agent_runs', ['model'])
    op.create_index('idx_agent_runs_task_type', 'agent_runs', ['task_type'])
    op.create_index('idx_agent_runs_created_at', 'agent_runs', ['created_at'])


def downgrade():
    op.drop_index('idx_agent_runs_created_at')
    op.drop_index('idx_agent_runs_task_type')
    op.drop_index('idx_agent_runs_model')
    op.drop_index('idx_agent_runs_user_id')
    op.drop_table('agent_runs')
