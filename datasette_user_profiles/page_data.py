from pydantic import BaseModel, ConfigDict


class UserProfile(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    actor_id: str
    display_name: str | None = None
    bio: str | None = None
    email: str | None = None
    has_photo: bool = False
    avatar_icon: str | None = None
    avatar_color: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProfileSectionData(BaseModel):
    id: str
    label: str
    tag_name: str
    js_urls: list[str] = []
    css_urls: list[str] = []
    sort_order: int = 100
    icon: str | None = None


# /-/profile/<actor_id> — public profile view
class ProfilePageData(BaseModel):
    profile: UserProfile
    is_own_profile: bool = False
    sections: list[ProfileSectionData] = []


# /-/user-profile/edit — edit your own profile
class EditProfilePageData(BaseModel):
    profile: UserProfile
    avatar_icon_choices: list[str] = []
    avatar_color_choices: dict[str, str] = {}
    avatar_icon_svgs: dict[str, str] = {}


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
    avatar_icon: str | None = None
    avatar_color: str | None = None


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
    ProfileSectionData,
]
