"""004_change_intelligence

Revision ID: 004
Revises: 003
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'change_intelligence_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repo_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=True),
        sa.Column('commit_sha', sa.String(), nullable=True),
        sa.Column('branch', sa.String(), default='main'),
        sa.Column('pusher', sa.String(), nullable=True),
        sa.Column('files_changed', JSON, default=[]),
        sa.Column('architectural_impact', JSON, default={}),
        sa.Column('risks', JSON, default=[]),
        sa.Column('affected_services', JSON, default=[]),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('change_intelligence_reports')
