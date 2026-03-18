from datasette import hookimpl
from datasette.permissions import Action
from datasette_vite import vite_entry
import os

# Import route modules to trigger route registration on the shared router
from .routes import pages, api
from .router import router, PROFILE_ACCESS_NAME

_ = (pages, api)


@hookimpl
def register_routes():
    return router.routes()


@hookimpl
def extra_template_vars(datasette):
    entry = vite_entry(
        datasette=datasette,
        plugin_package="datasette_user_profiles",
        vite_dev_path=os.environ.get("DATASETTE_USER_PROFILES_VITE_PATH"),
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

        def migrate(connection):
            db = SqliteUtilsDatabase(connection)
            internal_migrations.apply(db)

        await datasette.get_internal_database().execute_write_fn(migrate)

    return inner
