"""
Sample plugin that seeds user profiles from a JSON actor directory.

It implements ``datasette_user_profile_seeds`` and returns an async callable, so
the JSON is only fetched/read when seeding actually runs at startup. The source
is configurable; with no config it falls back to the bundled
``seed_actors.json`` sitting next to this file so the dev server shows people
out of the box.

    plugins:
      sample-seed-actors:
        url: https://example.com/actors.json   # fetched with httpx
        # or
        path: /absolute/path/to/actors.json     # read from disk

Each record maps ``name`` -> display_name and accepts ``id``/``actor_id``,
``email``, ``bio``, ``avatar_icon`` and ``avatar_color``.
"""

import json
import logging
import os

import httpx
from datasette import hookimpl
from datasette_user_profiles.hookspecs import ProfileSeed

logger = logging.getLogger("sample_seed_actors")

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "seed_actors.json")


async def _load_records(datasette) -> list[dict]:
    config = datasette.plugin_config("sample-seed-actors") or {}
    url = config.get("url")
    path = config.get("path", DEFAULT_PATH)

    if url:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    with open(path) as f:
        return json.load(f)


def _to_seed(record: dict) -> ProfileSeed | None:
    actor_id = record.get("id") or record.get("actor_id")
    if not actor_id:
        return None
    return ProfileSeed(
        actor_id=str(actor_id),
        display_name=record.get("name") or record.get("display_name"),
        email=record.get("email"),
        bio=record.get("bio"),
        avatar_icon=record.get("avatar_icon"),
        avatar_color=record.get("avatar_color"),
    )


@hookimpl
def datasette_user_profile_seeds(datasette):
    async def inner():
        try:
            records = await _load_records(datasette)
        except Exception:
            logger.exception("Could not load seed actors")
            return []
        return [seed for record in records if (seed := _to_seed(record)) is not None]

    return inner
