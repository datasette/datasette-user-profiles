from functools import wraps

from datasette import Forbidden
from datasette_plugin_router import Router

router = Router()

PROFILE_ACCESS_NAME = "profile_access"


def check_permission():
    """Decorator for routes requiring profile access."""

    def decorator(func):
        @wraps(func)
        async def wrapper(datasette, request, **kwargs):
            result = await datasette.allowed(
                action=PROFILE_ACCESS_NAME, actor=request.actor
            )
            if not result:
                raise Forbidden("Permission denied for profile access")
            return await func(datasette=datasette, request=request, **kwargs)

        return wrapper

    return decorator
