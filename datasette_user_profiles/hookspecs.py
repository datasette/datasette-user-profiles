from dataclasses import dataclass, field
from pluggy import HookspecMarker

hookspec = HookspecMarker("datasette")


@dataclass
class ProfileSection:
    """A section contributed by a plugin to a user profile page."""

    id: str  # unique key, e.g. "comments"
    label: str  # display name, e.g. "Comments"
    tag_name: str  # web component tag, e.g. "user-profile-comments"
    js_url: str | None = None  # single JS URL (use js_urls for multiple)
    js_urls: list[str] = field(default_factory=list)  # multiple JS URLs (e.g. vite client + entry)
    css_url: str | None = None
    css_urls: list[str] = field(default_factory=list)
    sort_order: int = 100
    icon: str | None = None  # raw SVG markup to render next to the section heading  # lower = higher on page

    def all_js_urls(self) -> list[str]:
        urls = list(self.js_urls)
        if self.js_url and self.js_url not in urls:
            urls.append(self.js_url)
        return urls

    def all_css_urls(self) -> list[str]:
        urls = list(self.css_urls)
        if self.css_url and self.css_url not in urls:
            urls.append(self.css_url)
        return urls


@hookspec
def datasette_user_profile_sections(datasette):
    """
    Register extra sections on user profile pages.

    Returns a list of ProfileSection instances. Each section provides a
    custom element tag name and a JS bundle URL that defines it. The
    profile page will load the JS and render:

        <tag-name actor-id="..." />

    The custom element is responsible for fetching its own data and
    rendering its own UI.
    """


@dataclass
class ProfileSeed:
    """A pre-existing profile contributed by a plugin to seed the directory.

    Plugins that already know about people (an auth backend, a debug actor
    set, a directory exported as JSON) return these from
    ``datasette_user_profile_seeds`` so their users appear in the profiles
    directory, people-search and avatar endpoints without anyone having to
    visit the edit page first.

    Only ``actor_id`` is required. A photo can be supplied either as raw
    ``photo_bytes`` (with ``photo_content_type``) or as a ``data:`` URL in
    ``photo_url``, which core decodes. Remote (``http(s)://``) photos are not
    fetched by core — fetch them in your plugin and pass ``photo_bytes``.
    """

    actor_id: str
    display_name: str | None = None
    bio: str | None = None
    email: str | None = None
    avatar_icon: str | None = None
    avatar_color: str | None = None
    photo_url: str | None = None  # data: URL, decoded by core
    photo_bytes: bytes | None = None
    photo_content_type: str | None = None


@hookspec
def datasette_user_profile_seeds(datasette):
    """
    Contribute pre-existing profiles to seed the profiles directory.

    Return a list of ProfileSeed instances (plain dicts are also accepted and
    coerced; ``id`` is treated as an alias for ``actor_id``). You may instead
    return an awaitable, or a zero-argument callable returning a list or
    awaitable, so a plugin can do async work (e.g. fetch a JSON file) before
    producing its seeds.

    Seeding runs once at startup and is *fill-missing*: a new actor is inserted
    with everything you provide, but for an actor that already exists each field
    is only filled when it is currently empty. Seeds never overwrite a value a
    user has set, and an existing photo is never replaced. Seeding is therefore
    idempotent and safe to run on every restart.
    """
