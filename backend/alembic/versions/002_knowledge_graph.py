"""add knowledge graph tables

Revision ID: 002_knowledge_graph
Revises: 001_initial
Create Date: 2024-01-02 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_knowledge_graph"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repo_full_name", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )
    op.create_index("knowledge_nodes_repo_idx", "knowledge_nodes", ["repo_id"])
    op.create_index("knowledge_nodes_name_idx", "knowledge_nodes", ["name"])

    op.create_table(
        "knowledge_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.String(), nullable=False),
        sa.Column("weight", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )
    op.create_index("knowledge_edges_source_idx", "knowledge_edges", ["source_node_id"])
    op.create_index("knowledge_edges_target_idx", "knowledge_edges", ["target_node_id"])


def downgrade() -> None:
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
