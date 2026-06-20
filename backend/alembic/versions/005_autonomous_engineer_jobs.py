"""005_autonomous_engineer_jobs

Revision ID: 005
Revises: 004
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'autonomous_engineer_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('repo_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=False),
        sa.Column('repo_full_name', sa.String(), nullable=False),
        sa.Column('issue_number', sa.Integer(), nullable=False),
        sa.Column('issue_title', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='queued'),
        sa.Column('branch_name', sa.String(), nullable=True),
        sa.Column('pr_url', sa.String(), nullable=True),
        sa.Column('pr_number', sa.Integer(), nullable=True),
        sa.Column('files_changed', JSON, server_default='[]'),
        sa.Column('step_log', JSON, server_default='[]'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_ae_jobs_user_id', 'autonomous_engineer_jobs', ['user_id'])
    op.create_index('idx_ae_jobs_repo_id', 'autonomous_engineer_jobs', ['repo_id'])


def downgrade():
    op.drop_index('idx_ae_jobs_repo_id')
    op.drop_index('idx_ae_jobs_user_id')
    op.drop_table('autonomous_engineer_jobs')
