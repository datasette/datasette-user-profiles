import json

from datasette import hookimpl
from datasette.permissions import Action
from datasette.plugins import pm
from datasette_vite import vite_entry

from . import hookspecs
from .avatar import avatar_url

pm.add_hookspecs(hookspecs)

from .router import router, PROFILE_ACCESS_NAME


@hookimpl
def register_routes():
    return router.routes()


async def resolve_profile_actors(datasette, actor_ids):
    """Resolve actor IDs to profile actor dictionaries.

    Returns a ``{actor_id: {...}}`` map for the IDs that have a matching
    profile. IDs without a profile are simply omitted, so callers can merge
    this result with other identity sources and apply their own fallback for
    anything still unresolved. Each known user resolves to::

        {
            "id": "alice",
            "display_name": "Alice Anderson",
            "email": "alice@example.com",
            "kind": "user",
            "avatar_url": "/-/profile/pic/alice?v=2026-05-20T00:00:00.000",
            "bio": "Builds things.",
        }

    ``avatar_url`` is ``None`` when the user has no photo and no valid icon
    avatar (so the URL would 404). Otherwise it carries a ``?v=`` version
    stamp that changes whenever the picture does, so it is safe to cache.

    This plugin deliberately does **not** implement Datasette's core
    ``actors_from_ids`` plugin hook. That hook is ``firstresult=True``, so any
    plugin implementing it locks out every other identity source. Instead, opt
    in from your own plugin if you want profiles to back actor resolution::

        from datasette import hookimpl
        from datasette_user_profiles import resolve_profile_actors

        @hookimpl
        def actors_from_ids(datasette, actor_ids):
            async def inner():
                actors = await resolve_profile_actors(datasette, actor_ids)
                # merge in your other identity sources here, then default the rest
                for actor_id in actor_ids:
                    actors.setdefault(str(actor_id), {"id": str(actor_id)})
                return actors
            return inner
    """
    ids = [str(a) for a in actor_ids]
    if not ids:
        return {}

    internal_db = datasette.get_internal_database()
    rows = (
        await internal_db.execute(
            "select p.actor_id, p.display_name, p.email, p.bio,"
            " p.avatar_icon, p.avatar_color, p.updated_at,"
            " ph.updated_at as photo_updated_at"
            " from datasette_user_profiles p"
            " left join datasette_user_profile_photos ph on ph.actor_id = p.actor_id"
            " where p.actor_id in (select value from json_each(:ids))",
            {"ids": json.dumps(ids)},
        )
    ).rows
    result = {}
    for r in rows:
        actor_id = r["actor_id"]
        result[actor_id] = {
            "id": actor_id,
            "display_name": r["display_name"],
            "email": r["email"],
            "kind": "user",
            "avatar_url": avatar_url(
                datasette,
                actor_id,
                photo_updated_at=r["photo_updated_at"],
                avatar_icon=r["avatar_icon"],
                avatar_color=r["avatar_color"],
                profile_updated_at=r["updated_at"],
            ),
            "bio": r["bio"],
        }
    return result


def hovercard_script_url(datasette) -> str:
    """URL of the profile hovercard script, for server-rendered templates::

        <script type="module" src="{{ hovercard_script_url }}"></script>

    It redirects to the built (or Vite dev server) module, and honours
    ``base_url``.
    """
    return datasette.urls.path("/-/profiles/hovercard.js")


# Import route modules to trigger route registration on the shared router.
# This happens after resolve_profile_actors is defined above so that
# routes.api can import it at module level without a circular import.
from .routes import pages, api  # noqa: E402

_ = (pages, api)


def _datasette_acl_installed():
    """True if datasette-acl is importable in this environment."""
    try:
        import datasette_acl  # noqa: F401
    except ImportError:
        return False
    return True


def _valid_actors_impl(datasette):
    """Return every known profile as an acl ``{"id", "display"}`` actor dict.

    Shared logic for the optional ``datasette_acl_valid_actors`` hookimpl.
    Kept as a standalone function so it can be exercised independently of
    whether ``datasette_acl`` is importable.
    """

    async def inner():
        internal_db = datasette.get_internal_database()
        rows = (
            await internal_db.execute(
                "select actor_id, display_name"
                " from datasette_user_profiles"
                " order by display_name"
            )
        ).rows
        return [
            {"id": r["actor_id"], "display": r["display_name"] or r["actor_id"]}
            for r in rows
        ]

    return inner


if _datasette_acl_installed():

    @hookimpl
    def datasette_acl_valid_actors(datasette):
        """Optional: feed acl's actor autocomplete from the profiles directory.

        acl's admin UI (group/permission editors) calls
        ``datasette_acl_valid_actors`` to populate its actor picker. We return
        every known profile as an ``{"id", "display"}`` dict so acl's standalone
        admin pages get nicer displays without needing the richer search API.

        This hookimpl is only registered when ``datasette_acl`` is importable,
        so profiles imposes no hard dependency on acl. The share dialog uses the
        richer ``/-/profiles/api/search`` endpoint instead of this hook.
        """

        return _valid_actors_impl(datasette)


@hookimpl
def extra_template_vars(datasette):
    entry = vite_entry(
        datasette=datasette,
        plugin_package="datasette_user_profiles",
    )
    return {"datasette_user_profiles_vite_entry": entry}


@hookimpl
def register_actions(datasette):
    return [
        Action(
            name=PROFILE_ACCESS_NAME,
            description="Can access user profile features",
        ),
    ]


@hookimpl
def menu_links(datasette, actor):
    async def inner():
        if actor and await datasette.allowed(action=PROFILE_ACCESS_NAME, actor=actor):
            actor_id = actor.get("id")
            if actor_id:
                return [
                    {
                        "href": datasette.urls.path(f"/-/profile/{actor_id}"),
                        "label": "Your profile",
                    },
                ]
        return []

    return inner


@hookimpl
def startup(datasette):
    """Apply internal migrations for user profiles tables."""

    async def inner():
        from sqlite_utils import Database as SqliteUtilsDatabase
        from .internal_migrations import internal_migrations
        from .seed import apply_seeds

        def migrate(conn):
            db = SqliteUtilsDatabase(conn)
            internal_migrations.apply(db)

        await datasette.get_internal_database().execute_write_fn(migrate)

        # Let other plugins seed the directory once the tables exist.
        await apply_seeds(datasette)

    return inner
