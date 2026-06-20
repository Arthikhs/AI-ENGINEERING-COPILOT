import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from database import Base


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OrgRole(str, enum.Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


# ─── Multi-Tenant SaaS Models ─────────────────────────────────────────────────

class Organization(Base):
    """Top-level tenant. All repos, conversations, KG are org-scoped."""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)  # url-safe name
    description = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)
    settings = Column(JSON, default={})               # org-level config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    repositories = relationship("Repository", back_populates="organization")


class OrganizationMember(Base):
    """Membership + role for a user in an organization."""
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(SAEnum(OrgRole), default=OrgRole.DEVELOPER, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="org_memberships")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id = Column(String, unique=True, nullable=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    avatar_url = Column(String, nullable=True)
    github_access_token = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    repositories = relationship("Repository", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")
    org_memberships = relationship("OrganizationMember", back_populates="user")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)  # org-scoped
    github_repo_id = Column(String, nullable=True)
    full_name = Column(String, nullable=False)  # owner/repo
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    default_branch = Column(String, default="main")
    language = Column(String, nullable=True)
    clone_url = Column(String, nullable=False)
    is_private = Column(Boolean, default=False)
    is_indexed = Column(Boolean, default=False)
    total_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    last_commit = Column(String, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="repositories")
    organization = relationship("Organization", back_populates="repositories")
    files = relationship("CodeFile", back_populates="repository", cascade="all, delete-orphan")
    syncs = relationship("RepositorySync", back_populates="repository", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="repository")


class RepositorySync(Base):
    __tablename__ = "repository_syncs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    status = Column(SAEnum(SyncStatus), default=SyncStatus.PENDING)
    branch = Column(String, default="main")
    commit_sha = Column(String, nullable=True)
    files_processed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="syncs")


