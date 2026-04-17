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
    sort_order: int = 100  # lower = higher on page

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
