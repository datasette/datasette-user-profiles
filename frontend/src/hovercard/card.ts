import css from "./hovercard.css?inline";

export const TAG = "profile-hovercard";
export const CARD_ID = "profile-hovercard";

/** Response of GET /-/profiles/api/hovercard/<id> (ProfileCard). */
export interface ProfileCardData {
  id: string;
  name: string;
  bio: string | null;
  avatar_url: string | null;
  profile_url: string;
  has_profile: boolean;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  part?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (part) {
    e.className = part;
    e.setAttribute("part", part);
  }
  if (text != null) e.textContent = text;
  return e;
}

function initial(name: string): HTMLDivElement {
  // Grey initial (decision E): background --_border, colour --_muted.
  return el("div", "avatar", Array.from(name.trim())[0]?.toUpperCase() ?? "?");
}

export class ProfileHovercard extends HTMLElement {
  readonly card: HTMLDivElement;

  constructor() {
    super();
    this.setAttribute("popover", "manual");
    this.id = CARD_ID;
    const root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = css;
    this.card = el("div", "card");
    root.append(style, this.card);
  }

  /** Every field goes in via textContent / properties, never innerHTML. */
  render(c: ProfileCardData): void {
    const head = el("div", "head");
    let avatar: HTMLElement;
    if (c.avatar_url) {
      const img = el("img", "avatar");
      img.alt = "";
      img.addEventListener("error", () => img.replaceWith(initial(c.name)), {
        once: true,
      });
      img.src = c.avatar_url;
      avatar = img;
    } else {
      avatar = initial(c.name);
    }
    const names = el("div", "names");
    names.append(el("div", "name", c.name));
    if (c.name !== c.id) names.append(el("div", "handle", "@" + c.id));
    head.append(avatar, names);

    const footer = el("div", "footer");
    const link = el("a", undefined, "View profile →");
    link.href = c.profile_url;
    footer.append(link);

    this.card.replaceChildren(head);
    if (!c.has_profile) this.card.append(el("p", "empty", "No profile yet"));
    else if (c.bio) this.card.append(el("p", "bio", c.bio));
    this.card.append(footer);
  }
}
