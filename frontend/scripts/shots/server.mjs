// Boot/teardown for the throwaway datasette the shots drive.
//
// Every profile endpoint is gated behind the `profile_access` permission, so
// that is granted to everyone here — mirroring `just dev`. Profiles themselves
// come from the shot plugin's `datasette_user_profile_seeds` hook (this plugin
// IS the actor directory, so there is no upstream to seed from).
import { rm } from "node:fs/promises";
import { spawn, execFileSync } from "node:child_process";
import {
  BASE,
  INTERNAL_DB,
  DATA_DB,
  SECRET,
  PLUGINS_DIR,
  PORT,
} from "./config.mjs";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Is something already answering on our port? (status < 500 = "alive").
// Refuse to start over an unknown already-listening server rather than
// screenshot garbage (or someone else's dev instance).
async function reachable() {
  try {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 500);
    const r = await fetch(`${BASE}/-/profiles/`, {
      redirect: "manual",
      signal: ac.signal,
    });
    clearTimeout(t);
    return r.status < 500;
  } catch {
    return false;
  }
}

// A fresh, empty-but-valid sqlite file so datasette has a database to serve.
// Profiles are stored in `--internal`, never here. Shell out to python so we
// don't need a Node sqlite dependency.
function setupDataDb() {
  execFileSync("uv", [
    "run",
    "python3",
    "-c",
    "import sqlite3, sys; sqlite3.connect(sys.argv[1]).close()",
    DATA_DB,
  ]);
}

export async function startServer() {
  // Refuse to start if something is already on the port rather than kill it
  // — that "something" might be a server the user cares about.
  if (await reachable()) {
    throw new Error(
      `something is already serving on ${BASE}. Stop it (or set SHOTS_PORT) and retry.`,
    );
  }

  await rm(INTERNAL_DB, { force: true });
  await rm(DATA_DB, { force: true });
  setupDataDb();

  // `detached: true` puts datasette in its own process group. We spawn via
  // `uv run`, so datasette is a *grandchild* — killing the `uv` pid alone
  // leaves datasette holding the port. Killing the whole group (negative pid
  // in stopServer) takes the grandchild down with it.
  //
  // DATASETTE_LOAD_PLUGINS is an allowlist of *distributions*: it pins the set
  // of installed plugins to exactly what these shots need. Without it
  // datasette-debug-gotham (a dev dependency, for `just dev`) would seed its
  // own Gotham cast into the directory and render its debug bar over every
  // shot. Plugins from --plugins-dir are loaded separately and are unaffected.
  // PYTHONHASHSEED=0 so any hash-derived ordering stays stable across runs.
  const child = spawn(
    "uv",
    [
      "run",
      "datasette",
      "-p",
      String(PORT),
      "--secret",
      SECRET,
      "--internal",
      INTERNAL_DB,
      "--plugins-dir",
      PLUGINS_DIR,
      "-s",
      "permissions.profile_access.id",
      "*",
      DATA_DB,
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
      env: {
        ...process.env,
        PYTHONHASHSEED: "0",
        DATASETTE_LOAD_PLUGINS:
          "datasette-user-profiles,datasette-plugin-router,datasette-vite",
      },
    },
  );
  let log = "";
  child.stdout.on("data", (d) => (log += d));
  child.stderr.on("data", (d) => (log += d));

  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(
        `datasette exited early (code ${child.exitCode}):\n${log}`,
      );
    }
    if (await reachable()) return child;
    await sleep(250);
  }
  stopServer(child);
  throw new Error(`datasette never came up on ${BASE}:\n${log}`);
}

// Kill the server's whole process group (datasette is uv's child). Idempotent.
export function stopServer(child) {
  if (!child || child.exitCode !== null) return;
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    try {
      child.kill("SIGKILL");
    } catch {
      // already gone
    }
  }
}
