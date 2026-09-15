"""Tests for the profile hovercard: card API and script delivery."""

import json
from contextlib import contextmanager

import pytest
from datasette import hookimpl
from datasette.app import Datasette
from datasette.plugins import pm

from datasette_user_profiles import hovercard_script_url
from datasette_user_profiles.routes import pages


async def _make_datasette(settings=None, config=None):
    config = {"permissions": {"profile_access": {"id": "alice"}}, **(config or {})}
    ds = Datasette(memory=True, config=config, settings=settings)
    await ds.invoke_startup()
    internal = ds.get_internal_database()
    await internal.execute_write(
        "INSERT INTO datasette_user_profiles"
        " (actor_id, display_name, bio, avatar_icon, avatar_color, updated_at)"
        " VALUES ('clark', 'Clark Kent', 'Mild-mannered reporter.',"
        " 'star', '#1e66f5', '2026-05-20T00:00:00.000')"
    )
    # A profile row with no display name, bio or avatar.
    await internal.execute_write(
        "INSERT INTO datasette_user_profiles (actor_id) VALUES ('jimmy')"
    )
    await internal.execute_write(
        "INSERT INTO datasette_user_profiles (actor_id, display_name)"
        " VALUES ('42', 'Numbered User')"
    )
    return ds


def _cookie(ds, actor_id):
    return {"ds_actor": ds.sign({"a": {"id": actor_id}}, "actor")}


@contextmanager
def register_actors_plugin(names):
    """Temporarily implement core ``actors_from_ids`` with ``names``."""

    class _ActorsPlugin:
        __name__ = "hovercard_actors_test_plugin"

        @hookimpl
        def actors_from_ids(self, datasette, actor_ids):
            return {
                actor_id: {"id": actor_id, "name": names[actor_id]}
                if actor_id in names
                else {"id": actor_id}
                for actor_id in actor_ids
            }

    plugin = _ActorsPlugin()
    pm.register(plugin, name="hovercard_actors_test_plugin")
    try:
        yield
    finally:
        pm.unregister(plugin)


async def _card(ds, actor_id, actor="alice"):
    response = await ds.client.get(
        f"/-/profiles/api/hovercard/{actor_id}", cookies=_cookie(ds, actor)
    )
    assert response.status_code == 200
    return response


# --- Card API: /-/profiles/api/hovercard/<actor_id> ---


@pytest.mark.asyncio
async def test_card_for_profile():
    ds = await _make_datasette()
    response = await _card(ds, "clark")
    assert response.json() == {
        "id": "clark",
        "name": "Clark Kent",
        "bio": "Mild-mannered reporter.",
        "avatar_url": "/-/profile/pic/clark?v=2026-05-20T00:00:00.000",
        "profile_url": "/-/profile/clark",
        "has_profile": True,
    }
    assert response.headers["cache-control"] == "private, max-age=60"


@pytest.mark.asyncio
async def test_card_for_profile_without_name_or_avatar():
    ds = await _make_datasette()
    card = (await _card(ds, "jimmy")).json()
    assert card == {
        "id": "jimmy",
        "name": "jimmy",
        "bio": None,
        "avatar_url": None,
        "profile_url": "/-/profile/jimmy",
        "has_profile": True,
    }


@pytest.mark.asyncio
async def test_card_name_from_actors_from_ids_hook():
    ds = await _make_datasette()
    with register_actors_plugin({"agent-1": "Research Agent", "jimmy": "Jimmy O."}):
        agent = (await _card(ds, "agent-1")).json()
        jimmy = (await _card(ds, "jimmy")).json()
        clark = (await _card(ds, "clark")).json()
    assert agent == {
        "id": "agent-1",
        "name": "Research Agent",
        "bio": None,
        "avatar_url": None,
        "profile_url": "/-/profile/agent-1",
        "has_profile": False,
    }
    # A profile without a display name also falls back to the hook...
    assert jimmy["name"] == "Jimmy O."
    assert jimmy["has_profile"] is True
    # ...but a display name wins over it.
    assert clark["name"] == "Clark Kent"


