import { defineShot } from "../defineShot.mjs";
import { BASE } from "../config.mjs";
import { waitForImages } from "../helpers.mjs";

// A public profile page. Viewed as `ada` looking at her own profile, so the
// "Edit profile" button is present — the state most readers of the README will
// recognise.
export default defineShot({
  name: "profile",
  order: 2,
  goto: async (page) => {
    await page.goto(`${BASE}/-/profile/ada`);
  },
  prepare: async (page) => {
    await page.locator(".profile-header h1").waitFor({ timeout: 15_000 });
    await page.locator(".bio").waitFor({ timeout: 10_000 });
    await waitForImages(page);
  },
});
