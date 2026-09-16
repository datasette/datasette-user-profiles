"""Throwaway demo cast for the screenshot harness.

Loaded via `datasette --plugins-dir` from frontend/scripts/screenshots.mjs. NOT
shipped — screenshot use only.

Seeding goes through this plugin's own public ``datasette_user_profile_seeds``
hook rather than writing to the internal database directly, so the shots
exercise the same path a real integrator would use.

Determinism, the contract these shots depend on:

* Every profile carries an explicit ``avatar_icon``/``avatar_color`` (except
  ``tim``, deliberately bare so the directory shows the letter-placeholder
  fallback). Nothing is derived from a hash or a random pick.
* ``ada``'s photo is generated pixel-by-pixel below instead of being a binary
  fixture, so it is byte-identical on every run and on every machine without
  committing an image to the repo just to screenshot it.
* ``updated_at`` is restamped after seeding (see ``startup``) because the
  profiles directory is ``ORDER BY updated_at DESC`` and the column defaults to
  ``strftime(..., 'now')`` at millisecond precision — a batch of seeds inserted
  in one transaction can easily tie, and SQLite's sort is not guaranteed stable,
  so the listing order would wobble between runs.
"""

import struct
import zlib

from datasette import hookimpl
from datasette_user_profiles.hookspecs import ProfileSeed


def _png(size, pixel):
    """Minimal 8-bit RGB PNG encoder (stdlib only, deterministic output)."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0 (None) for every scanline
        for x in range(size):
            raw.extend(pixel(x, y))

    def chunk(tag, data):
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _avatar_photo(size=400):
    """An abstract portrait: head + shoulders knocked out of a diagonal wash.

    Reads as a real uploaded picture in the shots (and proves the photo path,
    which renders differently from the generated icon avatars) without shipping
    a JPEG of a person into the repo.
    """
    top = (0x74, 0xC7, 0xEC)  # sky
    bottom = (0x88, 0x39, 0xEF)  # mauve
    head_c, head_r = (size / 2, size * 0.40), size * 0.17
    body_c, body_r = (size / 2, size * 1.08), size * 0.44
    edge = size * 0.008  # soft edge, in px, to avoid a jaggy silhouette

    def coverage(x, y, center, radius):
        d = ((x - center[0]) ** 2 + (y - center[1]) ** 2) ** 0.5
        if d <= radius - edge:
            return 1.0
        if d >= radius + edge:
            return 0.0
        return (radius + edge - d) / (2 * edge)

    def pixel(x, y):
        t = (x + y) / (2 * (size - 1))
        base = [top[i] + (bottom[i] - top[i]) * t for i in range(3)]
        a = max(coverage(x, y, head_c, head_r), coverage(x, y, body_c, body_r))
        # Lift the silhouette toward white rather than painting it flat, so the
        # gradient still reads through it.
        return bytes(int(c + (255 - c) * 0.80 * a) for c in base)

    return _png(size, pixel)


# The cast, in the order they should appear in the directory (newest first).
# updated_at is pinned to these fixed, distinct values in startup() below.
PROFILES = [
    (
        "2026-05-20T12:00:00.000",
        ProfileSeed(
            actor_id="ada",
            display_name="Ada Lovelace",
            email="ada@analytical.engine",
            bio="Wrote the first algorithm intended for a machine. Currently "
            "translating Menabrea, with rather extensive notes.",
            avatar_icon="star",
            avatar_color="#8839ef",
            photo_bytes=_avatar_photo(),
            photo_content_type="image/png",
        ),
    ),
    (
        "2026-05-19T11:00:00.000",
        ProfileSeed(
            actor_id="grace",
            display_name="Grace Hopper",
            email="grace@navy.mil",
            bio='Coined the term "debugging" after a literal moth. Compilers, mostly.',
            avatar_icon="lightning-charge",
            avatar_color="#1e66f5",
        ),
    ),
    (
        "2026-05-18T10:00:00.000",
        ProfileSeed(
            actor_id="alan",
            display_name="Alan Turing",
            email="alan@bletchley.park",
            bio="Asked whether machines can think.",
            avatar_icon="eye",
            avatar_color="#40a02b",
        ),
    ),
    (
        "2026-05-17T09:00:00.000",
        ProfileSeed(
            actor_id="katherine",
            display_name="Katherine Johnson",
            email="katherine@nasa.gov",
            bio="Orbital mechanics by hand. Check the numbers, then check them again.",
            avatar_icon="rocket",
            avatar_color="#d20f39",
        ),
    ),
    (
        "2026-05-16T08:00:00.000",
        ProfileSeed(
            actor_id="margaret",
            display_name="Margaret Hamilton",
            email="margaret@mit.edu",
            bio="Wrote the onboard flight software for Apollo. Coined "
            '"software engineering".',
            avatar_icon="moon",
            avatar_color="#fe640b",
        ),
    ),
    (
        "2026-05-15T07:00:00.000",
        # Deliberately no avatar_icon/avatar_color: shows the letter-placeholder
        # fallback in the directory next to the icon and photo avatars.
        ProfileSeed(
            actor_id="tim",
            display_name="Tim Berners-Lee",
            email="tim@w3.org",
            bio="Proposed a distributed hypertext system. It caught on.",
        ),
    ),
]


@hookimpl
def datasette_user_profile_seeds():
    return [seed for _, seed in PROFILES]


@hookimpl(trylast=True)
def startup(datasette):
    """Pin updated_at so the directory's ORDER BY updated_at DESC is stable.

    ``trylast`` so this runs after the plugin's own startup seeding has inserted
    the rows — otherwise there would be nothing to restamp.
    """

    async def inner():
        db = datasette.get_internal_database()
        for updated_at, seed in PROFILES:
            await db.execute_write(
                "UPDATE datasette_user_profiles"
                " SET updated_at = ?, created_at = ?"
                " WHERE actor_id = ?",
                [updated_at, updated_at, seed.actor_id],
            )

    return inner
