from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict):
    # Input
    question: str
    repo_id: str
    user_id: str

    # Routing (simple orchestrator)
    intent: str

    # Multi-agent pipeline fields
    plan: List[str]
    agent_outputs: Dict[str, Any]
    retriever_chunks: List[dict]

    # Legacy / shared fields
    retrieved_chunks: List[dict]
    context: str
    answer: str
    sources: List[dict]
    agent_type: str
    token_usage: dict
    memory: List[dict]
    error: Optional[str]

    # Model Router telemetry (populated per agent invocation)
    model_used: str
    latency_ms: int
    estimated_cost_usd: float
