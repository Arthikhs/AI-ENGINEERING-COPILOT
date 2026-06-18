"""
LLM Router — Vendor-independent model selection.
Supports: OpenAI, Anthropic (Claude), Google Gemini, Ollama (local), vLLM (local).

Usage:
    from llm_router import get_llm, get_available_models
    llm = get_llm()                          # uses settings default
    llm = get_llm("claude-3-5-sonnet")       # specific model
    llm = get_llm("llama3", provider="ollama") # local Ollama
"""
from typing import Optional
from langchain_core.language_models import BaseChatModel
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Model catalogue ─────────────────────────────────────────────────────────────
MODELS = {
    # OpenAI
    "gpt-4o":            {"provider": "openai",    "label": "GPT-4o",              "context": 128000},
    "gpt-4o-mini":       {"provider": "openai",    "label": "GPT-4o Mini",         "context": 128000},
    "gpt-4-turbo":       {"provider": "openai",    "label": "GPT-4 Turbo",         "context": 128000},
    # Anthropic
    "claude-3-5-sonnet": {"provider": "anthropic", "label": "Claude 3.5 Sonnet",   "context": 200000},
    "claude-3-haiku":    {"provider": "anthropic", "label": "Claude 3 Haiku",      "context": 200000},
    "claude-3-opus":     {"provider": "anthropic", "label": "Claude 3 Opus",       "context": 200000},
    # Google
    "gemini-1.5-pro":    {"provider": "google",    "label": "Gemini 1.5 Pro",      "context": 1000000},
    "gemini-1.5-flash":  {"provider": "google",    "label": "Gemini 1.5 Flash",    "context": 1000000},
    # Ollama (local)
    "llama3":            {"provider": "ollama",    "label": "Llama 3 (Local)",     "context": 8192},
    "llama3.1":          {"provider": "ollama",    "label": "Llama 3.1 (Local)",   "context": 128000},
    "codellama":         {"provider": "ollama",    "label": "CodeLlama (Local)",   "context": 16384},
    "mistral":           {"provider": "ollama",    "label": "Mistral (Local)",     "context": 32768},
    "deepseek-coder":    {"provider": "ollama",    "label": "DeepSeek Coder",      "context": 16384},
    # vLLM (OpenAI-compatible local)
    "vllm":              {"provider": "vllm",      "label": "vLLM (Local)",        "context": 32768},
}


def get_llm(
    model: Optional[str] = None,
    provider: Optional[str] = None,
    temperature: float = 0,
) -> BaseChatModel:
    """
    Return the correct LangChain LLM for the given model/provider.
    Falls back to settings.llm_model if not specified.
    """
    model = model or settings.llm_model
    meta = MODELS.get(model, {})
    provider = provider or meta.get("provider") or _infer_provider(model)

    logger.debug(f"LLM Router: model={model} provider={provider}")

    if provider == "openai":
        return _openai(model, temperature)
    elif provider == "anthropic":
        return _anthropic(model, temperature)
    elif provider == "google":
        return _google(model, temperature)
    elif provider == "ollama":
        return _ollama(model, temperature)
    elif provider == "vllm":
        return _vllm(model, temperature)
    else:
        logger.warning(f"Unknown provider '{provider}', falling back to OpenAI")
        return _openai(settings.llm_model, temperature)


def get_available_models() -> list:
    """Return list of all supported models with metadata."""
    available = []
    for model_id, meta in MODELS.items():
        entry = {
            "id": model_id,
            "label": meta["label"],
            "provider": meta["provider"],
            "context_window": meta["context"],
            "available": _check_available(meta["provider"]),
        }
        available.append(entry)
    return available


def _check_available(provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(getattr(settings, "anthropic_api_key", ""))
    if provider == "google":
        return bool(getattr(settings, "google_api_key", ""))
    if provider in ("ollama", "vllm"):
        return True  # always show local models
    return False


def _infer_provider(model: str) -> str:
    if model.startswith("gpt") or model.startswith("o1"):
        return "openai"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "google"
    return "openai"


def _openai(model: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )


def _anthropic(model: str, temperature: float) -> BaseChatModel:
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=getattr(settings, "anthropic_api_key", ""),
            temperature=temperature,
            max_tokens=4096,
        )
    except ImportError:
        raise ImportError("Run: pip install langchain-anthropic")


def _google(model: str, temperature: float) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=getattr(settings, "google_api_key", ""),
            temperature=temperature,
        )
    except ImportError:
        raise ImportError("Run: pip install langchain-google-genai")


def _ollama(model: str, temperature: float) -> BaseChatModel:
    try:
        from langchain_ollama import ChatOllama
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=temperature)
    except ImportError:
        # Fallback to community package
        from langchain_community.chat_models import ChatOllama as CommOllama
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        return CommOllama(model=model, base_url=base_url, temperature=temperature)


def _vllm(model: str, temperature: float) -> BaseChatModel:
    """vLLM exposes an OpenAI-compatible API."""
    from langchain_openai import ChatOpenAI
    base_url = getattr(settings, "vllm_base_url", "http://localhost:8001/v1")
    return ChatOpenAI(
        model=model,
        openai_api_key="vllm",          # vLLM doesn't check the key
        openai_api_base=base_url,
        temperature=temperature,
    )
