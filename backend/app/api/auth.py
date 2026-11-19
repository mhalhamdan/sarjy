import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.deps import (
    SESSION_USER_KEY,
    AppSettings,
    DbSession,
    Limiters,
    enforce,
    get_limiters,
    load_session_user,
)
from app.models import User
from app.schemas import AuthStatus, PasscodeIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def auth_status(request: Request, db: DbSession) -> AuthStatus:
    return AuthStatus(authenticated=await load_session_user(request, db) is not None)


@router.post("/passcode")
async def enter_passcode(
    body: PasscodeIn,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    limiters: Annotated[Limiters, Depends(get_limiters)],
) -> AuthStatus:
    """Exchange the shared passcode for a signed cookie identifying an anonymous user.

    A browser that already has a valid cookie keeps its user, so its memories are preserved.
    """
    client_ip = request.client.host if request.client else "unknown"
    enforce(limiters.passcode, client_ip, "Too many attempts. Try again in 15 minutes.")

    expected = settings.access_passcode.get_secret_value().encode()
    if not hmac.compare_digest(body.passcode.encode(), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong passcode.")
    limiters.passcode.reset(client_ip)

    if await load_session_user(request, db) is None:
        user = User()
        db.add(user)
        await db.commit()
        request.session[SESSION_USER_KEY] = str(user.id)
    return AuthStatus(authenticated=True)
