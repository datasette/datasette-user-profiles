const GAP = 8;
const EDGE = 8;

export interface Point {
  x: number;
  y: number;
}

/**
 * The trigger's client rect nearest the pointer (inline triggers can wrap
 * across lines), or its last rect when there's no pointer (keyboard or
 * programmatic open).
 */
function anchorRect(trigger: Element, pointer: Point | null): DOMRect {
  const rects = Array.from(trigger.getClientRects());
  const last = rects[rects.length - 1];
  if (!last) return trigger.getBoundingClientRect();
  if (!pointer) return last;
  const dist = (r: DOMRect) => Math.abs((r.top + r.bottom) / 2 - pointer.y);
  return rects.reduce((a, r) => (dist(r) < dist(a) ? r : a));
}

/**
 * Place `host` below the anchor with a gap, flipping above when there isn't
 * room, clamped inside the viewport. Returns the trigger's bounding rect so
 * the caller can detect whether a later scroll actually moved it.
 */
export function place(
  host: HTMLElement,
  card: HTMLElement,
  trigger: Element,
  pointer: Point | null,
): DOMRect {
  const a = anchorRect(trigger, pointer);
  const w = card.offsetWidth;
  const h = card.offsetHeight;
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  let top = a.bottom + GAP;
  let dy = "4px";
  if (top + h > vh - EDGE && a.top - GAP - h >= EDGE) {
    top = a.top - GAP - h;
    dy = "-4px";
  }
  host.style.top = top + "px";
  host.style.left = Math.max(EDGE, Math.min(a.left, vw - w - EDGE)) + "px";
  host.style.setProperty("--_dy", dy);
  return trigger.getBoundingClientRect();
}
