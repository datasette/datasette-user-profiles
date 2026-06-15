# datasette-user-profiles

[![PyPI](https://img.shields.io/pypi/v/datasette-user-profiles.svg)](https://pypi.org/project/datasette-user-profiles/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-user-profiles?include_prereleases&label=changelog)](https://github.com/datasette/datasette-user-profiles/releases)
[![Tests](https://github.com/datasette/datasette-user-profiles/actions/workflows/test.yml/badge.svg)](https://github.com/datasette/datasette-user-profiles/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-user-profiles/blob/main/LICENSE)

Plugin to allow users to define their own profiles

## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-user-profiles
```
## Usage

Usage instructions go here.

## Acting as the actor directory

`datasette-user-profiles` is the canonical user directory for this stack. Every
"who are the users?" surface — the share dialog's add-a-collaborator box,
`@mentions`, acl's actor picker, author chips, audit "shared by" lines — draws
from this one indexed, agent-aware directory rather than maintaining its own
ad-hoc list. It exposes three consumer-facing contracts:

### 1. Search / autocomplete endpoint

```
GET /-/profiles/api/search?q=<text>&limit=<n>&email=<0|1>
```

Gated by the `profile_access` permission (the same gate as every other profile
endpoint). Parameters:

- `q` — free-text query. Matched (case-insensitively) against `display_name`,
  `email`, and `actor_id`. Empty/absent `q` returns the most-recently-updated
  profiles instead.
- `limit` — max results, defaults to `20`, capped at `50` (and floored at `1`).
- `email` — set to `0`/`false`/`no`/`off` to omit emails from results
  (defaults to including them).

Display-name prefix matches rank ahead of contains-only matches, then results
are alphabetical by `display_name`. Response shape:

```json
{
  "results": [
    {
      "id": "alice",
      "display_name": "Alice Anderson",
      "email": "alice@example.com",
      "avatar_url": "/-/profile/pic/alice",
      "kind": "user"
    }
  ]
}
```

`kind` is always `"user"` — profiles only knows users. Callers that also want
agents (or other identities) query those sources separately and merge
client-side; profiles stays decoupled from the agent directory.

### 2. `resolve_profile_actors()` output shape

`resolve_profile_actors(datasette, actor_ids)` (see "Actor resolution" below)
returns a `{actor_id: {...}}` map containing only the IDs that have a profile.
Known users resolve to:

```json
{
  "id": "alice",
  "display_name": "Alice Anderson",
  "email": "alice@example.com",
  "kind": "user",
  "avatar_url": "/-/profile/pic/alice"
}
```

IDs without a matching profile are omitted from the map — the caller decides
how to fall back (typically a bare `{"id": <id>}`).

### Consolidation note

This directory replaces three previously-scattered user-listing mechanisms:

| Old mechanism | Now drawn from |
|---|---|
| acl `datasette_acl_valid_actors` (no query, all actors) | the profiles search API (acl admin UI may keep the hook as a fallback) |
| comments `datasette_comments_users` hook + `startswith` filtering | the profiles search API |
| comments' private `from datasette_user_profiles.routes.pages import get_profile` | `resolve_profile_actors(...)` |

The old hooks keep working for one release as a fallback when profiles is not
installed, then they are retired.

As a cheap convenience, when `datasette-acl` is installed this plugin also
implements acl's `datasette_acl_valid_actors` hook, returning every profile as
an `{"id", "display"}` dict so acl's standalone admin pages get nicer displays.
That hookimpl is only registered if `datasette_acl` is importable, so profiles
has no hard dependency on acl.

## Actor resolution (`resolve_profile_actors`)

This plugin **does not** implement Datasette's core `actors_from_ids` hook.
That hook is declared `firstresult=True`, so the first plugin to implement it
wins and every other identity source (agents, service accounts, remote
directories) is locked out. Rather than silently seize that hook just by being
installed, profiles exposes its resolution logic as a plain function you can
opt into:

```python
from datasette_user_profiles import resolve_profile_actors

actors = await resolve_profile_actors(datasette, ["alice", "agent-1"])
# {"alice": {"id": "alice", "display_name": "Alice Anderson",
#            "email": "alice@example.com", "kind": "user",
#            "avatar_url": "/-/profile/pic/alice"}}
```

It returns a `{actor_id: {...}}` map for the IDs that have a profile, and omits
the rest so you can merge it with other sources and apply your own fallback.

If you want profiles to back Datasette's core `actors_from_ids`, wire it up
from a plugin you control — designating a single owner for the hook and
choosing how to merge other identity sources:

```python
from datasette import hookimpl
from datasette_user_profiles import resolve_profile_actors

@hookimpl
def actors_from_ids(datasette, actor_ids):
    async def inner():
        actors = await resolve_profile_actors(datasette, actor_ids)
        # ...merge in agents / service accounts / other directories here...
        for actor_id in actor_ids:
            actors.setdefault(str(actor_id), {"id": str(actor_id)})
        return actors
    return inner
```

## Development

To set up this plugin locally, first checkout the code. You can confirm it is available like this:
```bash
cd datasette-user-profiles
# Confirm the plugin is visible
uv run datasette plugins
```
To run the tests:
```bash
uv run pytest
```
