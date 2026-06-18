from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "AI Engineering Copilot"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "change-me"

    # Database
    database_url: str
    sync_database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536
    llm_model: str = "gpt-4o"
    llm_provider: str = "openai"   # openai | anthropic | google | ollama | vllm

    # Anthropic (Claude)
    anthropic_api_key: str = ""

    # Google (Gemini)
    google_api_key: str = ""

    # Ollama (local)
    ollama_base_url: str = "http://localhost:11434"

    # vLLM (local OpenAI-compatible)
    vllm_base_url: str = "http://localhost:8001/v1"

    # GitHub
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    github_token: str = ""
    github_webhook_secret: str = ""

    # JWT
    jwt_secret_key: str = "jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "ai-engineering-copilot"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # Slack Integration
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = "#engineering"

    # Microsoft Teams Integration
    teams_webhook_url: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
