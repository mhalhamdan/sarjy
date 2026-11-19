from fastapi import APIRouter

from app.api import auth, health, memories, realtime, tools

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(realtime.router)
api_router.include_router(tools.router)
api_router.include_router(memories.router)
api_router.include_router(health.router)
