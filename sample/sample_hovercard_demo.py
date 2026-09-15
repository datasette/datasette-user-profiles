"""
Sample plugin: a manual test page for the profile hovercard.

    just dev   ->   http://localhost:8006/-/profiles/hovercard-demo

Uses datasette-debug-gotham's actors (log in with an ``actor=clark`` cookie).
It also seeds bios for a few of them, one profile with no avatar (``perry``),
and names a no-profile actor (``build-bot``) through core ``actors_from_ids``.
"""

import html

from datasette import Response, hookimpl
from datasette_user_profiles import hovercard_script_url
from datasette_user_profiles.hookspecs import ProfileSeed

BIOS = {
    "clark": "Mild-mannered reporter at the Daily Planet. Rarely at his desk when "
    "something big happens.",
    "lois": "Investigative reporter. Two Pulitzers, zero patience for press releases.",
    "bruce": "Publisher of the Gotham Gazette. Keeps odd hours.",
}


@hookimpl
def datasette_user_profile_seeds(datasette):
    # Fill-missing semantics: these only add bios to gotham's seeded profiles.
    return [ProfileSeed(actor_id=k, bio=v) for k, v in BIOS.items()] + [
        ProfileSeed(
            actor_id="perry",
            display_name="Perry White",
            bio="Editor-in-chief. Great Caesar's ghost! (No profile picture.)",
        )
    ]


@hookimpl
def actors_from_ids(datasette, actor_ids):
    # firstresult: gotham skips this hook when user-profiles is installed, so
    # this is the only implementation under `just dev`.
    return {
        actor_id: {"id": actor_id, "name": "Build Bot"}
        if actor_id == "build-bot"
        else {"id": actor_id}
        for actor_id in actor_ids
    }


@hookimpl
def register_routes():
    return [(r"^/-/profiles/hovercard-demo$", hovercard_demo)]


async def hovercard_demo(datasette):
    def link(actor_id, label):
        href = html.escape(datasette.urls.path(f"/-/profile/{actor_id}"))
        return f'<a href="{href}" data-profile-hovercard>{html.escape(label)}</a>'

    return Response.html(
        PAGE.replace("{{script}}", html.escape(hovercard_script_url(datasette)))
        .replace("{{clark}}", link("clark", "Clark Kent"))
        .replace("{{jimmy}}", link("jimmy", "Jimmy Olsen"))
        .replace("{{bruce}}", link("bruce", "Bruce Wayne"))
        .replace("{{selina}}", link("selina", "Selina Kyle"))
        .replace("{{perry}}", link("perry", "Perry White"))
        .replace("{{right}}", link("alfred", "Alfred Pennyworth"))
        .replace("{{bottom}}", link("lois", "Lois Lane (bottom)"))
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hovercard demo</title>
<style>
  :root { color-scheme: light; }
  :root.dark { color-scheme: dark; }
  body { font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 720px;
         padding: 16px; background: light-dark(#fff, #16181c); color: light-dark(#111, #eee); }
  .editor { border: 1px solid #888; border-radius: 6px; padding: 12px; }
  .pm-mention { background: light-dark(#e8efff, #25324d); border-radius: 4px; padding: 0 3px; }
  .pm-mention.ProseMirror-selectednode { outline: 2px solid #1e66f5; }
  .right { text-align: right; }
  #log { font: 13px monospace; border: 1px dashed #888; padding: 6px; min-height: 1.5em; white-space: pre-wrap; }
  .spacer { height: 150vh; }
</style>
<script type="module" src="{{script}}"></script>
</head>
<body>
<h1>Profile hovercard demo</h1>
<p>
  <button id="theme">Toggle color-scheme</button>
</p>
<p id="links">
  Links: {{clark}}, {{jimmy}}, {{bruce}}, {{selina}}.
  No avatar: {{perry}}.
  No profile: <span id="bot" data-profile-hovercard="build-bot" tabindex="0">@build-bot</span>.
  Span trigger: <span id="lois" data-profile-hovercard="lois" tabindex="0">@lois</span>.
</p>

<h2>Fake editor</h2>
<div class="editor" id="editor" contenteditable="true">
  Hey <span class="pm-mention" contenteditable="false" data-profile-hovercard="lois">@Lois Lane</span>,
  can you check with <span class="pm-mention" contenteditable="false" data-profile-hovercard="jimmy">@Jimmy Olsen</span>?
</div>
<p>
  <button id="select-open">Node-select first mention + open event</button>
  <button id="close">Dispatch close event</button>
  <button id="rebuild">Rebuild mentions (clone)</button>
</p>

<h2>Document keydown log (stands in for a Sidebar)</h2>
<div id="log"></div>

<p class="right">Right edge: {{right}}</p>
<div class="spacer"></div>
<p>Near the bottom: {{bottom}}</p>
<div style="height: 40px"></div>

<script>
  const log = document.getElementById("log");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") log.textContent += "document saw Escape\\n";
  });
  document.getElementById("theme").addEventListener("click", () => {
    document.documentElement.classList.toggle("dark");
  });
  const mentions = () => document.querySelectorAll("#editor .pm-mention");
  document.getElementById("select-open").addEventListener("click", () => {
    mentions().forEach((m) => m.classList.remove("ProseMirror-selectednode"));
    const m = mentions()[0];
    m.classList.add("ProseMirror-selectednode");
    m.dispatchEvent(new CustomEvent("profile-hovercard:open", { bubbles: true }));
  });
  document.getElementById("close").addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("profile-hovercard:close"));
  });
  document.getElementById("rebuild").addEventListener("click", () => {
    mentions().forEach((m) => m.replaceWith(m.cloneNode(true)));
  });
</script>
</body>
</html>
"""
