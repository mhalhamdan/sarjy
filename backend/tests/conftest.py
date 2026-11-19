"""Tests run against a real Postgres database.

The database comes from TEST_DATABASE_URL, or else from DATABASE_URL with the database name
changed to `sarjy_test`. It is created if missing, and migrated down and up once per run.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.config import DatabaseSettings, Settings
from app.deps import get_realtime_service, get_search_service
from app.main import create_app
from app.schemas import Source, WebSearchOut
from app.services.realtime import ClientSecret

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSCODE = "correct-horse"


def _test_database_url() -> str:
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    return (
        make_url(DatabaseSettings().database_url)
        .set(database="sarjy_test")
        .render_as_string(hide_password=False)
    )


async def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    await admin.dispose()


def _migrate(url: str) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    # Down then up, so both directions of every migration are exercised.
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
async def database_url() -> str:
    url = _test_database_url()
    await _ensure_database(url)
    # Alembic's env.py calls asyncio.run, which needs a thread without a running loop.
    await asyncio.to_thread(_migrate, url)
    return url


@pytest.fixture(autouse=True)
async def _clean_tables(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    yield
    if "database_url" not in request.fixturenames:
        return
    engine = create_async_engine(request.getfixturevalue("database_url"))
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, memories RESTART IDENTITY CASCADE"))
    await engine.dispose()


@dataclass
class FakeRealtime:
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def create_client_secret(self, instructions: str, safety_id: str) -> ClientSecret:
        self.calls.append((instructions, safety_id))
        return ClientSecret(value="ek_test", expires_at=1_900_000_000)


@dataclass
class FakeSearch:
    queries: list[str] = field(default_factory=list)

    async def search(self, query: str, safety_id: str) -> WebSearchOut:
        self.queries.append(query)
        return WebSearchOut(
            answer=f"Answer for {query}.",
            sources=[Source(title="Example", url="https://example.com")],
        )


@dataclass
class Harness:
    client: httpx.AsyncClient
    realtime: FakeRealtime
    search: FakeSearch
    settings: Settings

    async def login(self) -> None:
        response = await self.client.post("/api/v1/auth/passcode", json={"passcode": PASSCODE})
        assert response.status_code == 200, response.text


HarnessFactory = Callable[..., AbstractAsyncContextManager[Harness]]


@pytest.fixture
def make_harness(database_url: str) -> HarnessFactory:
    """Build an app with fake OpenAI services; keyword arguments override settings."""

    @asynccontextmanager
    async def factory(**overrides) -> AsyncIterator[Harness]:
        defaults = {
            "openai_api_key": "sk-test",
            "access_passcode": PASSCODE,
            "session_secret": "s" * 32,
            "database_url": database_url,
            "cookie_secure": False,
            "static_dir": Path("/nonexistent"),
        }
        settings = Settings(**(defaults | overrides))
        app = create_app(settings)
        realtime, search = FakeRealtime(), FakeSearch()
        app.dependency_overrides[get_realtime_service] = lambda: realtime
        app.dependency_overrides[get_search_service] = lambda: search
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield Harness(client=client, realtime=realtime, search=search, settings=settings)

    return factory


@pytest.fixture
async def harness(make_harness: HarnessFactory) -> AsyncIterator[Harness]:
    async with make_harness() as h:
        yield h


@pytest.fixture
async def authed(harness: Harness) -> Harness:
    await harness.login()
    return harness
