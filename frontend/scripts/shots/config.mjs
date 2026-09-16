// Shared constants for the screenshot harness. Imported by every other
// shots/*.mjs module and by each shot in shots/defs/.
import { fileURLToPath } from "node:url";
import { dirname, resolve, join } from "node:path";
import { tmpdir } from "node:os";

// Fixed port so a stale server is obvious rather than silently screenshot.
// 8486-8494 are claimed by sibling plugins' harnesses (paper, sheets, town,
// places, rss, chat, cron, kanban) — 8495 is the next free slot.
export const PORT = Number(process.env.SHOTS_PORT || 8495);
export const BASE = `http://localhost:${PORT}`;

// Fixed signing secret — lets us mint a signed ds_actor cookie so the shots
// browse as a real logged-in person (the edit page is "your own profile", so
// there is no anonymous version of it). NOT a real secret.
export const SECRET = "screenshots-secret-not-for-prod";

// Fresh scratch files under the OS tmpdir every run, so reruns start from
// identical state rather than the repo-root `internal.db` that `just dev`
// writes to. Profiles live entirely in the internal database; the data db is
// only there so datasette has something to serve.
export const INTERNAL_DB = join(
  tmpdir(),
  "datasette-user-profiles-shots-internal.db",
);
export const DATA_DB = join(tmpdir(), "datasette-user-profiles-shots-data.db");

const HERE = dirname(fileURLToPath(import.meta.url)); // frontend/scripts/shots
export const PLUGINS_DIR = resolve(HERE, "../shot-plugins");
export const OUT = resolve(HERE, "../../../docs/screenshots");

// The browsing actor. `ada` is seeded with a photo *and* an icon/colour (see
// shot-plugins/seed_profiles.py) so every surface renders its populated state
// and the avatar dialog never falls back to a random suggested colour.
export const ACTOR = "ada";

export const VIEWPORT = { width: 1000, height: 820 };
export const DEVICE_SCALE_FACTOR = 2;

// Absolute path of a shot's output PNG.
export const out = (name) => resolve(OUT, `${name}.png`);
