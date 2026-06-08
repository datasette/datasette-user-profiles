from datasette import hookimpl
from datasette.permissions import Action
from datasette.plugins import pm
from datasette.utils import await_me_maybe
from datasette_vite import vite_entry

from . import hookspecs

pm.add_hookspecs(hookspecs)

# Import route modules to trigger route registration on the shared router
from .routes import pages, api
from .router import router, PROFILE_ACCESS_NAME

_ = (pages, api)


@hookimpl
def register_routes():
    return router.routes()


@hookimpl
def actors_from_ids(datasette, actor_ids):
    """Resolve actor IDs to actor dictionaries.

    profiles is the single designated owner of this core hook (it is
    ``firstresult=True``). We resolve our own users from
    ``datasette_user_profiles`` and delegate any remaining IDs to other
    identity sources via the ``datasette_user_profiles_resolve_actors`` sub-hook.
    """

    async def inner():
        ids = [str(a) for a in actor_ids]
        result = {}
        if not ids:
            return result

        # 1. Our own users.
        internal_db = datasette.get_internal_database()
        placeholders = ",".join("?" * len(ids))
        rows = (
            await internal_db.execute(
                "select actor_id, display_name, email"
                " from datasette_user_profiles"
                " where actor_id in ({})".format(placeholders),
                ids,
            )
        ).rows
        for r in rows:
            actor_id = r["actor_id"]
            result[actor_id] = {
                "id": actor_id,
                "display_name": r["display_name"],
                "email": r["email"],
                "kind": "user",
                "avatar_url": datasette.urls.path(f"/-/profile/pic/{actor_id}"),
            }

        # 2. Delegate the rest to other identity sources (agents, service
        #    accounts, remote directories, ...).
        missing = [i for i in ids if i not in result]
        if missing:
            for hook_result in pm.hook.datasette_user_profiles_resolve_actors(
                datasette=datasette, actor_ids=missing
            ):
                hook_result = await await_me_maybe(hook_result)
                if hook_result:
                    result.update(hook_result)

        # 3. Default for anything still unresolved.
        for i in ids:
            result.setdefault(i, {"id": i})

        return result

    return inner


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
                        "href": datasette.urls.path(
                            f"/-/profile/{actor_id}"
                        ),
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

        def migrate(conn):
            db = SqliteUtilsDatabase(conn)
            internal_migrations.apply(db)

        await datasette.get_internal_database().execute_write_fn(migrate)

    return inner
