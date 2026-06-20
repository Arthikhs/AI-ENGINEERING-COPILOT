"""007_fix_numeric_columns

Revision ID: 007
Revises: 006
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Fix agent_runs: estimated_cost_usd and quality_score were String, change to Float
    op.alter_column('agent_runs', 'estimated_cost_usd',
                    existing_type=sa.String(),
                    type_=sa.Float(),
                    existing_nullable=True,
                    postgresql_using='estimated_cost_usd::double precision')
    op.alter_column('agent_runs', 'quality_score',
                    existing_type=sa.String(),
                    type_=sa.Float(),
                    existing_nullable=True,
                    postgresql_using='quality_score::double precision')

    # Add missing input_tokens / output_tokens columns if not present
    # (migration 003 included them, but add gracefully)
    try:
        op.add_column('agent_runs', sa.Column('input_tokens', sa.Integer(), server_default='0'))
    except Exception:
        pass
    try:
        op.add_column('agent_runs', sa.Column('output_tokens', sa.Integer(), server_default='0'))
    except Exception:
        pass

    # Add indexes for faster dashboard queries
    try:
        op.create_index('idx_agent_runs_model', 'agent_runs', ['model'])
    except Exception:
        pass
    try:
        op.create_index('idx_agent_runs_task_type', 'agent_runs', ['task_type'])
    except Exception:
        pass
    try:
        op.create_index('idx_agent_runs_created_at', 'agent_runs', ['created_at'])
    except Exception:
        pass

    # Fix benchmark_runs: accuracy, total_cost_usd, hallucination_rate were String
    op.alter_column('benchmark_runs', 'accuracy',
                    existing_type=sa.String(),
                    type_=sa.Float(),
                    existing_nullable=True,
                    postgresql_using='accuracy::double precision')
    op.alter_column('benchmark_runs', 'total_cost_usd',
                    existing_type=sa.String(),
                    type_=sa.Float(),
                    existing_nullable=True,
                    postgresql_using='total_cost_usd::double precision')
    op.alter_column('benchmark_runs', 'hallucination_rate',
                    existing_type=sa.String(),
                    type_=sa.Float(),
                    existing_nullable=True,
                    postgresql_using='hallucination_rate::double precision')


def downgrade():
    op.alter_column('benchmark_runs', 'hallucination_rate',
                    existing_type=sa.Float(), type_=sa.String(), existing_nullable=True)
    op.alter_column('benchmark_runs', 'total_cost_usd',
                    existing_type=sa.Float(), type_=sa.String(), existing_nullable=True)
    op.alter_column('benchmark_runs', 'accuracy',
                    existing_type=sa.Float(), type_=sa.String(), existing_nullable=True)
    op.alter_column('agent_runs', 'quality_score',
                    existing_type=sa.Float(), type_=sa.String(), existing_nullable=True)
    op.alter_column('agent_runs', 'estimated_cost_usd',
                    existing_type=sa.Float(), type_=sa.String(), existing_nullable=True)
