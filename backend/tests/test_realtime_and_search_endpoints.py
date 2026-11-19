from tests.conftest import Harness, HarnessFactory


async def test_session_returns_the_ephemeral_key(authed: Harness) -> None:
    response = await authed.client.post("/api/v1/realtime/session")

    assert response.status_code == 200
    assert response.json() == {
        "client_secret": "ek_test",
        "expires_at": 1_900_000_000,
        "model": authed.settings.realtime_model,
    }


async def test_session_instructions_contain_the_users_memories(authed: Harness) -> None:
    saved = await authed.client.post(
        "/api/v1/tools/remember", json={"content": "The user's favorite color is green."}
    )
    memory_id = saved.json()["memory"]["id"]

    await authed.client.post("/api/v1/realtime/session")

    instructions, safety_id = authed.realtime.calls[-1]
    assert f"[{memory_id}] The user's favorite color is green." in instructions
    assert len(safety_id) == 64  # sha256 hex, not the raw user id


async def test_session_instructions_say_nothing_yet_for_a_new_user(authed: Harness) -> None:
    await authed.client.post("/api/v1/realtime/session")
    instructions, _ = authed.realtime.calls[-1]
    assert instructions.endswith("Nothing yet.")


async def test_only_the_newest_facts_are_loaded(make_harness: HarnessFactory) -> None:
    async with make_harness(memory_prompt_limit=2) as h:
        await h.login()
        for fact in ["Oldest.", "Middle.", "Newest."]:
            await h.client.post("/api/v1/tools/remember", json={"content": fact})

        await h.client.post("/api/v1/realtime/session")

        instructions, _ = h.realtime.calls[-1]
        assert "Newest." in instructions and "Middle." in instructions
        assert "Oldest." not in instructions
        assert "Only the 2 most recent facts are shown" in instructions


async def test_sessions_are_limited_per_day(make_harness: HarnessFactory) -> None:
    async with make_harness(sessions_per_user_per_day=2) as h:
        await h.login()
        statuses = [(await h.client.post("/api/v1/realtime/session")).status_code for _ in "abc"]
        assert statuses == [200, 200, 429]


async def test_web_search_returns_answer_and_sources(authed: Harness) -> None:
    response = await authed.client.post(
        "/api/v1/tools/web_search", json={"query": "weather in Riyadh"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Answer for weather in Riyadh.",
        "sources": [{"title": "Example", "url": "https://example.com"}],
    }


async def test_web_search_is_rate_limited(make_harness: HarnessFactory) -> None:
    async with make_harness(searches_per_user_per_minute=1) as h:
        await h.login()
        first = await h.client.post("/api/v1/tools/web_search", json={"query": "a"})
        second = await h.client.post("/api/v1/tools/web_search", json={"query": "b"})
        assert (first.status_code, second.status_code) == (200, 429)
        assert h.search.queries == ["a"]


async def test_health(harness: Harness) -> None:
    response = await harness.client.get("/api/v1/health")
    assert response.json() == {"status": "ok"}
