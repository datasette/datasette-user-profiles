"""Tests for the datasette_user_profile_seeds hook and core seeding."""

import base64
from contextlib import contextmanager

import pytest
from datasette import hookimpl
from datasette.app import Datasette
from datasette.plugins import pm

from datasette_user_profiles.hookspecs import ProfileSeed
from datasette_user_profiles.seed import apply_seeds


@contextmanager
def register_seed_plugin(impl):
    """Register a temporary plugin whose seed hook delegates to ``impl``.

    ``impl`` receives ``datasette`` and returns whatever the hook should return
    (a list, awaitable, callable, etc.). The plugin is unregistered afterwards
    so tests don't leak into one another.
    """

    class _SeedPlugin:
        __name__ = "seed_test_plugin"

        @hookimpl
        def datasette_user_profile_seeds(self, datasette):
            return impl(datasette)

    plugin = _SeedPlugin()
    pm.register(plugin, name="seed_test_plugin")
    try:
        yield
    finally:
        pm.unregister(plugin)


async def _profile_row(ds, actor_id):
    return (
        await ds.get_internal_database().execute(
            "SELECT actor_id, display_name, bio, email, avatar_icon, avatar_color"
            " FROM datasette_user_profiles WHERE actor_id = ?",
            [actor_id],
        )
    ).first()


async def _photo_row(ds, actor_id):
    return (
        await ds.get_internal_database().execute(
            "SELECT photo, content_type FROM datasette_user_profile_photos"
            " WHERE actor_id = ?",
            [actor_id],
        )
    ).first()


@pytest.mark.asyncio
async def test_seeds_insert_new_profiles():
    def impl(datasette):
        return [
            ProfileSeed(actor_id="ada", display_name="Ada Lovelace", email="ada@x.io"),
            ProfileSeed(actor_id="grace", display_name="Grace Hopper"),
        ]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()

    ada = await _profile_row(ds, "ada")
    assert ada["display_name"] == "Ada Lovelace"
    assert ada["email"] == "ada@x.io"
    assert (await _profile_row(ds, "grace"))["display_name"] == "Grace Hopper"


@pytest.mark.asyncio
async def test_dict_seeds_and_id_alias_accepted():
    def impl(datasette):
        return [{"id": "alan", "display_name": "Alan Turing", "bogus_field": "x"}]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()

    row = await _profile_row(ds, "alan")
    assert row["actor_id"] == "alan"
    assert row["display_name"] == "Alan Turing"


@pytest.mark.asyncio
async def test_async_callable_seed_form():
    def impl(datasette):
        async def inner():
            return [ProfileSeed(actor_id="async-bot", display_name="Async Bot")]

        return inner

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()

    assert (await _profile_row(ds, "async-bot"))["display_name"] == "Async Bot"


@pytest.mark.asyncio
async def test_fill_missing_does_not_clobber_user_value():
    # First seed only sets a display_name (no bio); the second seed (a later
    # restart) carries both a new name and a bio.
    def impl(datasette):
        calls["n"] += 1
        if calls["n"] == 1:
            return [ProfileSeed(actor_id="ada", display_name="SEED NAME")]
        return [ProfileSeed(actor_id="ada", display_name="SEED2", bio="seed bio")]

    calls = {"n": 0}
    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()
        # Simulate a user who set their own display_name (bio still empty).
        await ds.get_internal_database().execute_write(
            "UPDATE datasette_user_profiles SET display_name = ? WHERE actor_id = ?",
            ["User Chosen", "ada"],
        )
        # Re-seeding must not overwrite the user's name, but should fill the
        # still-empty bio.
        await apply_seeds(ds)

    row = await _profile_row(ds, "ada")
    assert row["display_name"] == "User Chosen"
    assert row["bio"] == "seed bio"


@pytest.mark.asyncio
async def test_seed_is_idempotent():
    calls = {"n": 0}

    def impl(datasette):
        calls["n"] += 1
        return [ProfileSeed(actor_id="ada", display_name="Ada")]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()
        await apply_seeds(ds)

    # Hook ran twice, but only one row exists.
    assert calls["n"] == 2
    rows = (
        await ds.get_internal_database().execute(
            "SELECT count(*) AS c FROM datasette_user_profiles WHERE actor_id = 'ada'"
        )
    ).first()
    assert rows["c"] == 1


@pytest.mark.asyncio
async def test_seed_photo_from_data_url_and_not_clobbered():
    # 1x1 transparent PNG as a base64 data URL.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    data_url = "data:image/png;base64," + base64.b64encode(png).decode()

    def impl(datasette):
        return [ProfileSeed(actor_id="ada", photo_url=data_url)]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()
        row = await _photo_row(ds, "ada")
        assert row["content_type"] == "image/png"
        assert row["photo"] == png
        # A user uploads their own photo; a later seed must not replace it.
        await ds.get_internal_database().execute_write(
            "UPDATE datasette_user_profile_photos SET photo = ? WHERE actor_id = ?",
            [b"USER-PHOTO", "ada"],
        )
        await apply_seeds(ds)

    assert (await _photo_row(ds, "ada"))["photo"] == b"USER-PHOTO"


@pytest.mark.asyncio
async def test_seed_photo_from_raw_bytes():
    def impl(datasette):
        return [
            ProfileSeed(
                actor_id="grace",
                photo_bytes=b"GIF89a-fake",
                photo_content_type="image/gif",
            )
        ]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()

    row = await _photo_row(ds, "grace")
    assert row["photo"] == b"GIF89a-fake"
    assert row["content_type"] == "image/gif"


@pytest.mark.asyncio
async def test_seeded_profiles_resolve_via_helper():
    from datasette_user_profiles import resolve_profile_actors

    def impl(datasette):
        return [ProfileSeed(actor_id="ada", display_name="Ada Lovelace")]

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        await ds.invoke_startup()

    actors = await resolve_profile_actors(ds, ["ada", "ghost"])
    assert "ghost" not in actors
    assert actors["ada"]["display_name"] == "Ada Lovelace"
    assert actors["ada"]["avatar_url"].endswith("/-/profile/pic/ada")


@pytest.mark.asyncio
async def test_failing_seed_impl_does_not_break_startup():
    def impl(datasette):
        raise RuntimeError("boom")

    with register_seed_plugin(impl):
        ds = Datasette(memory=True)
        # Startup must complete despite the broken implementation.
        await ds.invoke_startup()

    # Tables still exist and are simply empty.
    rows = (
        await ds.get_internal_database().execute(
            "SELECT count(*) AS c FROM datasette_user_profiles"
        )
    ).first()
    assert rows["c"] == 0
