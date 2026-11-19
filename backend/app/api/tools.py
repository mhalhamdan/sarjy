"""Tool endpoints. The voice model's tool calls arrive in the browser, which relays them here.

Each endpoint is authenticated by the session cookie and only touches the caller's own data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import (
    CurrentUser,
    DbSession,
    Limiters,
    enforce,
    get_limiters,
    get_search_service,
    safety_id,
)
from app.schemas import (
    ForgetIn,
    ForgetOut,
    MemoryOut,
    RememberIn,
    RememberOut,
    WebSearchIn,
    WebSearchOut,
)
from app.services import memory as memory_service
from app.services.search import SearchService

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/remember")
async def remember(body: RememberIn, user: CurrentUser, db: DbSession) -> RememberOut:
    try:
        result, memory = await memory_service.remember(db, user.id, body.content, body.replaces_id)
    except memory_service.MemoryNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No remembered fact with id {body.replaces_id}."
        ) from None
    return RememberOut(status=result, memory=MemoryOut.model_validate(memory))


@router.post("/forget")
async def forget(body: ForgetIn, user: CurrentUser, db: DbSession) -> ForgetOut:
    deleted = await memory_service.forget(db, user.id, body.memory_id)
    return ForgetOut(status="forgotten" if deleted else "not_found")


@router.post("/web_search")
async def web_search(
    body: WebSearchIn,
    user: CurrentUser,
    limiters: Annotated[Limiters, Depends(get_limiters)],
    search: Annotated[SearchService, Depends(get_search_service)],
) -> WebSearchOut:
    enforce(limiters.searches, str(user.id), "Too many searches. Wait a minute and try again.")
    return await search.search(body.query, safety_id(user))