class CodeFile(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    file_path = Column(String, nullable=False)
    language = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    commit_sha = Column(String, nullable=True)
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")


class CodeChunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    file_path = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    chunk_type = Column(String, nullable=True)  # function, class, module, etc.
    chunk_name = Column(String, nullable=True)  # function/class name
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    language = Column(String, nullable=True)
    extra_metadata = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("CodeFile", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    repository = relationship("Repository", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    agent_type = Column(String, nullable=True)  # qa, pr_review, architecture
    sources = Column(JSON, default=[])  # retrieved code chunks used
    token_usage = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String, nullable=True)
    base_branch = Column(String, nullable=False)
    head_branch = Column(String, nullable=False)
    findings = Column(JSON, default=[])
    summary = Column(Text, nullable=True)
    risk_level = Column(String, default="low")  # low, medium, high
    created_at = Column(DateTime, default=datetime.utcnow)


class ArchitectureReport(Base):
    __tablename__ = "architecture_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    service_count = Column(Integer, default=0)
    api_count = Column(Integer, default=0)
    dependency_graph = Column(JSON, default={})
    circular_dependencies = Column(JSON, default=[])
    layers = Column(JSON, default={})
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── HITL Approval Model ─────────────────────────────────────────────────────

class HITLApproval(Base):
    """
    Tracks human-in-the-loop approval requests from the security HITL workflow.
    """
    __tablename__ = "hitl_approvals"

    id = Column(String, primary_key=True)           # UUID string
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    repo_full_name = Column(String, nullable=True)  # owner/repo for GitHub API
    pr_number = Column(Integer, nullable=True)
    findings = Column(JSON, default=[])             # high/critical findings
    overall_risk = Column(String, default="low")
    summary = Column(Text, nullable=True)
    status = Column(String, default="pending")      # pending | approved | rejected
    comment_posted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Agent Run Model (Model Router telemetry) ─────────────────────────────────

class AgentRun(Base):
    """
    Records every LLM invocation made through the model router.
    Used for cost analytics, latency tracking, and benchmark comparison.
    """
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    task_type = Column(String, nullable=False)       # simple_qa | security_review | etc.
    model = Column(String, nullable=False)           # gpt-4o-mini | claude-3-5-sonnet | etc.
    provider = Column(String, nullable=True)         # openai | anthropic | ollama
    latency_ms = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Prompt Management Models ─────────────────────────────────────────────────

class PromptTemplate(Base):
    """A named, versioned prompt template for a specific agent type."""
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    agent_type = Column(String, nullable=False)    # security | architecture | etc.
    description = Column(Text, nullable=True)
    active_version = Column(Integer, default=1)
    ab_group = Column(String, nullable=True)       # "A" | "B" for A/B testing
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    versions = relationship("PromptVersion", back_populates="template", cascade="all, delete-orphan")


class PromptVersion(Base):
    """A single version of a prompt template's content."""
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"), nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("PromptTemplate", back_populates="versions")


# ─── Benchmark Run Model ───────────────────────────────────────────────────────

class BenchmarkRun(Base):
    """Stores agent benchmark test runs and their aggregate metrics."""
    __tablename__ = "benchmark_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type = Column(String, nullable=False)
    version_label = Column(String, nullable=False)  # e.g. "security-v2"
    model = Column(String, nullable=False)
    test_cases = Column(JSON, default=[])
    results = Column(JSON, default=[])
    status = Column(String, default="pending")       # pending | running | completed
    accuracy = Column(Float, nullable=True)
    avg_latency_ms = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Knowledge Graph Models ───────────────────────────────────────────────────

class ChangeIntelligenceReport(Base):
    """
    Stores the AI-generated impact report for each GitHub push event.
    """
    __tablename__ = "change_intelligence_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    commit_sha = Column(String, nullable=True)
    branch = Column(String, default="main")
    pusher = Column(String, nullable=True)
    files_changed = Column(JSON, default=[])
    architectural_impact = Column(JSON, default={})
    risks = Column(JSON, default=[])
    affected_services = Column(JSON, default=[])
    recommendation = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Autonomous Engineer Job Model ───────────────────────────────────────────

class AutonomousEngineerJob(Base):
    """
    Persists the state of an Autonomous Engineer pipeline run.
    Replaces the in-memory _jobs dict so jobs survive server restarts.
    """
    __tablename__ = "autonomous_engineer_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    repo_full_name = Column(String, nullable=False)
    issue_number = Column(Integer, nullable=False)
    issue_title = Column(String, nullable=True)
    status = Column(String, default="queued")          # queued | running | completed | failed
    branch_name = Column(String, nullable=True)
    pr_url = Column(String, nullable=True)
    pr_number = Column(Integer, nullable=True)
    files_changed = Column(JSON, default=[])
    step_log = Column(JSON, default=[])
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    repository = relationship("Repository")


# ─── Knowledge Graph Models ───────────────────────────────────────────────────

class KnowledgeNode(Base):
    """
    A node in the multi-repo knowledge graph.
    Represents a service, module, class, or shared library.
    """
    __tablename__ = "knowledge_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    repo_full_name = Column(String, nullable=False)     # owner/repo for cross-repo display
    node_type = Column(String, nullable=False)          # service | module | class | library
    name = Column(String, nullable=False)               # e.g. "UserService", "auth"
    file_path = Column(String, nullable=True)           # source file
    language = Column(String, nullable=True)
    extra_metadata = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    outgoing_edges = relationship("KnowledgeEdge", foreign_keys="KnowledgeEdge.source_node_id",
                                  back_populates="source", cascade="all, delete-orphan")
    incoming_edges = relationship("KnowledgeEdge", foreign_keys="KnowledgeEdge.target_node_id",
                                  back_populates="target", cascade="all, delete-orphan")


class KnowledgeEdge(Base):
    """
    A directed edge between two knowledge nodes.
    Represents import, call, inheritance, or API dependency.
    """
    __tablename__ = "knowledge_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=False)
    edge_type = Column(String, nullable=False)          # imports | calls | inherits | uses_api
    weight = Column(Integer, default=1)                 # number of occurrences
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("KnowledgeNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target = relationship("KnowledgeNode", foreign_keys=[target_node_id], back_populates="incoming_edges")
