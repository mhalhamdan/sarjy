import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import User
from app.rate_limit import RateLimiter
from app.services.realtime import RealtimeService
from app.services.search import SearchService

SESSION_USER_KEY = "user_id"


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def load_session_user(request: Request, db: AsyncSession) -> User | None:
    """The user named by the signed session cookie, if it names one that still exists."""
    try:
        user_id = uuid.UUID(request.session[SESSION_USER_KEY])
    except (KeyError, ValueError, TypeError):
        return None
    return await db.get(User, user_id)


async def get_current_user(request: Request, db: DbSession) -> User:
    """The user identified by the signed session cookie; 401 when absent or unknown."""
    user = await load_session_user(request, db)
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Enter the passcode to continue.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def safety_id(user: User) -> str:
    """A stable, non-reversible user id for OpenAI's abuse monitoring."""
    return hashlib.sha256(str(user.id).encode()).hexdigest()


def get_realtime_service(request: Request) -> RealtimeService:
    return request.app.state.realtime_service


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search_service


class Limiters:
    def __init__(self, settings: Settings) -> None:
        self.passcode = RateLimiter(settings.passcode_attempts_per_15_min, 15 * 60)
        self.sessions = RateLimiter(settings.sessions_per_user_per_day, 24 * 60 * 60)
        self.searches = RateLimiter(settings.searches_per_user_per_minute, 60)


def get_limiters(request: Request) -> Limiters:
    return request.app.state.limiters


def enforce(limiter: RateLimiter, key: str, message: str) -> None:
    if not limiter.hit(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
