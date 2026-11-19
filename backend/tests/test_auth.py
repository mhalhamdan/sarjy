from tests.conftest import PASSCODE, Harness, HarnessFactory


async def test_status_is_unauthenticated_without_cookie(harness: Harness) -> None:
    response = await harness.client.get("/api/v1/auth/status")
    assert response.json() == {"authenticated": False}


async def test_wrong_passcode_is_rejected(harness: Harness) -> None:
    response = await harness.client.post("/api/v1/auth/passcode", json={"passcode": "nope"})
    assert response.status_code == 401
    assert harness.settings.cookie_name not in response.cookies


async def test_correct_passcode_sets_signed_httponly_cookie(harness: Harness) -> None:
    response = await harness.client.post("/api/v1/auth/passcode", json={"passcode": PASSCODE})

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    status = await harness.client.get("/api/v1/auth/status")
    assert status.json() == {"authenticated": True}


async def test_secure_flag_is_set_when_configured(make_harness: HarnessFactory) -> None:
    async with make_harness(cookie_secure=True) as h:
        response = await h.client.post("/api/v1/auth/passcode", json={"passcode": PASSCODE})
        assert "secure" in response.headers["set-cookie"].lower()


async def test_reentering_passcode_keeps_the_same_user(authed: Harness) -> None:
    await authed.client.post("/api/v1/tools/remember", json={"content": "Likes tea."})

    await authed.login()

    memories = (await authed.client.get("/api/v1/memories")).json()
    assert [m["content"] for m in memories] == ["Likes tea."]


async def test_passcode_attempts_are_rate_limited(make_harness: HarnessFactory) -> None:
    async with make_harness(passcode_attempts_per_15_min=3) as h:
        for _ in range(3):
            response = await h.client.post("/api/v1/auth/passcode", json={"passcode": "nope"})
            assert response.status_code == 401
        # Even the right passcode is refused once the limit is reached.
        response = await h.client.post("/api/v1/auth/passcode", json={"passcode": PASSCODE})
        assert response.status_code == 429


async def test_protected_endpoints_require_the_cookie(harness: Harness) -> None:
    requests = [
        ("GET", "/api/v1/memories", None),
        ("DELETE", "/api/v1/memories", None),
        ("DELETE", "/api/v1/memories/1", None),
        ("POST", "/api/v1/realtime/session", None),
        ("POST", "/api/v1/tools/remember", {"content": "x"}),
        ("POST", "/api/v1/tools/forget", {"memory_id": 1}),
        ("POST", "/api/v1/tools/web_search", {"query": "x"}),
    ]
    for method, path, body in requests:
        response = await harness.client.request(method, path, json=body)
        assert response.status_code == 401, (method, path)


async def test_tampered_cookie_is_rejected(authed: Harness) -> None:
    cookie = authed.client.cookies[authed.settings.cookie_name]
    authed.client.cookies.set(authed.settings.cookie_name, cookie[:-4] + "AAAA")

    response = await authed.client.get("/api/v1/memories")

    assert response.status_code == 401
