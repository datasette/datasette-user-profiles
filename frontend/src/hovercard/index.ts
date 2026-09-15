/**
 * Profile hovercard client.
 *
 *   <a href="/-/profile/alex" data-profile-hovercard>Alex</a>
 *   <span data-profile-hovercard="alex">@Alex</span>
 *   <script type="module" src="/-/profiles/hovercard.js"></script>
 *
 * Vanilla TS, no imports from src/pages/**, one delegated listener set.
 */
import { CARD_ID, ProfileHovercard, TAG, type ProfileCardData } from "./card";
import { place, type Point } from "./position";

const OPEN_DELAY = 500;
const CLOSE_DELAY = 300;
const SELECTOR = "[data-profile-hovercard]";

/**
 * Datasette base_url prefix for the card endpoint.
 *
 * - `<html data-profile-hovercard-base="/prefix">` wins when present. This is
 *   needed in Vite dev mode, where the module is served by the Vite dev server
 *   and its URL says nothing about the Datasette base_url.
 * - Otherwise it is derived from this module's own URL: the built file lives
 *   under `<base>/-/…`, so the base is the pathname before the first `/-/`
 *   ("" when the path starts with `/-/` or has no `/-/` at all).
 *
 * Requests always go to `location.origin`, never the script's origin.
 */
function basePath(): string {
  const override = document.documentElement.dataset.profileHovercardBase;
  if (override != null) return override.replace(/\/+$/, "");
  const path = new URL(import.meta.url).pathname;
  const i = path.indexOf("/-/");
  return i > 0 ? path.slice(0, i) : "";
}

const cache = new Map<string, Promise<ProfileCardData | null>>();
function load(id: string): Promise<ProfileCardData | null> {
  let p = cache.get(id);
  if (!p) {
    const url = new URL(
      `${basePath()}/-/profiles/api/hovercard/${encodeURIComponent(id)}`,
      location.origin,
    );
    // Anything but 200 (403, 404, 5xx) or a network error is cached as null:
    // never show a card for that id on this page.
    p = fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then((r) => (r.status === 200 ? r.json() : null))
      .catch(() => null);
    cache.set(id, p);
  }
  return p;
}

