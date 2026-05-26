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

### 2. `actors_from_ids` output shape

`datasette.actors_from_ids([...])` (resolved by this plugin, see below) returns
a `{actor_id: {...}}` map. Known users resolve to:

```json
{
  "id": "alice",
  "display_name": "Alice Anderson",
  "email": "alice@example.com",
  "kind": "user",
  "avatar_url": "/-/profile/pic/alice"
}
```

IDs that neither profiles nor any `datasette_resolve_actors` implementation
recognise default to a bare `{"id": <id>}`.

### 3. `datasette_resolve_actors` sub-hook

Other identity sources contribute resolved actors through this sub-hook (see
"Actor resolution" below). This is how agents and service accounts add
themselves to the directory without colliding with the single-owner
`actors_from_ids` hook.

### Consolidation note

This directory replaces three previously-scattered user-listing mechanisms:

| Old mechanism | Now drawn from |
|---|---|
| acl `datasette_acl_valid_actors` (no query, all actors) | the profiles search API (acl admin UI may keep the hook as a fallback) |
| comments `datasette_comments_users` hook + `startswith` filtering | the profiles search API |
| comments' private `from datasette_user_profiles.routes.pages import get_profile` | `datasette.actors_from_ids(...)` |

The old hooks keep working for one release as a fallback when profiles is not
installed, then they are retired.

As a cheap convenience, when `datasette-acl` is installed this plugin also
implements acl's `datasette_acl_valid_actors` hook, returning every profile as
an `{"id", "display"}` dict so acl's standalone admin pages get nicer displays.
That hookimpl is only registered if `datasette_acl` is importable, so profiles
has no hard dependency on acl.

## Actor resolution (`actors_from_ids`)

This plugin is the **single designated owner** of Datasette's core
`actors_from_ids` hook. Because that hook is declared `firstresult=True`, only
one plugin may implement it — if two plugins implement core `actors_from_ids`
they collide and only one result is used. In this stack, `datasette-user-profiles`
owns it: it resolves known users (with `display_name`, `email`, `kind: "user"`,
and an `avatar_url` of `/-/profile/pic/<id>`), then defaults any unresolved ID
to `{"id": <id>}`.

Other identity sources — agents, service accounts, remote directories — must
**not** implement core `actors_from_ids` themselves. Instead they implement the
`datasette_resolve_actors` sub-hook provided by this plugin:

```python
from datasette import hookimpl

@hookimpl
def datasette_resolve_actors(datasette, actor_ids):
    # actor_ids only contains IDs profiles could not resolve itself.
    # Return a (partial) {actor_id: {...}} map for the IDs you own.
    return {
        "agent-1": {
            "id": "agent-1",
            "display_name": "Research Agent",
            "avatar_url": "/-/agents/pic/agent-1",
            "kind": "agent",
        },
    }
```

profiles aggregates every `datasette_resolve_actors` implementation, so any
feature calling `datasette.actors_from_ids(...)` gets names and avatars for
users and contributed identities alike. If a deployment needs a different
`actors_from_ids` owner, it should disable this plugin's implementation rather
than register a second one.

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
