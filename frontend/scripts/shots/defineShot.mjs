// defineShot turns a declarative descriptor into the `async (browser) => {…}`
// the runner calls, owning the per-shot boilerplate: open a fresh browser
// context (signed in as the shot's actor) → navigate → interact → freeze →
// capture → close.
//
// Each shot gets its own context rather than sharing one, so the ds_actor
// cookie is stamped per shot and nothing (cookies, localStorage, a dialog left
// open) can leak between shots. The plugin's pages are all read-only here — no
// shot mutates a profile — so `order` has no correctness effect; it just keeps
// the run log in a readable sequence and matches the sibling plugins'
// discovery contract.
//
// No dark-theme twins: the profiles frontend has no prefers-color-scheme or
// data-theme handling of its own (the hovercard, added separately, follows the
// *host* page's color-scheme), so there is no second leg to capture.
//
// Descriptor fields:
//   name    (required) — output PNG base name; MUST equal the shot's file name
//                        (asserted by the runner in screenshots.mjs).
//   actor   — the ds_actor cookie's actor id (default ACTOR from config).
//   order   — run sequence (ascending); ties broken by name.
//   goto    — async (page, {ctx}) for navigation; default is the profiles
//             directory at /-/profiles/.
//   prepare — async (page, {ctx}) interaction + waits after navigation.
//   freeze  — default true; runs freezeVolatile before capturing.
//   capture — async (page, file, {ctx}); default = shotPage, a full-width
//             capture trimmed to the footer. Use for dialog-only captures
//             (shotUnion in helpers.mjs).
import { signActorCookie } from "./cookie.mjs";
import {
  STABILITY_CSS,
  freezeVolatile,
  stubRandom,
  shotPage,
} from "./helpers.mjs";
import { VIEWPORT, DEVICE_SCALE_FACTOR, BASE, ACTOR, out } from "./config.mjs";

export function defineShot(desc) {
  const {
    name,
    actor = ACTOR,
    order = 0,
    goto,
    prepare,
    capture,
    freeze = true,
  } = desc;
  if (!name) throw new Error("defineShot: missing `name`");

  const run = async (browser) => {
    const ctx = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: DEVICE_SCALE_FACTOR,
      // STABILITY_CSS below is injected into the document, and a document
      // stylesheet cannot reach inside a shadow root — so the hovercard's
      // 120ms fade/slide would still be in flight when we captured it. The
      // component already honours prefers-reduced-motion, and a media query
      // does apply inside shadow roots, so ask for reduced motion at the
      // context level and let the component's own escape hatch do the work.
      reducedMotion: "reduce",
    });
    // Re-inject the stability stylesheet on every navigation (addStyleTag on a
    // single page wouldn't survive page.goto). The very first invocation (the
    // context's initial about:blank document) can run before
    // document.documentElement exists at all — if that threw it would abort the
    // whole init script and the DOMContentLoaded listener below would never
    // register, so it bails out quietly instead and lets the retry do the work.
    await ctx.addInitScript((css) => {
      const inject = () => {
        if (document.getElementById("__shots_stability")) return;
        const target = document.head || document.documentElement;
        if (!target) return;
        const s = document.createElement("style");
        s.id = "__shots_stability";
        s.textContent = css;
        target.appendChild(s);
      };
      inject();
      document.addEventListener("DOMContentLoaded", inject);
    }, STABILITY_CSS);
    await ctx.addCookies([
      {
        name: "ds_actor",
        value: signActorCookie(actor),
        domain: "localhost",
        path: "/",
      },
    ]);
    const page = await ctx.newPage();
    try {
      await stubRandom(page);
      if (goto) await goto(page, { ctx });
      else await page.goto(`${BASE}/-/profiles/`);
      if (prepare) await prepare(page, { ctx });
      if (freeze) await freezeVolatile(page);
      if (capture) await capture(page, out(name), { ctx });
      else await shotPage(page, out(name));
    } finally {
      await ctx.close();
    }
  };
  run.shotName = name;
  run.order = order;
  return run;
}
