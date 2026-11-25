// The encoder card (avatar + persona name) and its menu of all encoders, grouped by family.

import { FAMILIES, avatarSvg, persona, sortModels, tokenizerLabel } from "./encoders.js";
import { escapeHtml } from "./format.js";

export class EncoderPicker {
  constructor({ card, menu, avatar, name, sub }, { onSelect }) {
    Object.assign(this, { card, menu, avatarEl: avatar, nameEl: name, subEl: sub, onSelect });
    this.models = [];
    this.current = null;
    card.addEventListener("click", () => this.toggle());
    document.addEventListener("click", (e) => {
      if (!this.menu.hidden && !this.menu.contains(e.target) && !this.card.contains(e.target)) this.close();
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") this.close(); });
  }

  setModels(models) {
    this.models = models;
    const sorted = sortModels(models);
    this.menu.innerHTML = FAMILIES.map((family) => {
      const list = sorted.filter((m) => persona(m).family === family.id);
      if (!list.length) return "";
      return `<div class="menu-group">${escapeHtml(family.title)}</div>` + list.map((m) => {
        const p = persona(m);
        return `<button type="button" class="menu-item" role="option" data-id="${m.id}"
                  ${m.available ? "" : "disabled"} title="${escapeHtml(m.description)}">
            <span class="avatar">${avatarSvg(m)}</span>
            <span><span class="title">${escapeHtml(p.title)}</span><br>
              <span class="meta">${escapeHtml(m.name)} · ${escapeHtml(tokenizerLabel(m))}${m.available ? "" : " · files missing"}</span>
              <span class="unable-note">can't encode this text</span></span>
          </button>`;
      }).join("");
    }).join("");
    this.menu.querySelectorAll(".menu-item").forEach((el) => el.addEventListener("click", () => {
      this.close();
      if (el.dataset.id !== this.current?.id) this.onSelect(this.models.find((m) => m.id === el.dataset.id));
    }));
  }

  /** Grey out encoders that are taken elsewhere (the compare page's other card). */
  markUsed(ids) {
    this.menu.querySelectorAll(".menu-item").forEach((el) => {
      const model = this.models.find((m) => m.id === el.dataset.id);
      const used = ids.includes(el.dataset.id) && el.dataset.id !== this.current?.id;
      el.disabled = !model?.available || used;
      el.classList.toggle("used", used);
    });
  }

  /** Flag encoders that can't encode the current text (they can still be picked). */
  markUnable(ids) {
    this.menu.querySelectorAll(".menu-item").forEach((el) => el.classList.toggle("unable", ids.includes(el.dataset.id)));
  }

  /** Show model on the card (color: the avatar's ring, e.g. a compare card's series colour). */
  show(model, color) {
    this.current = model;
    const p = persona(model);
    this.avatarEl.innerHTML = avatarSvg(model, color);
    this.nameEl.textContent = p.title;
    this.subEl.textContent = `${model.name} · ${tokenizerLabel(model)}`;
    this.card.title = model.description;
    this.menu.querySelectorAll(".menu-item").forEach((el) =>
      el.setAttribute("aria-selected", String(el.dataset.id === model.id)));
  }

  toggle() { this.menu.hidden ? this.open() : this.close(); }

  open() {
    this.menu.hidden = false;
    this.card.setAttribute("aria-expanded", "true");
    this.menu.querySelector('[aria-selected="true"]')?.focus();
  }

  close() {
    this.menu.hidden = true;
    this.card.setAttribute("aria-expanded", "false");
  }
}

/** Build the card + menu elements a picker drives inside container (index.html has them inline). */
export function pickerElements(container) {
  container.innerHTML = `<button type="button" class="encoder-card" aria-haspopup="listbox" aria-expanded="false">
      <span class="avatar"></span>
      <span class="encoder-text"><span class="encoder-name"></span><span class="encoder-sub"></span></span>
      <span class="chevron" aria-hidden="true">&#9662;</span>
    </button>
    <div class="encoder-menu" role="listbox" hidden></div>`;
  const q = (selector) => container.querySelector(selector);
  return { card: q(".encoder-card"), menu: q(".encoder-menu"), avatar: q(".avatar"), name: q(".encoder-name"),
    sub: q(".encoder-sub") };
}
