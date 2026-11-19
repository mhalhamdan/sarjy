from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    Limiters,
    enforce,
    get_limiters,
    get_realtime_service,
    safety_id,
)
from app.schemas import RealtimeSessionOut
from app.services import memory as memory_service
from app.services.prompts import build_instructions
from app.services.realtime import RealtimeService

router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.post("/session")
async def create_session(
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    limiters: Annotated[Limiters, Depends(get_limiters)],
    realtime: Annotated[RealtimeService, Depends(get_realtime_service)],
) -> RealtimeSessionOut:
    """Mint a short-lived key for one voice call, with this user's memories in its instructions."""
    enforce(limiters.sessions, str(user.id), "Daily call limit reached. Try again tomorrow.")

    limit = settings.memory_prompt_limit
    memories = await memory_service.list_memories(db, user.id, limit + 1)
    instructions = build_instructions(memories[:limit], truncated=len(memories) > limit)

    secret = await realtime.create_client_secret(instructions, safety_id(user))
    return RealtimeSessionOut(
        client_secret=secret.value, expires_at=secret.expires_at, model=settings.realtime_model
    )
