from fastapi import APIRouter
from .chat import router as chat_router
from .github import router as github_router
from .system import router as system_router
from .conversations import router as conversations_router
from .test import router as test_router

api_router = APIRouter()

api_router.include_router(chat_router)
api_router.include_router(github_router)
api_router.include_router(system_router)
api_router.include_router(conversations_router)
api_router.include_router(test_router)
