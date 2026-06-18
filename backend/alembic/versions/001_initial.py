"""initial schema with pgvector

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("github_id", sa.String(), unique=True, nullable=True),
        sa.Column("username", sa.String(), unique=True, nullable=False),
        sa.Column("email", sa.String(), unique=True, nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("github_access_token", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # repositories
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("github_repo_id", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(), server_default="main"),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("clone_url", sa.String(), nullable=False),
        sa.Column("is_private", sa.Boolean(), server_default="false"),
        sa.Column("is_indexed", sa.Boolean(), server_default="false"),
        sa.Column("total_files", sa.Integer(), server_default="0"),
        sa.Column("total_chunks", sa.Integer(), server_default="0"),
        sa.Column("last_commit", sa.String(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # repository_syncs
    op.create_table(
        "repository_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("branch", sa.String(), server_default="main"),
        sa.Column("commit_sha", sa.String(), nullable=True),
        sa.Column("files_processed", sa.Integer(), server_default="0"),
        sa.Column("chunks_created", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # files
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), server_default="0"),
        sa.Column("commit_sha", sa.String(), nullable=True),
        sa.Column("is_indexed", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # chunks
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_type", sa.String(), nullable=True),
        sa.Column("chunk_name", sa.String(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # embeddings (pgvector)
    op.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            repo_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(1536),
            language TEXT,
            chunk_type TEXT,
            chunk_name TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx
        ON embeddings USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS embeddings_repo_idx ON embeddings(repo_id)")

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_type", sa.String(), nullable=True),
        sa.Column("sources", postgresql.JSON(), server_default="[]"),
        sa.Column("token_usage", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # pr_reviews
    op.create_table(
        "pr_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_title", sa.String(), nullable=True),
        sa.Column("base_branch", sa.String(), nullable=False),
        sa.Column("head_branch", sa.String(), nullable=False),
        sa.Column("findings", postgresql.JSON(), server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(), server_default="low"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # architecture_reports
    op.create_table(
        "architecture_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("service_count", sa.Integer(), server_default="0"),
        sa.Column("api_count", sa.Integer(), server_default="0"),
        sa.Column("dependency_graph", postgresql.JSON(), server_default="{}"),
        sa.Column("circular_dependencies", postgresql.JSON(), server_default="[]"),
        sa.Column("layers", postgresql.JSON(), server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("architecture_reports")
    op.drop_table("pr_reviews")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP TABLE IF EXISTS embeddings")
    op.drop_table("chunks")
    op.drop_table("files")
    op.drop_table("repository_syncs")
    op.drop_table("repositories")
    op.drop_table("users")
