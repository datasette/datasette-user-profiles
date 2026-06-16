"""Seed the profiles directory from other plugins.

Plugins implement the ``datasette_user_profile_seeds`` hook to contribute
``ProfileSeed`` records for people they already know about. This module
collects those records and writes them into the internal profile tables with
*fill-missing* semantics: new actors are inserted in full, existing actors only
have their empty fields filled, and existing photos are never replaced. That
makes seeding idempotent and safe to re-run on every startup.
"""

import base64
import inspect
import logging
from urllib.parse import unquote

from datasette.plugins import pm

from .hookspecs import ProfileSeed

logger = logging.getLogger("datasette_user_profiles.seed")

# Matches the CHECK constraint on datasette_user_profile_photos.photo.
MAX_PHOTO_BYTES = 1048576


async def _resolve_hook_result(result):
    """Normalize one hook return value into a list.

    A plugin may return a list directly, an awaitable, or a zero-argument
    callable returning either — the last form lets it await async work (such as
    fetching a JSON file) only when seeding actually runs.
    """
    if result is None:
        return []
    if callable(result):
        result = result()
    if inspect.isawaitable(result):
        result = await result
    return list(result or [])


def _coerce_seed(item) -> ProfileSeed | None:
    """Coerce a hook item (ProfileSeed or dict) into a ProfileSeed.

    Plain dicts are accepted for convenience; ``id`` is treated as an alias for
    ``actor_id``. Items without an actor id, or of an unexpected type, are
    dropped with a warning rather than aborting the whole seed pass.
    """
    if isinstance(item, ProfileSeed):
        seed = item
    elif isinstance(item, dict):
        data = dict(item)
        actor_id = data.pop("actor_id", None) or data.pop("id", None)
        if actor_id is None:
            logger.warning("Skipping seed with no actor_id/id: %r", item)
            return None
        known = ProfileSeed.__dataclass_fields__
        unknown = set(data) - set(known)
        for key in unknown:
            data.pop(key)
        if unknown:
            logger.warning(
                "Ignoring unknown seed fields %s for actor %r",
                sorted(unknown),
                actor_id,
            )
        try:
            seed = ProfileSeed(actor_id=str(actor_id), **data)
        except TypeError as exc:
            logger.warning("Skipping invalid seed %r: %s", item, exc)
            return None
    else:
        logger.warning("Skipping seed of unexpected type %r", type(item))
        return None

    if not seed.actor_id:
        logger.warning("Skipping seed with empty actor_id: %r", item)
        return None
    seed.actor_id = str(seed.actor_id)
    return seed


async def collect_seeds(datasette) -> list[ProfileSeed]:
    """Gather and normalize seeds from every plugin implementing the hook."""
    seeds: list[ProfileSeed] = []
    try:
        results = list(pm.hook.datasette_user_profile_seeds(datasette=datasette))
    except Exception:
        # A plugin that raises synchronously in its hook body would otherwise
        # abort startup; degrade to seeding nothing instead.
        logger.exception("datasette_user_profile_seeds hook raised; skipping seeds")
        return []
    for result in results:
        try:
            items = await _resolve_hook_result(result)
        except Exception:
            logger.exception("A datasette_user_profile_seeds implementation failed")
            continue
        for item in items:
            seed = _coerce_seed(item)
            if seed is not None:
                seeds.append(seed)
    return seeds


def _decode_data_url(data_url) -> tuple[bytes, str] | None:
    """Decode a ``data:`` URL into ``(bytes, content_type)`` or ``None``.

    Handles both percent-encoded (e.g. inline SVG) and base64 data URLs.
    Anything that is empty, malformed, not a data URL, or over the 1MB photo
    limit returns ``None`` so the profile is still seeded without a photo.
    """
    if (
        not data_url
        or not isinstance(data_url, str)
        or not data_url.startswith("data:")
    ):
        return None
    try:
        header, sep, payload = data_url[len("data:") :].partition(",")
        if not sep:
            return None
        is_base64 = header.endswith(";base64")
        content_type = header[: -len(";base64")] if is_base64 else header
        content_type = content_type or "application/octet-stream"
        if is_base64:
            body = base64.b64decode(payload)
        else:
            body = unquote(payload).encode("utf-8")
    except Exception:
        return None
    if not body or len(body) > MAX_PHOTO_BYTES:
        return None
    return body, content_type


def _resolve_photo(seed: ProfileSeed) -> tuple[bytes, str] | None:
    """Resolve a seed's photo to ``(bytes, content_type)`` or ``None``.

    Raw ``photo_bytes`` win over ``photo_url``. Remote URLs are intentionally
    not fetched here (a plugin that wants them should fetch and pass bytes).
    """
    if seed.photo_bytes is not None:
        if not seed.photo_bytes or len(seed.photo_bytes) > MAX_PHOTO_BYTES:
            logger.warning(
                "Ignoring photo_bytes for actor %r (empty or over 1MB)", seed.actor_id
            )
            return None
        return seed.photo_bytes, seed.photo_content_type or "image/jpeg"
    return _decode_data_url(seed.photo_url)


async def apply_seeds(datasette) -> int:
    """Collect seeds and write them into the internal profile tables.

    Returns the number of seeds written. Safe to call on every startup: writes
    use fill-missing upserts so user edits and existing photos are preserved.
    """
    seeds = await collect_seeds(datasette)
    if not seeds:
        return 0

    photos = {seed.actor_id: _resolve_photo(seed) for seed in seeds}

    def write(conn):
        with conn:
            for seed in seeds:
                # Fill-missing: insert a new actor in full, but for an existing
                # row only populate columns that are still NULL. COALESCE keeps
                # whatever the user (or an earlier seed) already set.
                conn.execute(
                    """
                    INSERT INTO datasette_user_profiles
                        (actor_id, display_name, bio, email, avatar_icon, avatar_color)
                    VALUES (:actor_id, :display_name, :bio, :email, :avatar_icon, :avatar_color)
                    ON CONFLICT(actor_id) DO UPDATE SET
                        display_name = COALESCE(display_name, excluded.display_name),
                        bio = COALESCE(bio, excluded.bio),
                        email = COALESCE(email, excluded.email),
                        avatar_icon = COALESCE(avatar_icon, excluded.avatar_icon),
                        avatar_color = COALESCE(avatar_color, excluded.avatar_color)
                    """,
                    {
                        "actor_id": seed.actor_id,
                        "display_name": seed.display_name,
                        "bio": seed.bio,
                        "email": seed.email,
                        "avatar_icon": seed.avatar_icon,
                        "avatar_color": seed.avatar_color,
                    },
                )
                photo = photos.get(seed.actor_id)
                if photo is not None:
                    photo_bytes, content_type = photo
                    # INSERT OR IGNORE: never replace an existing (uploaded or
                    # previously seeded) photo.
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO datasette_user_profile_photos
                            (actor_id, photo, content_type)
                        VALUES (?, ?, ?)
                        """,
                        [seed.actor_id, photo_bytes, content_type],
                    )

    await datasette.get_internal_database().execute_write_fn(write)
    logger.info("Seeded %d profile(s) from plugins", len(seeds))
    return len(seeds)
