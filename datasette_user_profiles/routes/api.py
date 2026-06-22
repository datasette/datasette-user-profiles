import base64
from typing import Annotated

from datasette import Response
from datasette_plugin_router import Body

from ..config import editable_fields
from ..page_data import (
    DeletePhotoResponse,
    ResolveResponse,
    SearchResponse,
    SearchResult,
    UpdateProfileRequest,
    UpdateProfileResponse,
    UploadPhotoRequest,
    UploadPhotoResponse,
)
from ..router import router, check_permission
from .. import resolve_profile_actors


@router.POST("/-/api/user-profile/update$", output=UpdateProfileResponse)
@check_permission()
async def api_update_profile(
    datasette, request, body: Annotated[UpdateProfileRequest, Body()]
):
    if not request.actor:
        return Response.json(
            UpdateProfileResponse(ok=False, error="Not authenticated").model_dump(),
            status=403,
        )
    actor_id = request.actor.get("id")
    if not actor_id:
        return Response.json(
            UpdateProfileResponse(ok=False, error="Actor has no id").model_dump(),
            status=403,
        )
    actor_id = str(actor_id)

    internal_db = datasette.get_internal_database()
    editable = editable_fields(datasette)

    # Locked fields keep whatever is already stored; users can't change them.
    existing = (
        await internal_db.execute(
            "SELECT display_name, bio, email, avatar_icon, avatar_color"
            " FROM datasette_user_profiles WHERE actor_id = ?",
            [actor_id],
        )
    ).first()

    def pick(field, submitted, current_key=None):
        if editable[field]:
            return submitted
        return existing[current_key or field] if existing else None

    display_name = pick("display_name", body.display_name)
    bio = pick("bio", body.bio)
    email = pick("email", body.email)
    avatar_icon = pick("avatar", body.avatar_icon, "avatar_icon")
    avatar_color = pick("avatar", body.avatar_color, "avatar_color")

    def write(conn):
        with conn:
            # Upsert the profile
            conn.execute(
                """
                INSERT INTO datasette_user_profiles (actor_id, display_name, bio, email, avatar_icon, avatar_color)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    bio = excluded.bio,
                    email = excluded.email,
                    avatar_icon = excluded.avatar_icon,
                    avatar_color = excluded.avatar_color,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                """,
                [actor_id, display_name, bio, email, avatar_icon, avatar_color],
            )

    await internal_db.execute_write_fn(write)
    return Response.json(UpdateProfileResponse(ok=True).model_dump())


@router.POST("/-/api/user-profile/photo$", output=UploadPhotoResponse)
@check_permission()
async def api_upload_photo(
    datasette, request, body: Annotated[UploadPhotoRequest, Body()]
):
    if not request.actor:
        return Response.json(
            UploadPhotoResponse(ok=False, error="Not authenticated").model_dump(),
            status=403,
        )
    actor_id = request.actor.get("id")
    if not actor_id:
        return Response.json(
            UploadPhotoResponse(ok=False, error="Actor has no id").model_dump(),
            status=403,
        )
    actor_id = str(actor_id)

    if not editable_fields(datasette)["avatar"]:
        return Response.json(
            UploadPhotoResponse(
                ok=False, error="Avatar editing is disabled"
            ).model_dump(),
            status=403,
        )

    try:
        photo_bytes = base64.b64decode(body.photo_data)
    except Exception:
        return Response.json(
            UploadPhotoResponse(ok=False, error="Invalid base64 data").model_dump(),
            status=400,
        )

    if len(photo_bytes) > 1048576:
        return Response.json(
            UploadPhotoResponse(ok=False, error="Photo exceeds 1MB limit").model_dump(),
            status=400,
        )

    internal_db = datasette.get_internal_database()

    def write(conn):
        with conn:
            # Ensure profile row exists
            conn.execute(
                "INSERT OR IGNORE INTO datasette_user_profiles (actor_id) VALUES (?)",
                [actor_id],
            )
            # Upsert the photo
            conn.execute(
                """
                INSERT INTO datasette_user_profile_photos (actor_id, photo, content_type)
                VALUES (?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    photo = excluded.photo,
                    content_type = excluded.content_type,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                """,
                [actor_id, photo_bytes, body.content_type],
            )

    await internal_db.execute_write_fn(write)
    return Response.json(UploadPhotoResponse(ok=True).model_dump())


