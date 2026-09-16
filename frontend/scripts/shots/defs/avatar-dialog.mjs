import { defineShot } from "../defineShot.mjs";
import { BASE } from "../config.mjs";
import { shotUnion, waitForImages } from "../helpers.mjs";

const DIALOG = "dialog[aria-label='Profile picture']";

// The profile-picture dialog, switched to its Icon tab: the icon grid and
// colour swatches that generate an avatar for someone who hasn't uploaded a
// photo. Captured tight to the dialog (pad 0) rather than the whole page — a
// padded clip would frame it with fragments of half-cut text from the edit
// form behind the semi-transparent backdrop.
//
// `ada` has an explicit avatar_color seeded, so AvatarDialog's random
// "suggested colour" branch never fires (stubRandom in defineShot pins it
// regardless) and the highlighted swatch is the same on every run.
export default defineShot({
  name: "avatar-dialog",
  order: 4,
  freeze: false,
  goto: async (page) => {
    await page.goto(`${BASE}/-/user-profile/edit`);
  },
  prepare: async (page) => {
    await page.locator(".avatar-btn").waitFor({ timeout: 15_000 });
    await waitForImages(page);
    await page.locator(".avatar-btn").click();
    const dialog = page.locator(DIALOG);
    await dialog.waitFor({ state: "visible", timeout: 10_000 });
    // Switch to the Icon tab — the Photo tab is just a dropzone.
    await page.locator(`${DIALOG} [role="tab"]`, { hasText: "Icon" }).click();
    await page.locator(`${DIALOG} .icon-grid`).waitFor({ timeout: 10_000 });
    await page.locator(`${DIALOG} .color-row`).waitFor({ timeout: 10_000 });
    await waitForImages(page);
  },
  capture: (page, file) => shotUnion(page, [DIALOG], file, 0),
});
