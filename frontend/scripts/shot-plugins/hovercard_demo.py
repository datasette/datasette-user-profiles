"""A host page for the hovercard screenshot.

Loaded via `datasette --plugins-dir` from frontend/scripts/screenshots.mjs. NOT
shipped — screenshot use only.

The hovercard is a thing other plugins embed, so screenshotting it needs a host
page to embed it in. `sample/sample_hovercard_demo.py` exists for that, but it's
a manual test harness — toggles, an event log, a 150vh spacer — which would make
a confusing README image. This renders the same component in the shape it's
actually meant for: a comment thread whose author names and @mentions carry
`data-profile-hovercard`.

Kept deliberately compact so the shot can clip to the content with no dead
space, and free of anything volatile (no timestamps).
"""

import html

from datasette import Response, hookimpl
from datasette_user_profiles import hovercard_script_url


@hookimpl
def register_routes():
    return [(r"^/-/shots/hovercard-demo$", hovercard_demo)]


async def hovercard_demo(datasette):
    def person(actor_id, label):
        href = html.escape(datasette.urls.path(f"/-/profile/{actor_id}"))
        return (
            f'<a class="author" href="{href}" data-profile-hovercard>'
            f"{html.escape(label)}</a>"
        )

    def mention(actor_id, label):
        return (
            f'<span class="mention" data-profile-hovercard="{html.escape(actor_id)}"'
            f' tabindex="0">{html.escape(label)}</span>'
        )

    return Response.html(
        PAGE.replace("{{script}}", html.escape(hovercard_script_url(datasette)))
        .replace("{{ada}}", person("ada", "Ada Lovelace"))
        .replace("{{katherine}}", person("katherine", "Katherine Johnson"))
        .replace("{{margaret}}", person("margaret", "Margaret Hamilton"))
        .replace("{{m_grace}}", mention("grace", "@grace"))
        .replace("{{m_alan}}", mention("alan", "@alan"))
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Hovercard</title>
<style>
  :root { color-scheme: light; }
  body {
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    margin: 0; padding: 28px; background: #f8f9fb; color: #1b1f29;
  }
  .demo { max-width: 620px; margin: 0 auto; }
  h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .06em;
       color: #6b7280; margin: 0 0 16px; }
  .comment { display: flex; gap: 12px; padding: 14px 0; border-top: 1px solid #e5e7eb; }
  .comment:first-of-type { border-top: 0; }
  .dot { flex: 0 0 34px; height: 34px; border-radius: 50%; }
  .body { flex: 1; min-width: 0; }
  .author { display: inline-block; font-weight: 600; color: #111827;
           text-decoration: none; }
  .author:hover { text-decoration: underline; }
  p { margin: 2px 0 0; }
  .mention { color: #1e66f5; background: #eaf0ff; border-radius: 4px;
             padding: 0 4px; cursor: default; }
</style>
<script type="module" src="{{script}}"></script>
</head>
<body>
<div class="demo">
  <h2>Comments</h2>

  <div class="comment">
    <div class="dot" style="background:#8839ef"></div>
    <div class="body">
      {{ada}}
      <p>Reran the tables with the new figures — {{m_grace}} the totals line up
        with yours now.</p>
    </div>
  </div>

  <div class="comment">
    <div class="dot" style="background:#d20f39"></div>
    <div class="body">
      {{katherine}}
      <p>Checked the trajectory by hand twice. Passing it to {{m_alan}} for a
        second opinion before it ships.</p>
    </div>
  </div>

  <div class="comment">
    <div class="dot" style="background:#fe640b"></div>
    <div class="body">
      {{margaret}}
      <!-- Kept short so it clears the open card's left edge: the card overlays
           this comment, and its bottom border slicing through a line of text
           reads as a rendering glitch in the screenshot. -->
      <p>Priority-display routine is in.</p>
    </div>
  </div>
</div>
</body>
</html>
"""
