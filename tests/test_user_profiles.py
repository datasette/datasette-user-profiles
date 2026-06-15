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


async def _make_datasette(plugin_config=None):
    """Datasette where actor 'alice' has profile_access, seeded with profiles.

    Pass ``plugin_config`` to set ``plugins.datasette-user-profiles`` config,
    e.g. ``{"editable_fields": {"email": False}}``.
    """
    config = {"permissions": {"profile_access": {"id": "alice"}}}
    if plugin_config is not None:
        config["plugins"] = {"datasette-user-profiles": plugin_config}
    ds = Datasette(memory=True, config=config)
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
    response = await ds.client.get("/-/profiles/api/search", cookies=_cookie(ds, "bob"))
    assert response.status_code == 403


# --- resolve_profile_actors helper ---


@pytest.mark.asyncio
async def test_resolve_profile_actors_returns_known_users_only():
    from datasette_user_profiles import resolve_profile_actors

    ds = await _make_datasette()
    actors = await resolve_profile_actors(ds, ["alice", "bob", "ghost"])
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
    # Unknown id is omitted entirely — callers apply their own fallback.
    assert "ghost" not in actors


@pytest.mark.asyncio
async def test_resolve_profile_actors_coerces_numeric_ids_to_strings():
    from datasette_user_profiles import resolve_profile_actors

    ds = await _make_datasette()
    # Numeric ids are coerced to strings; unknown ids are omitted.
    assert await resolve_profile_actors(ds, [1, 2]) == {}


@pytest.mark.asyncio
async def test_resolve_profile_actors_empty_list():
    from datasette_user_profiles import resolve_profile_actors

    ds = await _make_datasette()
    assert await resolve_profile_actors(ds, []) == {}


@pytest.mark.asyncio
async def test_plugin_does_not_own_actors_from_ids_hook():
    """profiles must not claim core's firstresult=True actors_from_ids hook."""
    ds = await _make_datasette()
    # With no other identity plugin installed, core falls back to the default
    # {"id": <id>} for every id, including known profile users.
    actors = await ds.actors_from_ids(["alice", "ghost"])
    assert actors == {"alice": {"id": "alice"}, "ghost": {"id": "ghost"}}


# --- Optional datasette_acl_valid_actors integration ---

from datasette.utils import await_me_maybe
from datasette_user_profiles import _datasette_acl_installed, _valid_actors_impl


@pytest.mark.asyncio
async def test_no_hard_dependency_on_acl():
    """profiles must import and start cleanly without datasette-acl, and only
    register the acl hookimpl when acl is importable."""
    import datasette_user_profiles as dup

    has_hookimpl = hasattr(dup, "datasette_acl_valid_actors")
    # The module-level hookimpl is registered iff acl is importable.
    assert has_hookimpl == _datasette_acl_installed()

    # Either way, profiles starts cleanly.
    ds = Datasette(memory=True)
    await ds.invoke_startup()
    response = await ds.client.get("/-/plugins.json")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_valid_actors_returns_seeded_users():
    """The valid_actors implementation returns every profile as an acl-style
    {"id", "display"} dict (no query needed there — acl filters)."""
    ds = await _make_datasette()
    actors = await await_me_maybe(_valid_actors_impl(ds))
    # All seeded users present, sorted by display_name
    # ("Albert Smith" < "Alice Anderson" < "Bob Jones" < "Carol Lee").
    assert actors == [
        {"id": "albert", "display": "Albert Smith"},
        {"id": "alice", "display": "Alice Anderson"},
        {"id": "bob", "display": "Bob Jones"},
        {"id": "cal", "display": "Carol Lee"},
    ]


@pytest.mark.asyncio
async def test_valid_actors_falls_back_to_actor_id_when_no_display_name():
    ds = Datasette(memory=True)
    await ds.invoke_startup()
    internal = ds.get_internal_database()
    await internal.execute_write(
        "INSERT INTO datasette_user_profiles (actor_id) VALUES (?)", ["nameless"]
    )
    actors = await await_me_maybe(_valid_actors_impl(ds))
    assert actors == [{"id": "nameless", "display": "nameless"}]


# --- editable_fields config ---


async def _get_profile_row(ds, actor_id):
    return (
        await ds.get_internal_database().execute(
            "SELECT display_name, bio, email, avatar_icon, avatar_color"
            " FROM datasette_user_profiles WHERE actor_id = ?",
            [actor_id],
        )
    ).first()


def test_editable_fields_defaults_all_true():
    from datasette_user_profiles.config import editable_fields

    ds = Datasette(memory=True)
    assert editable_fields(ds) == {
        "display_name": True,
        "bio": True,
        "email": True,
        "avatar": True,
    }


def test_editable_fields_honours_overrides():
    from datasette_user_profiles.config import editable_fields

    ds = Datasette(
        memory=True,
        config={
            "plugins": {
                "datasette-user-profiles": {
                    "editable_fields": {"email": False, "avatar": False}
                }
            }
        },
    )
    assert editable_fields(ds) == {
        "display_name": True,
        "bio": True,
        "email": False,
        "avatar": False,
    }


@pytest.mark.asyncio
async def test_update_changes_all_fields_by_default():
    ds = await _make_datasette()
    response = await ds.client.post(
        "/-/api/user-profile/update",
        json={"display_name": "Alice A.", "email": "new@example.com"},
        cookies=_cookie(ds, "alice"),
    )
    assert response.status_code == 200
    row = await _get_profile_row(ds, "alice")
    assert row["display_name"] == "Alice A."
    assert row["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_update_preserves_locked_field():
    ds = await _make_datasette({"editable_fields": {"email": False}})
    response = await ds.client.post(
        "/-/api/user-profile/update",
        json={"display_name": "Alice A.", "email": "hacker@evil.com"},
        cookies=_cookie(ds, "alice"),
    )
    assert response.status_code == 200
    row = await _get_profile_row(ds, "alice")
    # Editable field changed; locked email kept its seeded value.
    assert row["display_name"] == "Alice A."
    assert row["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_update_locked_avatar_not_written():
    ds = await _make_datasette({"editable_fields": {"avatar": False}})
    response = await ds.client.post(
        "/-/api/user-profile/update",
        json={"avatar_icon": "star", "avatar_color": "#ff0000"},
        cookies=_cookie(ds, "alice"),
    )
    assert response.status_code == 200
    row = await _get_profile_row(ds, "alice")
    assert row["avatar_icon"] is None
    assert row["avatar_color"] is None


@pytest.mark.asyncio
async def test_locked_avatar_rejects_photo_upload():
    ds = await _make_datasette({"editable_fields": {"avatar": False}})
    import base64

    tiny_png = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
    response = await ds.client.post(
        "/-/api/user-profile/photo",
        json={"photo_data": tiny_png, "content_type": "image/png"},
        cookies=_cookie(ds, "alice"),
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Avatar editing is disabled"


@pytest.mark.asyncio
async def test_locked_avatar_rejects_photo_delete():
    ds = await _make_datasette({"editable_fields": {"avatar": False}})
    response = await ds.client.post(
        "/-/api/user-profile/photo/delete",
        json={},
        cookies=_cookie(ds, "alice"),
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Avatar editing is disabled"


@pytest.mark.asyncio
async def test_edit_page_exposes_editable_map():
    ds = await _make_datasette({"editable_fields": {"email": False}})
    response = await ds.client.get("/-/user-profile/edit", cookies=_cookie(ds, "alice"))
    assert response.status_code == 200
    # The page_data JSON embedded in the page carries the editable map.
    assert '"email": false' in response.text or '"email":false' in response.text
