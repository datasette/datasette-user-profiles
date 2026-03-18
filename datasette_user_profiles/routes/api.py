import base64
from typing import Annotated

from datasette import Response
from datasette_plugin_router import Body

from ..page_data import (
    DeletePhotoResponse,
    UpdateProfileRequest,
    UpdateProfileResponse,
    UploadPhotoRequest,
    UploadPhotoResponse,
)
from ..router import router, check_permission


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

    internal_db = datasette.get_internal_database()

    def write(conn):
        with conn:
            # Upsert the profile
            conn.execute(
                """
                INSERT INTO datasette_user_profiles (actor_id, display_name, bio, email)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    bio = excluded.bio,
                    email = excluded.email,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                """,
                [actor_id, body.display_name, body.bio, body.email],
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

    try:
        photo_bytes = base64.b64decode(body.photo_data)
    except Exception:
        return Response.json(
            UploadPhotoResponse(ok=False, error="Invalid base64 data").model_dump(),
            status=400,
        )

    if len(photo_bytes) > 1048576:
        return Response.json(
            UploadPhotoResponse(
                ok=False, error="Photo exceeds 1MB limit"
            ).model_dump(),
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

    internal_db = datasette.get_internal_database()
    await internal_db.execute_write(
        "DELETE FROM datasette_user_profile_photos WHERE actor_id = ?",
        [actor_id],
    )
    return Response.json(DeletePhotoResponse(ok=True).model_dump())


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
