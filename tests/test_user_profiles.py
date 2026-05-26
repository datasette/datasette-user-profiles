from datasette.app import Datasette
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
