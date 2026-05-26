from datasette import hookimpl
from datasette.app import Datasette
from datasette.plugins import pm
import pytest


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-user-profiles" in installed_plugins


# --- Search API: /-/profiles/api/search ---

SEED_PROFILES = [
    # (actor_id, display_name, email, updated_at)
    ("alice", "Alice Anderson", "alice@example.com", "2026-05-20T00:00:00.000"),
    ("albert", "Albert Smith", "albert@work.org", "2026-05-21T00:00:00.000"),
    ("bob", "Bob Jones", "bob@example.com", "2026-05-22T00:00:00.000"),
    ("cal", "Carol Lee", "carol@al.io", "2026-05-23T00:00:00.000"),
]


async def _make_datasette():
    """Datasette where actor 'alice' has profile_access, seeded with profiles."""
    ds = Datasette(
        memory=True,
        config={"permissions": {"profile_access": {"id": "alice"}}},
    )
    await ds.invoke_startup()
    internal = ds.get_internal_database()
    for actor_id, display_name, email, updated_at in SEED_PROFILES:
        await internal.execute_write(
            "INSERT INTO datasette_user_profiles"
            " (actor_id, display_name, email, updated_at)"
            " VALUES (?, ?, ?, ?)",
            [actor_id, display_name, email, updated_at],
        )
    return ds


def _cookie(ds, actor_id):
    return {"ds_actor": ds.sign({"a": {"id": actor_id}}, "actor")}


@pytest.mark.asyncio
async def test_search_indexes_created_and_idempotent():
    ds = Datasette(memory=True)
    await ds.invoke_startup()
    # Running startup again must not raise (migrations are idempotent).
    await ds.invoke_startup()
    internal = ds.get_internal_database()
    rows = (
        await internal.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
            " AND name LIKE 'idx_profiles%'"
        )
    ).rows
    names = sorted(r["name"] for r in rows)
    assert names == ["idx_profiles_display_name", "idx_profiles_email"]


@pytest.mark.asyncio
async def test_search_empty_q_returns_recent():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["results"]]
    # Most-recently-updated first.
    assert ids == ["cal", "bob", "albert", "alice"]


@pytest.mark.asyncio
async def test_search_matches_display_name_and_email():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?q=al", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["results"]]
    # albert + alice match display_name; cal matches via email "carol@al.io".
    assert set(ids) == {"albert", "alice", "cal"}


@pytest.mark.asyncio
async def test_search_prefix_matches_rank_first():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?q=al", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["results"]]
    # display_name prefix matches (Albert, Alice) come before the
    # email-only contains match (cal).
    assert ids[:2] == ["albert", "alice"]
    assert ids[-1] == "cal"


@pytest.mark.asyncio
async def test_search_limit_respected():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?q=al&limit=2", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@pytest.mark.asyncio
async def test_search_limit_capped_at_50():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?limit=999", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    # Only 4 seeded rows, but the request must not error on the large limit.
    assert len(response.json()["results"]) == 4


@pytest.mark.asyncio
async def test_search_result_shape():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?q=alice", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result == {
        "id": "alice",
        "display_name": "Alice Anderson",
        "email": "alice@example.com",
        "avatar_url": "/-/profile/pic/alice",
        "kind": "user",
    }


@pytest.mark.asyncio
async def test_search_email_can_be_omitted():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search?q=al&email=0", cookies=_cookie(ds, "alice")
    )
    assert response.status_code == 200
    assert all(r["email"] is None for r in response.json()["results"])


@pytest.mark.asyncio
async def test_search_unauthenticated_blocked():
    ds = await _make_datasette()
    response = await ds.client.get("/-/profiles/api/search")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_forbidden_actor_blocked():
    ds = await _make_datasette()
    response = await ds.client.get(
        "/-/profiles/api/search", cookies=_cookie(ds, "bob")
    )
    assert response.status_code == 403


# --- actors_from_ids + datasette_resolve_actors sub-hook ---


@pytest.mark.asyncio
async def test_actors_from_ids_resolves_users_and_defaults_unknown():
    ds = await _make_datasette()
    actors = await ds.actors_from_ids(["alice", "bob", "ghost"])
    assert actors["alice"] == {
        "id": "alice",
        "display_name": "Alice Anderson",
        "email": "alice@example.com",
        "kind": "user",
        "avatar_url": "/-/profile/pic/alice",
    }
    assert actors["bob"] == {
        "id": "bob",
        "display_name": "Bob Jones",
        "email": "bob@example.com",
        "kind": "user",
        "avatar_url": "/-/profile/pic/bob",
    }
    # Unknown id defaults to just {"id": id}.
    assert actors["ghost"] == {"id": "ghost"}


@pytest.mark.asyncio
async def test_actors_from_ids_coerces_numeric_ids_to_strings():
    ds = await _make_datasette()
    actors = await ds.actors_from_ids([1, 2])
    # Numeric ids are coerced to strings; unknown -> {"id": "1"} etc.
    assert actors == {"1": {"id": "1"}, "2": {"id": "2"}}


@pytest.mark.asyncio
async def test_actors_from_ids_empty_list():
    ds = await _make_datasette()
    assert await ds.actors_from_ids([]) == {}


class ResolveActorsPlugin:
    """Test plugin contributing identities via the sub-hook."""

    __name__ = "ResolveActorsPlugin"

    @hookimpl
    def datasette_resolve_actors(self, datasette, actor_ids):
        resolved = {}
        for actor_id in actor_ids:
            if actor_id == "agent-x":
                resolved[actor_id] = {
                    "id": "agent-x",
                    "display_name": "Agent X",
                    "avatar_url": "/-/agents/pic/agent-x",
                    "kind": "agent",
                }
        return resolved


@pytest.mark.asyncio
async def test_actors_from_ids_delegates_to_subhook():
    ds = await _make_datasette()
    plugin = ResolveActorsPlugin()
    pm.register(plugin, name="undo-resolve-actors-plugin")
    try:
        actors = await ds.actors_from_ids(["alice", "agent-x", "nobody"])
    finally:
        pm.unregister(plugin)

    # Known user still resolved by profiles.
    assert actors["alice"]["kind"] == "user"
    # Unknown id resolved by the sub-hook is merged in.
    assert actors["agent-x"] == {
        "id": "agent-x",
        "display_name": "Agent X",
        "avatar_url": "/-/agents/pic/agent-x",
        "kind": "agent",
    }
    # Still-unresolved id falls back to the default.
    assert actors["nobody"] == {"id": "nobody"}


@pytest.mark.asyncio
async def test_subhook_not_called_when_all_resolved():
    ds = await _make_datasette()

    calls = []

    class SpyPlugin:
        __name__ = "SpyPlugin"

        @hookimpl
        def datasette_resolve_actors(self, datasette, actor_ids):
            calls.append(list(actor_ids))
            return {}

    plugin = SpyPlugin()
    pm.register(plugin, name="undo-spy-resolve-actors")
    try:
        # Only known users -> sub-hook should not be invoked.
        await ds.actors_from_ids(["alice", "bob"])
        assert calls == []
        # An unknown id -> sub-hook invoked with only the missing ids.
        await ds.actors_from_ids(["alice", "ghost"])
        assert calls == [["ghost"]]
    finally:
        pm.unregister(plugin)
