from tests.conftest import Harness, HarnessFactory


async def remember(h: Harness, content: str, replaces_id: int | None = None) -> dict:
    body = {"content": content}
    if replaces_id is not None:
        body["replaces_id"] = replaces_id
    response = await h.client.post("/api/v1/tools/remember", json=body)
    assert response.status_code == 200, response.text
    return response.json()


async def contents(h: Harness) -> list[str]:
    return [m["content"] for m in (await h.client.get("/api/v1/memories")).json()]


async def test_remember_saves_a_fact(authed: Harness) -> None:
    result = await remember(authed, "The user's favorite color is green.")

    assert result["status"] == "saved"
    assert result["memory"]["content"] == "The user's favorite color is green."
    assert await contents(authed) == ["The user's favorite color is green."]


async def test_remember_normalizes_whitespace(authed: Harness) -> None:
    result = await remember(authed, "  Lives in\n  Riyadh.  ")
    assert result["memory"]["content"] == "Lives in Riyadh."


async def test_remember_with_replaces_id_updates_in_place(authed: Harness) -> None:
    original = await remember(authed, "Favorite color is green.")
    memory_id = original["memory"]["id"]

    result = await remember(authed, "Favorite color is blue.", replaces_id=memory_id)

    assert result["status"] == "updated"
    assert result["memory"]["id"] == memory_id
    assert result["memory"]["updated_at"] >= original["memory"]["updated_at"]
    assert await contents(authed) == ["Favorite color is blue."]


async def test_replacing_an_unknown_id_is_404(authed: Harness) -> None:
    response = await authed.client.post(
        "/api/v1/tools/remember", json={"content": "x", "replaces_id": 999}
    )
    assert response.status_code == 404


async def test_remember_rejects_empty_and_overlong_content(authed: Harness) -> None:
    for content in ["", "   \n ", "x" * 501]:
        response = await authed.client.post("/api/v1/tools/remember", json={"content": content})
        assert response.status_code == 422


async def test_memories_are_listed_newest_first(authed: Harness) -> None:
    first = await remember(authed, "First.")
    await remember(authed, "Second.")
    await remember(authed, "First, revised.", replaces_id=first["memory"]["id"])

    assert await contents(authed) == ["First, revised.", "Second."]


async def test_forget_tool(authed: Harness) -> None:
    memory_id = (await remember(authed, "Temporary."))["memory"]["id"]

    forgotten = await authed.client.post("/api/v1/tools/forget", json={"memory_id": memory_id})
    again = await authed.client.post("/api/v1/tools/forget", json={"memory_id": memory_id})

    assert forgotten.json() == {"status": "forgotten"}
    assert again.json() == {"status": "not_found"}
    assert await contents(authed) == []


async def test_delete_one_and_delete_all(authed: Harness) -> None:
    memory_id = (await remember(authed, "A."))["memory"]["id"]
    await remember(authed, "B.")
    await remember(authed, "C.")

    assert (await authed.client.delete(f"/api/v1/memories/{memory_id}")).status_code == 204
    assert (await authed.client.delete(f"/api/v1/memories/{memory_id}")).status_code == 404
    assert (await authed.client.delete("/api/v1/memories")).json() == {"deleted": 2}
    assert await contents(authed) == []


async def test_users_cannot_see_or_change_each_others_memories(
    make_harness: HarnessFactory,
) -> None:
    async with make_harness() as alice, make_harness() as bob:
        await alice.login()
        await bob.login()
        alice_fact = await remember(alice, "Alice's secret.")
        alice_id = alice_fact["memory"]["id"]

        assert await contents(bob) == []
        replace = await bob.client.post(
            "/api/v1/tools/remember", json={"content": "Hijacked.", "replaces_id": alice_id}
        )
        assert replace.status_code == 404
        forget = await bob.client.post("/api/v1/tools/forget", json={"memory_id": alice_id})
        assert forget.json() == {"status": "not_found"}
        assert (await bob.client.delete(f"/api/v1/memories/{alice_id}")).status_code == 404
        assert (await bob.client.delete("/api/v1/memories")).json() == {"deleted": 0}

        assert await contents(alice) == ["Alice's secret."]
