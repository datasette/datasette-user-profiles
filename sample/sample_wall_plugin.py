"""
Sample datasette plugin that adds a "Wall" section to user profiles.

Users can write a message on their own wall. The wall is visible to
anyone viewing their profile.

Install: place this file where Datasette can discover it as a plugin,
or add it to the plugins_dir.
"""

import json
import logging

from datasette import hookimpl, Response
from datasette_user_profiles.hookspecs import ProfileSection
from sqlite_utils import Database as SqliteUtilsDatabase

logger = logging.getLogger("sample_wall_plugin")


WALL_TABLE = "sample_profile_walls"


@hookimpl
def startup(datasette):
    async def inner():
        def migrate(connection):
            db = SqliteUtilsDatabase(connection)
            if WALL_TABLE not in db.table_names():
                db[WALL_TABLE].create(
                    {
                        "actor_id": str,
                        "content": str,
                        "updated_at": str,
                    },
                    pk="actor_id",
                )

        await datasette.get_internal_database().execute_write_fn(migrate)

    return inner


@hookimpl
def register_routes():
    return [
        (r"^/-/api/wall/update$", wall_update),
        (r"^/-/api/wall/get/(?P<actor_id>[^/]+)$", wall_get),
        (r"^/-/wall-component\.js$", wall_component_js),
    ]


async def wall_get(datasette, request):
    actor_id = request.url_vars["actor_id"]
    internal_db = datasette.get_internal_database()
    row = (
        await internal_db.execute(
            f"SELECT content, updated_at FROM {WALL_TABLE} WHERE actor_id = ?",
            [actor_id],
        )
    ).first()
    if row:
        return Response.json(
            {"content": row["content"], "updated_at": row["updated_at"]}
        )
    return Response.json({"content": None, "updated_at": None})


async def wall_update(datasette, request):
    logger.info("wall_update called, method=%s", request.method)
    if request.method != "POST":
        return Response.json({"error": "POST required"}, status=405)

    logger.info("actor=%s", request.actor)
    if not request.actor:
        return Response.json({"error": "Not authenticated"}, status=403)

    actor_id = request.actor.get("id")
    if not actor_id:
        return Response.json({"error": "Actor has no id"}, status=403)

    body = await request.post_body()
    logger.info("raw body=%s", body)
    data = json.loads(body)
    content = data.get("content", "")
    logger.info("actor_id=%s content=%r", actor_id, content)

    internal_db = datasette.get_internal_database()
    logger.info("internal_db=%s", internal_db.name)

    def write(connection):
        logger.info("write callback called, connection=%s", connection)
        try:
            with connection:
                connection.execute(
                    f"""
                    INSERT INTO {WALL_TABLE} (actor_id, content, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(actor_id) DO UPDATE SET
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    [actor_id, content],
                )
            logger.info("write succeeded")
        except Exception:
            logger.exception("write failed")
            raise

    await internal_db.execute_write_fn(write)
    logger.info("execute_write_fn returned")
    return Response.json({"ok": True})


async def wall_component_js(datasette, request):
    return Response(
        body=WALL_COMPONENT_JS,
        content_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600"},
    )


WALL_COMPONENT_JS = r"""
import { h, render, Component } from "https://esm.sh/preact@10.25.4";
import { useState, useEffect } from "https://esm.sh/preact@10.25.4/hooks";
import { html } from "https://esm.sh/htm@3.1.1/preact";
import register from "https://esm.sh/preact-custom-element@4.3.0?bundle-deps&deps=preact@10.25.4";

function ProfileWall(props) {
  const actorId = props["actor-id"];
  const isOwn = props["is-own-profile"] === "true";
  const [content, setContent] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`/-/api/wall/get/${encodeURIComponent(actorId)}`)
      .then((r) => r.json())
      .then((data) => {
        setContent(data.content);
        setDraft(data.content || "");
        setLoading(false);
      });
  }, [actorId]);

  const save = async () => {
    setSaving(true);
    const csrfToken = document.querySelector('input[name="csrftoken"]')?.value
      || document.cookie.match(/ds_csrftoken=([^;]+)/)?.[1]
      || "";
    await fetch("/-/api/wall/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: draft, csrftoken: csrfToken }),
    });
    setContent(draft);
    setEditing(false);
    setSaving(false);
  };

  const cancel = () => {
    setDraft(content || "");
    setEditing(false);
  };

  if (loading) {
    return html`<p style="color: #888; font-size: 0.9rem;">Loading...</p>`;
  }

  if (editing) {
    return html`
      <div class="wall-edit">
        <textarea
          value=${draft}
          onInput=${(e) => setDraft(e.target.value)}
          rows="4"
          style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; font-size: 0.9rem; resize: vertical;"
          placeholder="Write something on your wall..."
        />
        <div style="display: flex; gap: 8px; margin-top: 8px;">
          <button
            onClick=${save}
            disabled=${saving}
            style="padding: 6px 16px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;"
          >
            ${saving ? "Saving..." : "Save"}
          </button>
          <button
            onClick=${cancel}
            style="padding: 6px 16px; background: #f5f5f5; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; font-size: 0.85rem;"
          >
            Cancel
          </button>
        </div>
      </div>
    `;
  }

  if (!content) {
    if (isOwn) {
      return html`
        <div>
          <p style="color: #888; font-size: 0.9rem; margin: 0 0 8px;">No wall post yet.</p>
          <button
            onClick=${() => setEditing(true)}
            style="padding: 6px 16px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; font-size: 0.85rem;"
          >
            Write something
          </button>
        </div>
      `;
    }
    return html`<p style="color: #888; font-size: 0.9rem; margin: 0;">Nothing here yet.</p>`;
  }

  return html`
    <div>
      <div style="white-space: pre-wrap; font-size: 0.95rem; line-height: 1.5;">${content}</div>
      ${isOwn && html`
        <button
          onClick=${() => setEditing(true)}
          style="margin-top: 8px; padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; font-size: 0.8rem; color: #666;"
        >
          Edit
        </button>
      `}
    </div>
  `;
}

register(ProfileWall, "profile-wall", ["actor-id", "is-own-profile"], { shadow: false });
"""


@hookimpl
def menu_links(datasette, actor):
    async def inner():
        if actor:
            actor_id = actor.get("id")
            if actor_id:
                return [
                    {
                        "href": datasette.urls.path(
                            f"/-/profile/{actor_id}#wall"
                        ),
                        "label": "Edit your wall",
                    },
                ]
        return []

    return inner


@hookimpl
def datasette_user_profile_sections(datasette):
    return [
        ProfileSection(
            id="wall",
            label="Wall",
            tag_name="profile-wall",
            js_url="/-/wall-component.js",
            sort_order=50
        ),
    ]