@router.POST("/-/api/user-profile/photo/delete$", output=DeletePhotoResponse)
@check_permission()
async def api_delete_photo(datasette, request):
    if not request.actor:
        return Response.json(
            DeletePhotoResponse(ok=False, error="Not authenticated").model_dump(),
            status=403,
        )
    actor_id = request.actor.get("id")
    if not actor_id:
        return Response.json(
            DeletePhotoResponse(ok=False, error="Actor has no id").model_dump(),
            status=403,
        )
    actor_id = str(actor_id)

    if not editable_fields(datasette)["avatar"]:
        return Response.json(
            DeletePhotoResponse(
                ok=False, error="Avatar editing is disabled"
            ).model_dump(),
            status=403,
        )

    internal_db = datasette.get_internal_database()
    await internal_db.execute_write(
        "DELETE FROM datasette_user_profile_photos WHERE actor_id = ?",
        [actor_id],
    )
    return Response.json(DeletePhotoResponse(ok=True).model_dump())


def _truthy(value, default=True):
    """Interpret a query-string flag. Absent → default."""
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


@router.GET("/-/profiles/api/search$", output=SearchResponse)
@check_permission()
async def api_search(datasette, request):
    q = (request.args.get("q") or "").strip()

    try:
        limit = int(request.args.get("limit") or 20)
    except (TypeError, ValueError):
        limit = 20
    # Cap the limit at 50, and keep it at least 1.
    limit = max(1, min(limit, 50))

    # Per plan §F: email is included by default but can be omitted on request.
    include_email = _truthy(request.args.get("email"), default=True)

    internal_db = datasette.get_internal_database()

    if not q:
        # Empty query → most-recently-updated profiles (capped).
        rows = (
            await internal_db.execute(
                "SELECT actor_id, display_name, email"
                " FROM datasette_user_profiles"
                " ORDER BY updated_at DESC"
                " LIMIT ?",
                [limit],
            )
        ).rows
    else:
        like = f"%{q}%"
        prefix = f"{q}%"
        # Match across display_name / email / actor_id; surface prefix
        # matches on display_name first, then alphabetical by display_name.
        rows = (
            await internal_db.execute(
                "SELECT actor_id, display_name, email"
                " FROM datasette_user_profiles"
                " WHERE display_name LIKE ? OR email LIKE ? OR actor_id LIKE ?"
                " ORDER BY CASE WHEN display_name LIKE ? THEN 0 ELSE 1 END,"
                " display_name"
                " LIMIT ?",
                [like, like, like, prefix, limit],
            )
        ).rows

    results = [
        SearchResult(
            id=row["actor_id"],
            display_name=row["display_name"],
            email=row["email"] if include_email else None,
            avatar_url=datasette.urls.path(f"/-/profile/pic/{row['actor_id']}"),
            kind="user",
        )
        for row in rows
    ]

    return Response.json(SearchResponse(results=results).model_dump())


@router.GET("/-/profiles/api/resolve$", output=ResolveResponse)
@check_permission()
async def api_resolve(datasette, request):
    """Batch-resolve known actor ids to profile dicts (HTTP sibling of the
    in-process ``resolve_profile_actors`` helper).

    Unlike search, this takes a known set of ids (``?ids=clark,lois,bruce``)
    and returns them keyed by id. Unknown ids are omitted from ``results`` —
    the caller applies its own fallback for anything still unresolved.
    """
    # Accept comma-separated ids in one or more repeated `ids` params.
    raw = ",".join(request.args.getlist("ids"))
    ids = [part for part in (p.strip() for p in raw.split(",")) if part]

    # Mirror search: email is included by default but can be omitted.
    include_email = _truthy(request.args.get("email"), default=True)

    actors = await resolve_profile_actors(datasette, ids)
    results = {
        actor_id: SearchResult(
            id=actor["id"],
            display_name=actor["display_name"],
            email=actor["email"] if include_email else None,
            avatar_url=actor["avatar_url"],
            kind=actor["kind"],
        )
        for actor_id, actor in actors.items()
    }

    return Response.json(ResolveResponse(results=results).model_dump())


@router.GET("/-/api/user-profile/photo/(?P<actor_id>[^/]+)$")
@check_permission()
async def api_get_photo(datasette, request, actor_id: str):
    internal_db = datasette.get_internal_database()
    row = (
        await internal_db.execute(
            "SELECT photo, content_type FROM datasette_user_profile_photos WHERE actor_id = ?",
            [actor_id],
        )
    ).first()
    if row is not None:
        return Response(
            body=row["photo"],
            content_type=row["content_type"],
            headers={"Cache-Control": "max-age=300"},
        )
    return Response.text("Photo not found", status=404)
