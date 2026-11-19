"""Service tests against a mocked OpenAI transport, checking real request and response shapes."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.rate_limit import RateLimiter
from app.services.realtime import RealtimeService, build_session_config
from app.services.search import SearchService, clean_for_speech

Handler = Callable[[httpx2.Request], httpx2.Response]


def openai_client(handler: Handler) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="sk-test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        access_passcode="x",
        session_secret="s" * 32,
        database_url="postgresql+asyncpg://unused/unused",
        static_dir=Path("/nonexistent"),
    )


async def test_realtime_service_requests_a_client_secret(settings: Settings) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(
            200, json={"value": "ek_abc", "expires_at": 1_900_000_000, "session": {}}
        )

    service = RealtimeService(openai_client(handler), settings)
    secret = await service.create_client_secret("Be helpful.", "hashed-id")

    assert (secret.value, secret.expires_at) == ("ek_abc", 1_900_000_000)
    request = captured[0]
    assert request.url.path == "/v1/realtime/client_secrets"
    assert request.headers["OpenAI-Safety-Identifier"] == "hashed-id"
    body = json.loads(request.content)
    assert body["expires_after"] == {"anchor": "created_at", "seconds": 120}
    session = body["session"]
    assert session["type"] == "realtime"
    assert session["model"] == settings.realtime_model
    assert session["instructions"] == "Be helpful."
    assert session["audio"]["input"]["transcription"] == {"model": settings.transcription_model}
    assert {tool["name"] for tool in session["tools"]} == {"remember", "forget", "web_search"}


def test_session_config_tools_have_strict_schemas(settings: Settings) -> None:
    for tool in build_session_config(settings, "x")["tools"]:
        assert tool["type"] == "function"
        assert tool["parameters"]["additionalProperties"] is False
        assert set(tool["parameters"]["required"]) <= set(tool["parameters"]["properties"])


RESPONSE_JSON = {
    "id": "resp_1",
    "object": "response",
    "created_at": 0,
    "model": "gpt-6.1-terra",
    "status": "completed",
    "output": [
        {
            "type": "web_search_call",
            "id": "ws_1",
            "status": "completed",
            "action": {"type": "search", "query": "weather riyadh"},
        },
        {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "status": "completed",
            "content": [
                {
                    "type": "output_text",
                    "text": "It's 31 degrees and sunny in Riyadh "
                    "([weather.com](https://weather.com/riyadh)).",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://weather.com/riyadh",
                            "title": "Riyadh weather",
                            "start_index": 0,
                            "end_index": 10,
                        },
                        {
                            "type": "url_citation",
                            "url": "https://weather.com/riyadh",
                            "title": "Duplicate",
                            "start_index": 11,
                            "end_index": 20,
                        },
                    ],
                }
            ],
        },
    ],
}


async def test_search_service_calls_responses_with_hosted_web_search() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, json=RESPONSE_JSON)

    service = SearchService(
        openai_client(handler), model="gpt-6.1-terra", reasoning_effort="low", timeout_seconds=5
    )
    result = await service.search("weather riyadh", "hashed-id")

    assert result.answer == "It's 31 degrees and sunny in Riyadh."
    assert [(s.title, s.url) for s in result.sources] == [
        ("Riyadh weather", "https://weather.com/riyadh")
    ]
    body = json.loads(captured[0].content)
    assert captured[0].url.path == "/v1/responses"
    assert body["model"] == "gpt-6.1-terra"
    assert body["input"] == "weather riyadh"
    assert body["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert body["reasoning"] == {"effort": "low"}
    assert body["store"] is False
    assert body["safety_identifier"] == "hashed-id"
    assert "untrusted" in body["instructions"]


@pytest.mark.parametrize(
    ("raw", "spoken"),
    [
        ("Plain answer.", "Plain answer."),
        ("Sunny ([bbc.co.uk](https://bbc.co.uk/x)).", "Sunny."),
        ("See [the report](https://a.b/c) today.", "See the report today."),
        ("Line one.\n\nLine  two.", "Line one. Line two."),
    ],
)
def test_clean_for_speech(raw: str, spoken: str) -> None:
    assert clean_for_speech(raw) == spoken


def test_rate_limiter_sliding_window() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=10, clock=lambda: now[0])

    assert limiter.hit("a") and limiter.hit("a")
    assert not limiter.hit("a")
    assert limiter.hit("b")  # keys are independent

    now[0] = 10.0
    assert limiter.hit("a")

    limiter.reset("a")
    assert limiter.hit("a") and limiter.hit("a")