/** Id from the attribute value, else from a `…/-/profile/<id>` href suffix. */
function actorIdFor(trigger: Element): string | null {
  const v = trigger.getAttribute("data-profile-hovercard");
  if (v) return v;
  const m = (trigger.getAttribute("href") ?? "").match(
    /\/-\/profile\/([^/?#]+)\/?(?:[?#]|$)/,
  );
  if (!m?.[1]) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return null;
  }
}

let card: ProfileHovercard | null = null;
let active: Element | null = null;
let openTimer = 0;
let closeTimer = 0;
let lastPointer: Point | null = null;
let token = 0;
let anchorAt: DOMRect | null = null;

const isOpen = () => !!card?.matches(":popover-open");

async function open(trigger: Element): Promise<void> {
  const id = actorIdFor(trigger);
  if (!id) return;
  const my = ++token;
  const data = await load(id);
  if (my !== token || active !== trigger) return;
  if (!data || !trigger.isConnected) {
    close();
    return;
  }
  card ??= document.body.appendChild(new ProfileHovercard());
  card.render(data);
  if (!isOpen()) card.showPopover();
  anchorAt = place(card, card.card, trigger, lastPointer);
  const shown = card;
  requestAnimationFrame(() => {
    if (active === trigger) shown.setAttribute("data-shown", "");
  });
  trigger.setAttribute("aria-describedby", CARD_ID);
}

function close(): void {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  token++;
  active?.removeAttribute("aria-describedby");
  active = null;
  anchorAt = null;
  if (card && isOpen()) {
    card.removeAttribute("data-shown");
    card.hidePopover();
  }
}

function intend(trigger: Element, immediate = false): void {
  clearTimeout(closeTimer);
  if (active === trigger) return;
  clearTimeout(openTimer);
  active?.removeAttribute("aria-describedby");
  active = trigger;
  const id = actorIdFor(trigger);
  if (id) void load(id); // warm the cache during the delay
  // Programmatic opens are immediate; an already-open card swaps in place.
  if (immediate || isOpen()) void open(trigger);
  else openTimer = window.setTimeout(() => void open(trigger), OPEN_DELAY);
}

function release(): void {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  closeTimer = window.setTimeout(close, CLOSE_DELAY);
}

const triggerOf = (t: EventTarget | null) =>
  t instanceof Element ? t.closest(SELECTOR) : null;
// Events from inside the shadow root are retargeted to the host.
const inCard = (t: EventTarget | null) => !!card && t === card;
// The trigger can be torn down under us (e.g. collab rebuilds NodeViews).
const alive = () => {
  if (active && !active.isConnected) close();
};

function install(): void {
  document.addEventListener("pointerover", (e) => {
    if (e.pointerType === "touch") return;
    alive();
    lastPointer = { x: e.clientX, y: e.clientY };
    const t = triggerOf(e.target);
    if (t) intend(t);
    else if (inCard(e.target)) clearTimeout(closeTimer);
  });
  document.addEventListener(
    "pointermove",
    (e) => {
      lastPointer = { x: e.clientX, y: e.clientY };
    },
    { passive: true },
  );
  document.addEventListener("pointerout", (e) => {
    if (e.pointerType === "touch") return;
    alive();
    const from = triggerOf(e.target) ?? (inCard(e.target) ? card : null);
    if (!from) return;
    const to = e.relatedTarget;
    if (
      to instanceof Node &&
      (from.contains(to) || inCard(to) || active?.contains(to))
    )
      return;
    release();
  });
  document.addEventListener("focusin", (e) => {
    alive();
    const t = triggerOf(e.target);
    if (t && t.matches(":focus-visible")) {
      lastPointer = null;
      intend(t);
    }
  });
  document.addEventListener("focusout", (e) => {
    // Only the active trigger losing focus matters, and not while the pointer
    // still holds the card open (e.g. clicking another trigger, or pressing
    // "View profile", which moves focus into the card).
    const t = triggerOf(e.target);
    if (
      !t ||
      t !== active ||
      inCard(e.relatedTarget) ||
      t.matches(":hover") ||
      card?.matches(":hover")
    )
      return;
    release();
  });
  document.addEventListener("profile-hovercard:open", (e) => {
    const t = triggerOf(e.target);
    if (t) {
      lastPointer = null;
      intend(t, true);
    }
  });
  document.addEventListener("profile-hovercard:close", () => close());

  // Capture on window so an open card claims Escape before page/editor
  // handlers. When closed we never claim keys, preserving the host's own
  // Escape precedence; a key only cancels a pending open.
  window.addEventListener(
    "keydown",
    (e) => {
      if (!active) return;
      if (e.key === "Escape" && isOpen()) {
        e.preventDefault();
        e.stopPropagation();
      }
      if (["Shift", "Control", "Alt", "Meta"].includes(e.key)) return;
      close();
    },
    true,
  );
  // Editors fire scroll events without moving anything (focus / caret
  // scroll-into-view). Only close when the trigger actually moved.
  window.addEventListener(
    "scroll",
    () => {
      if (!active || !anchorAt) return;
      if (!active.isConnected) return close();
      const r = active.getBoundingClientRect();
      if (
        Math.abs(r.top - anchorAt.top) > 2 ||
        Math.abs(r.left - anchorAt.left) > 2
      )
        close();
    },
    { passive: true, capture: true },
  );
  window.addEventListener("resize", () => {
    if (active) close();
  });
}

// Idempotent: a second evaluation (e.g. the script included twice, or from
// both a hashed build URL and the dev server) must not double-register.
if (!customElements.get(TAG)) {
  customElements.define(TAG, ProfileHovercard);
  install();
}
