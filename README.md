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
