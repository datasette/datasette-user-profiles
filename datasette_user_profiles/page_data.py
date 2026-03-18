from pydantic import BaseModel


class UserProfile(BaseModel):
    actor_id: str
    display_name: str | None = None
    bio: str | None = None
    email: str | None = None
    has_photo: bool = False
    created_at: str | None = None
    updated_at: str | None = None


# /-/profile/<actor_id> — public profile view
class ProfilePageData(BaseModel):
    profile: UserProfile
    is_own_profile: bool = False


# /-/user-profile/edit — edit your own profile
class EditProfilePageData(BaseModel):
    profile: UserProfile


# /-/profiles/ — list all profiles
class ProfilesPageData(BaseModel):
    profiles: list[UserProfile] = []
    has_own_profile: bool = False
    current_actor_id: str | None = None


# API models

class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    email: str | None = None


class UpdateProfileResponse(BaseModel):
    ok: bool
    error: str | None = None


class UploadPhotoRequest(BaseModel):
    photo_data: str  # base64-encoded image
    content_type: str = "image/jpeg"


class UploadPhotoResponse(BaseModel):
    ok: bool
    error: str | None = None


class DeletePhotoResponse(BaseModel):
    ok: bool
    error: str | None = None


__exports__ = [
    ProfilePageData,
    EditProfilePageData,
    ProfilesPageData,
]
