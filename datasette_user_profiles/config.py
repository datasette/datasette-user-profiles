"""Plugin configuration helpers."""

# Profile fields whose user-editability can be toggled via plugin config.
# "avatar" covers both the generated icon/color and an uploaded photo.
EDITABLE_FIELD_NAMES = ("display_name", "bio", "email", "avatar")


def editable_fields(datasette) -> dict[str, bool]:
    """Return a ``{field: bool}`` map of which profile fields users may edit.

    Controlled by plugin config. Every field defaults to ``True`` (editable),
    so a field is only locked when explicitly turned off. This lets a
    deployment whose actor JSON already carries authoritative values (e.g. a
    GitHub auth plugin that sets ``email``) stop users from overwriting them::

        plugins:
          datasette-user-profiles:
            editable_fields:
              email: false
              avatar: false
    """
    config = datasette.plugin_config("datasette-user-profiles") or {}
    overrides = config.get("editable_fields") or {}
    return {name: bool(overrides.get(name, True)) for name in EDITABLE_FIELD_NAMES}
