import { defineShot } from "../defineShot.mjs";
import { BASE } from "../config.mjs";
import { waitForImages } from "../helpers.mjs";

// The edit page at /-/user-profile/edit: the current picture with its "change"
// affordance, plus the display name / bio / email fields. Every field is
// editable here — the locked state (`editable_fields` config) is a separate
// concern the README covers in prose.
export default defineShot({
  name: "edit-profile",
  order: 3,
  goto: async (page) => {
    await page.goto(`${BASE}/-/user-profile/edit`);
  },
  prepare: async (page) => {
    await page.locator(".photo-section").waitFor({ timeout: 15_000 });
    // The form hydrates from page_data; wait for a populated field rather than
    // an empty one so the shot shows the saved values.
    await page.waitForFunction(
      () => {
        const el = document.querySelector("#display-name");
        return el instanceof HTMLInputElement && el.value.length > 0;
      },
      { timeout: 10_000 },
    );
    await waitForImages(page);
  },
});
