// Page-stabilization + capture helpers shared by every shot definition.
import { VIEWPORT } from "./config.mjs";

// Injected on every shot's context (see defineShot.mjs) so it's present from
// first paint: kills the blinking caret and disables transitions/animations.
// (datasette-debug-gotham's debug bar is excluded at the source via
// DATASETTE_LOAD_PLUGINS in server.mjs, so there's nothing to hide here.)
export const STABILITY_CSS = `
  *, *::before, *::after {
    caret-color: transparent !important;
    transition: none !important;
    animation: none !important;
  }
`;

// Replace Math.random with a fixed-seed LCG (numerical-recipes constants) so
// anything that scatters randomly lands identically on every run. The live
// case is AvatarDialog.svelte's `suggestedColor`, which picks among the first
// four colour swatches at random when the profile has no avatar colour yet.
// The seeded profiles all carry an explicit colour so that branch shouldn't
// fire — this is the belt to that braces, and keeps a future random-using
// component from silently making the PNGs non-deterministic.
export async function stubRandom(page, seed = 42) {
  await page.addInitScript((s0) => {
    let s = s0 >>> 0;
    Math.random = () => {
      s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }, seed);
}

// Rewrite the on-screen text that moves between runs.
//
// There is currently NONE: the profiles frontend renders no timestamps and no
// relative times (grepped frontend/src for toLocaleString/toLocaleDateString/
// "ago"/new Date). `updated_at` only ever reaches the browser inside avatar
// `?v=` cache-busting URLs, which aren't visible pixels. This hook is kept as
// the documented place to put such a fix the moment the UI grows one — see
// the sibling plugins' helpers.mjs for what that looks like.
export async function freezeVolatile(page) {
  await page.evaluate(() => {
    // Intentionally empty — see the comment above.
  });
}

// Screenshot the padded bounding-box union of one or more selectors — used for
// the avatar dialog so the capture includes its backdrop/shadow rather than a
// tight element screenshot cropped exactly to its box.
export async function shotUnion(page, selectors, path, pad = 16) {
  const boxes = [];
  for (const sel of selectors) {
    const box = await page.locator(sel).first().boundingBox();
    if (box) boxes.push(box);
  }
  if (!boxes.length) {
    throw new Error(`shotUnion: no boxes for ${selectors.join(", ")}`);
  }
  const x = Math.min(...boxes.map((b) => b.x));
  const y = Math.min(...boxes.map((b) => b.y));
  const right = Math.max(...boxes.map((b) => b.x + b.width));
  const bottom = Math.max(...boxes.map((b) => b.y + b.height));
  const clip = {
    x: Math.max(0, x - pad),
    y: Math.max(0, y - pad),
    width: Math.min(VIEWPORT.width, right - x + pad * 2),
    height: bottom - y + pad * 2,
  };
  await page.screenshot({ path, clip });
}

// Full-page screenshot trimmed to the bottom of Datasette's footer.
//
// These pages are shorter than the viewport, and datasette's base template
// gives <body> a min-height, so a plain fullPage capture trails a few hundred
// pixels of empty background below the footer — dead space in a README. Clip
// to the footer instead. Falls back to a plain fullPage shot if the footer
// isn't there (a template change shouldn't break the harness).
export async function shotPage(page, file) {
  const bottom = await page.evaluate(() => {
    const footer = document.querySelector("footer.ft");
    if (!footer) return null;
    const r = footer.getBoundingClientRect();
    return Math.ceil(r.bottom + window.scrollY);
  });
  if (bottom === null) {
    await page.screenshot({ path: file, fullPage: true });
    return;
  }
  const width = await page.evaluate(() => document.documentElement.clientWidth);
  await page.screenshot({
    path: file,
    clip: { x: 0, y: 0, width, height: bottom },
  });
}

// Wait until every <img> that has started loading has finished decoding.
// Avatars are served from /-/profile/pic/<id>; capturing mid-decode gives a
// half-drawn or blank circle and a spurious diff.
export async function waitForImages(page) {
  await page.waitForFunction(
    () =>
      Array.from(document.images).every(
        (img) => img.complete && img.naturalWidth > 0,
      ),
    { timeout: 10_000 },
  );
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
