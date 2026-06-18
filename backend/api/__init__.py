from api.github_auth import router as auth_router
from api.repositories import router as repos_router
from api.chat import router as chat_router
from api.pr_review import router as pr_router
from api.architecture import router as arch_router

__all__ = ["auth_router", "repos_router", "chat_router", "pr_router", "arch_router"]
