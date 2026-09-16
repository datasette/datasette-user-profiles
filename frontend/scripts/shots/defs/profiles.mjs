import { defineShot } from "../defineShot.mjs";
import { waitForImages } from "../helpers.mjs";

// The profiles directory at /-/profiles/ — the whole seeded cast, showing all
// three avatar states side by side: an uploaded photo (ada), generated
// icon+colour avatars (grace, alan, katherine, margaret) and the letter
// placeholder for a profile with no picture at all (tim).
export default defineShot({
  name: "profiles",
  order: 1,
  prepare: async (page) => {
    await page.locator(".profile-card").first().waitFor({ timeout: 15_000 });
    // All six rows, so the capture never lands mid-render.
    await page.waitForFunction(
      () => document.querySelectorAll(".profile-card").length >= 6,
      { timeout: 10_000 },
    );
    await waitForImages(page);
  },
});
