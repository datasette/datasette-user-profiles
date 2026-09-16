import { defineShot } from "../defineShot.mjs";
import { BASE } from "../config.mjs";
import { shotUnion, waitForImages } from "../helpers.mjs";

// The profile hovercard, open over a host page's comment thread (served by
// shot-plugins/hovercard_demo.py — the hovercard is something other plugins
// embed, so it needs a host page to be shown in).
//
// Opened by dispatching the documented `profile-hovercard:open` event rather
// than by hovering: hover would mean waiting out the component's 500ms open
// delay and hoping the pointer settled, which is exactly the kind of timing
// race that makes a screenshot suite flaky. The event is the same code path
// the card's own keyboard/programmatic entry uses.
export default defineShot({
  name: "hovercard",
  order: 5,
  freeze: false,
  goto: async (page) => {
    await page.goto(`${BASE}/-/shots/hovercard-demo`);
  },
  prepare: async (page) => {
    const trigger = page.locator('[data-profile-hovercard="grace"]');
    await trigger.waitFor({ timeout: 15_000 });
    // Wait for the module to upgrade the element before firing at it.
    await page.waitForFunction(
      () => customElements.get("profile-hovercard") !== undefined,
      { timeout: 10_000 },
    );
    await trigger.evaluate((el) => {
      el.dispatchEvent(
        new CustomEvent("profile-hovercard:open", { bubbles: true }),
      );
    });
    const card = page.locator("profile-hovercard");
    await card.waitFor({ state: "visible", timeout: 10_000 });
    // The card fetches /-/profiles/api/hovercard/<id>; wait for the resolved
    // name to land in its shadow root rather than capturing an empty shell.
    // The avatar lives in the shadow root too, so it isn't covered by
    // waitForImages' document.images sweep — check it here.
    await page.waitForFunction(
      () => {
        const el = document.querySelector("profile-hovercard");
        const root = el?.shadowRoot;
        if (!root) return false;
        const name = root.querySelector("[part~='name']");
        if (!name || !name.textContent.trim()) return false;
        // Guard against capturing mid-fade even if reduced motion regresses.
        const card = root.querySelector("[part~='card']");
        if (!card || getComputedStyle(card).opacity !== "1") return false;
        return Array.from(root.querySelectorAll("img")).every(
          (img) => img.complete && img.naturalWidth > 0,
        );
      },
      { timeout: 10_000 },
    );
    await waitForImages(page);
  },
  capture: (page, file) =>
    shotUnion(page, [".demo", "profile-hovercard"], file, 24),
});
