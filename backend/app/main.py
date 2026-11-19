import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.deps import Limiters
from app.services.realtime import RealtimeService
from app.services.search import SearchService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.limiters = Limiters(settings)
        app.state.realtime_service = RealtimeService(openai_client, settings)
        app.state.search_service = SearchService(
            openai_client,
            model=settings.search_model,
            reasoning_effort=settings.search_reasoning_effort,
            timeout_seconds=settings.search_timeout_seconds,
        )
        yield
        await openai_client.close()
        await engine.dispose()

    app = FastAPI(
        title="Sarjy",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    # Signed, HttpOnly cookie holding the anonymous user id.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        session_cookie=settings.cookie_name,
        max_age=settings.cookie_max_age_days * 24 * 60 * 60,
        same_site="lax",
        https_only=settings.cookie_secure,
    )

    @app.exception_handler(openai.APITimeoutError)
    async def openai_timeout(request: Request, exc: openai.APITimeoutError) -> JSONResponse:
        logger.warning("OpenAI request timed out: %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "The upstream service timed out."}, status_code=504)

    @app.exception_handler(openai.APIError)
    async def openai_error(request: Request, exc: openai.APIError) -> JSONResponse:
        logger.error("OpenAI request failed on %s: %s", request.url.path, exc)
        return JSONResponse({"detail": "The upstream service failed."}, status_code=502)

    app.include_router(api_router)

    # In the Docker image the built frontend sits next to the app and is served from "/".
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")

    return app