@pytest.mark.asyncio
async def test_card_for_unknown_id_without_hook():
    ds = await _make_datasette()
    assert (await _card(ds, "ghost")).json() == {
        "id": "ghost",
        "name": "ghost",
        "bio": None,
        "avatar_url": None,
        "profile_url": "/-/profile/ghost",
        "has_profile": False,
    }


@pytest.mark.asyncio
async def test_card_numeric_actor_id():
    ds = await _make_datasette()
    card = (await _card(ds, "42")).json()
    assert card["id"] == "42"
    assert card["name"] == "Numbered User"
    assert card["has_profile"] is True
    assert card["profile_url"] == "/-/profile/42"


@pytest.mark.asyncio
async def test_card_quotes_special_ids():
    ds = await _make_datasette()
    card = (await _card(ds, "a%20b@x.com")).json()
    assert card["id"] == "a b@x.com"
    assert card["profile_url"] == "/-/profile/a%20b@x.com"


@pytest.mark.asyncio
async def test_card_requires_profile_access():
    ds = await _make_datasette()
    anonymous = await ds.client.get("/-/profiles/api/hovercard/clark")
    assert anonymous.status_code == 403
    forbidden = await ds.client.get(
        "/-/profiles/api/hovercard/clark", cookies=_cookie(ds, "bob")
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_card_profile_url_honours_base_url():
    ds = await _make_datasette(settings={"base_url": "/prefix/"})
    card = (await _card(ds, "clark")).json()
    assert card["profile_url"] == "/prefix/-/profile/clark"
    assert card["avatar_url"] == (
        "/prefix/-/profile/pic/clark?v=2026-05-20T00:00:00.000"
    )


def test_card_in_openapi_document():
    from datasette_user_profiles.router import router

    doc = router.openapi_document_json()
    assert "ProfileCard" in json.dumps(doc)


# --- Script delivery: /-/profiles/hovercard.js ---


@pytest.fixture
def hovercard_manifest(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "src/hovercard/index.ts": {
                    "file": "static/gen/hovercard-AbC123.js",
                    "name": "hovercard",
                    "src": "src/hovercard/index.ts",
                    "isEntry": True,
                }
            }
        )
    )
    monkeypatch.setattr(pages, "HOVERCARD_MANIFEST_DIR", tmp_path)


def test_hovercard_script_url_honours_base_url():
    assert hovercard_script_url(Datasette(memory=True)) == "/-/profiles/hovercard.js"
    ds = Datasette(memory=True, settings={"base_url": "/prefix/"})
    assert hovercard_script_url(ds) == "/prefix/-/profiles/hovercard.js"


@pytest.mark.asyncio
async def test_hovercard_js_redirects_to_built_file(hovercard_manifest):
    ds = await _make_datasette()
    # Anonymous: the script isn't permission-gated.
    response = await ds.client.get("/-/profiles/hovercard.js")
    assert response.status_code == 302
    assert response.headers["location"] == (
        "/-/static-plugins/datasette_user_profiles/gen/hovercard-AbC123.js"
    )


@pytest.mark.asyncio
async def test_hovercard_js_redirect_honours_base_url(hovercard_manifest):
    ds = await _make_datasette(settings={"base_url": "/prefix/"})
    response = await ds.client.get("/-/profiles/hovercard.js")
    assert response.status_code == 302
    assert response.headers["location"] == (
        "/prefix/-/static-plugins/datasette_user_profiles/gen/hovercard-AbC123.js"
    )


@pytest.mark.asyncio
async def test_hovercard_js_redirects_to_vite_dev_server():
    ds = await _make_datasette(
        config={
            "plugins": {
                "datasette-vite": {"dev_ports": {"datasette_user_profiles": 5182}}
            }
        }
    )
    response = await ds.client.get("/-/profiles/hovercard.js")
    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://localhost:5182/src/hovercard/index.ts"
    )


@pytest.mark.asyncio
async def test_hovercard_js_404_when_not_built(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text("{}")
    monkeypatch.setattr(pages, "HOVERCARD_MANIFEST_DIR", tmp_path)
    ds = await _make_datasette()
    response = await ds.client.get("/-/profiles/hovercard.js")
    assert response.status_code == 404
    assert "src/hovercard/index.ts" in response.text
