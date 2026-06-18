"""003_new_features

Revision ID: 003
Revises: 002
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hitl_approvals',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('repo_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=True),
        sa.Column('repo_full_name', sa.String(), nullable=True),
        sa.Column('pr_number', sa.Integer(), nullable=True),
        sa.Column('findings', JSON, default=[]),
        sa.Column('overall_risk', sa.String(), default='low'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('comment_posted', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), default=0),
        sa.Column('input_tokens', sa.Integer(), default=0),
        sa.Column('output_tokens', sa.Integer(), default=0),
        sa.Column('estimated_cost_usd', sa.String(), default='0'),
        sa.Column('quality_score', sa.String(), default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'prompt_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active_version', sa.Integer(), default=1),
        sa.Column('ab_group', sa.String(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'prompt_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('prompt_templates.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'benchmark_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('version_label', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('test_cases', JSON, default=[]),
        sa.Column('results', JSON, default=[]),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('accuracy', sa.String(), nullable=True),
        sa.Column('avg_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.String(), nullable=True),
        sa.Column('hallucination_rate', sa.String(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('benchmark_runs')
    op.drop_table('prompt_versions')
    op.drop_table('prompt_templates')
    op.drop_table('agent_runs')
    op.drop_table('hitl_approvals')
