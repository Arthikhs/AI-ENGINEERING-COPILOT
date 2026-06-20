"""enterprise features: sandbox, governance, health score, reports, eval, observability

Revision ID: 007
Revises: 006_fix_numeric_columns
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '007'
down_revision = '006_fix_numeric_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Sandbox executions
    op.create_table('sandbox_executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), nullable=True),
        sa.Column('language', sa.String(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('stdout', sa.Text(), nullable=True),
        sa.Column('stderr', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), default=0),
        sa.Column('memory_used_mb', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Architecture governance rules
    op.create_table('governance_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), default='medium'),
        sa.Column('config', JSONB, default={}),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Governance violations
    op.create_table('governance_violations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repo_id', UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', UUID(as_uuid=True), nullable=True),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), default='medium'),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Repository health scores
    op.create_table('repo_health_scores',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repo_id', UUID(as_uuid=True), nullable=False),
        sa.Column('overall_score', sa.Float(), default=0.0),
        sa.Column('security_score', sa.Float(), default=0.0),
        sa.Column('architecture_score', sa.Float(), default=0.0),
        sa.Column('test_coverage_score', sa.Float(), default=0.0),
        sa.Column('code_quality_score', sa.Float(), default=0.0),
        sa.Column('dependency_score', sa.Float(), default=0.0),
        sa.Column('documentation_score', sa.Float(), default=0.0),
        sa.Column('details', JSONB, default={}),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Engineering reports
    op.create_table('engineering_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('content', JSONB, default={}),
        sa.Column('pdf_path', sa.String(), nullable=True),
        sa.Column('delivered_to', JSONB, default=[]),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # LLM evaluation results
    op.create_table('llm_evaluations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('benchmark_run_id', UUID(as_uuid=True), nullable=True),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('faithfulness', sa.Float(), nullable=True),
        sa.Column('relevance', sa.Float(), nullable=True),
        sa.Column('hallucination_score', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), default=0),
        sa.Column('cost_usd', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Feature flags
    op.create_table('feature_flags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), unique=True, nullable=False),
        sa.Column('is_enabled', sa.Boolean(), default=False),
        sa.Column('rollout_percentage', sa.Integer(), default=100),
        sa.Column('config', JSONB, default={}),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('feature_flags')
    op.drop_table('llm_evaluations')
    op.drop_table('engineering_reports')
    op.drop_table('repo_health_scores')
    op.drop_table('governance_violations')
    op.drop_table('governance_rules')
    op.drop_table('sandbox_executions')
