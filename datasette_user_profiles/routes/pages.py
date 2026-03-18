from pydantic import BaseModel

from datasette import Response

from ..page_data import (
    EditProfilePageData,
    ProfilePageData,
    ProfilesPageData,
    UserProfile,
)

from ..router import router, check_permission


async def render_page(
    datasette, request, *, page_title: str, entrypoint: str, page_data: BaseModel
) -> Response:
    return Response.html(
        await datasette.render_template(
            "user_profiles_base.html",
            {
                "page_title": page_title,
                "entrypoint": entrypoint,
                "page_data": page_data.model_dump(),
            },
            request=request,
        )
    )


async def get_profile(datasette, actor_id: str) -> UserProfile:
    """Load a user profile from the internal database."""
    internal_db = datasette.get_internal_database()

    row = (
        await internal_db.execute(
            "SELECT actor_id, display_name, bio, email, created_at, updated_at"
            " FROM datasette_user_profiles WHERE actor_id = ?",
            [actor_id],
        )
    ).first()

    if row is None:
        return UserProfile(actor_id=actor_id)

    photo_row = (
        await internal_db.execute(
            "SELECT 1 FROM datasette_user_profile_photos WHERE actor_id = ?",
            [actor_id],
        )
    ).first()

    return UserProfile(
        actor_id=row["actor_id"],
        display_name=row["display_name"],
        bio=row["bio"],
        email=row["email"],
        has_photo=photo_row is not None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.GET("/-/profiles/$")
@check_permission()
async def profiles_page(datasette, request):
    internal_db = datasette.get_internal_database()

    rows = (
        await internal_db.execute(
            "SELECT p.actor_id, p.display_name, p.bio, p.email, p.created_at, p.updated_at,"
            " (SELECT 1 FROM datasette_user_profile_photos ph WHERE ph.actor_id = p.actor_id) AS has_photo"
            " FROM datasette_user_profiles p"
            " ORDER BY p.updated_at DESC"
        )
    ).rows

    profiles = [
        UserProfile(
            actor_id=row["actor_id"],
            display_name=row["display_name"],
            bio=row["bio"],
            email=row["email"],
            has_photo=row["has_photo"] is not None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    current_actor_id = request.actor.get("id") if request.actor else None

    return await render_page(
        datasette,
        request,
        page_title="Profiles",
        entrypoint="src/pages/profiles/index.ts",
        page_data=ProfilesPageData(
            profiles=profiles,
            has_own_profile=any(
                p.actor_id == current_actor_id for p in profiles
            ),
            current_actor_id=current_actor_id,
        ),
    )


@router.GET("/-/profile/(?P<actor_id>[^/]+)$")
@check_permission()
async def profile_page(datasette, request, actor_id: str):
    profile = await get_profile(datasette, actor_id)
    current_actor_id = request.actor.get("id") if request.actor else None
    is_own = current_actor_id == actor_id

    page_title = profile.display_name or actor_id
    return await render_page(
        datasette,
        request,
        page_title=page_title,
        entrypoint="src/pages/profile/index.ts",
        page_data=ProfilePageData(
            profile=profile,
            is_own_profile=is_own,
        ),
    )


@router.GET("/-/profile/pic/(?P<actor_id>[^/]+)$")
@check_permission()
async def profile_pic(datasette, request, actor_id: str):
    internal_db = datasette.get_internal_database()
    row = (
        await internal_db.execute(
            "SELECT photo, content_type, updated_at"
            " FROM datasette_user_profile_photos WHERE actor_id = ?",
            [actor_id],
        )
    ).first()
    if row is not None:
        return Response(
            body=row["photo"],
            content_type=row["content_type"],
            headers={
                "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
                "ETag": f'"{hash(row["updated_at"])}"',
            },
        )
    return Response.text("Photo not found", status=404)


@router.GET("/-/user-profile/edit$")
@check_permission()
async def edit_profile_page(datasette, request):
    if not request.actor:
        return Response.text("Not authenticated", status=403)
    actor_id = request.actor.get("id")
    if not actor_id:
        return Response.text("Actor has no id", status=403)

    profile = await get_profile(datasette, actor_id)

    return await render_page(
        datasette,
        request,
        page_title="Edit Profile",
        entrypoint="src/pages/edit_profile/index.ts",
        page_data=EditProfilePageData(profile=profile),
    )
