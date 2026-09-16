// Programmatic doc screenshots of the profiles UI → docs/screenshots/*.png.
//
// SELF-CONTAINED: boots its own throwaway datasette on a fixed port with a
// fresh internal DB, drives Playwright, then tears the server down. One
// command, reproducible — so the committed PNGs only change when the UI
// actually changes (clean git diffs).
//
// Unlike the sibling plugins' harnesses there is no shots/seed.mjs driving the
// HTTP API: this plugin *is* the actor directory, so the demo cast is seeded
// server-side through its own public `datasette_user_profile_seeds` hook — see
// shot-plugins/seed_profiles.py. That exercises the real seeding path and
// leaves nothing to seed over the wire.
//
// Output is committed. Re-run + commit when the directory / profile / edit
// page look changes: `just shots` (or `just shots profile` for a subset).
//
// This file is a THIN RUNNER. The harness lives in shots/:
//   * shots/config.mjs     — constants + out(name)
//   * shots/server.mjs     — boot/teardown of the throwaway datasette
//   * shots/cookie.mjs     — signed ds_actor cookie (itsdangerous via uv)
//   * shots/helpers.mjs    — STABILITY_CSS / freezeVolatile / stubRandom /
//                            shotUnion / waitForImages
//   * shots/defineShot.mjs — the per-shot new-context → freeze → capture →
//                            close boilerplate
//   * shots/defs/<name>.mjs — ONE FILE PER SHOT, auto-discovered below.
//                            Adding a screenshot is a single new file here.
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { mkdir, readdir } from "node:fs/promises";
import { OUT, BASE } from "./shots/config.mjs";
import { startServer, stopServer } from "./shots/server.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));

// Auto-discover the shots: every shots/defs/<name>.mjs default-exports a
// defineShot() descriptor. The file name IS the shot id — asserted below so a
// typo can't silently mis-name an output PNG. No central registry to edit.
async function discoverShots() {
  const dir = resolve(HERE, "shots/defs");
  const files = (await readdir(dir)).filter((f) => f.endsWith(".mjs"));
  const shots = [];
  for (const f of files) {
    const name = f.replace(/\.mjs$/, "");
    const mod = await import(resolve(dir, f));
    const run = mod.default;
    if (typeof run !== "function") {
      throw new Error(
        `shots/defs/${f} must default-export a defineShot() descriptor`,
      );
    }
    if (run.shotName !== name) {
      throw new Error(
        `shots/defs/${f}: declared name "${run.shotName}" != file name "${name}"`,
      );
    }
    shots.push({ name, run, order: run.order ?? 0 });
  }
  shots.sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
  return shots;
}

async function main() {
  const requested = new Set(process.argv.slice(2));

  const shots = await discoverShots();
  const names = shots.map((s) => s.name);
  const unknown = [...requested].filter((n) => !names.includes(n));
  if (unknown.length) {
    throw new Error(
      `unknown shot(s): ${unknown.join(", ")} (have: ${names.join(", ")})`,
    );
  }
  const todo = requested.size
    ? shots.filter((s) => requested.has(s.name))
    : shots;

  await mkdir(OUT, { recursive: true });
  console.log(`booting a throwaway datasette on ${BASE} …`);
  const server = await startServer();
  // Make sure the server dies even on Ctrl-C / a thrown error mid-run.
  const onSignal = () => {
    stopServer(server);
    process.exit(130);
  };
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);

  try {
    const browser = await chromium.launch();
    try {
      for (const { name, run } of todo) {
        await run(browser);
        console.log(`✓ ${name} → docs/screenshots/${name}.png`);
      }
    } finally {
      await browser.close();
    }
  } finally {
    stopServer(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
