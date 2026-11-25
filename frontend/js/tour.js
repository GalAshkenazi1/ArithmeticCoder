// A short guided tour: one step per element, each a spotlight on the element and a card that
// explains it, with Back / Next / Skip. Shown once (remembered), or again on request.

export class Tour {
  /** steps: [{ target: selector or () => Element, title, text }]; key: localStorage flag "seen". */
  constructor(steps, key) {
    Object.assign(this, { steps, key, index: -1 });
    this.spot = Object.assign(document.createElement("div"), { className: "tour-spot" });
    this.card = Object.assign(document.createElement("div"), { className: "tour-card", role: "dialog" });
    this.card.setAttribute("aria-label", "guided tour");
    this.onKey = (e) => {
      if (e.key === "Escape") this.end();
      if (e.key === "ArrowRight") this.go(this.index + 1);
      if (e.key === "ArrowLeft") this.go(this.index - 1);
    };
    this.onMove = () => this.place();
  }

  get seen() { return localStorage.getItem(this.key) === "1"; }

  start() {
    document.body.append(this.spot, this.card);
    document.addEventListener("keydown", this.onKey);
    window.addEventListener("resize", this.onMove);
    window.addEventListener("scroll", this.onMove, { passive: true });
    this.go(0);
  }

  end() {
    localStorage.setItem(this.key, "1");
    this.spot.remove();
    this.card.remove();
    document.removeEventListener("keydown", this.onKey);
    window.removeEventListener("resize", this.onMove);
    window.removeEventListener("scroll", this.onMove);
    this.index = -1;
  }

  _target(step) {
    return typeof step.target === "function" ? step.target() : document.querySelector(step.target);
  }

  go(index) {
    if (index < 0) return;
    if (index >= this.steps.length) { this.end(); return; }
    const step = this.steps[index];
    const el = this._target(step);
    if (!el) { this.go(index + (index > this.index ? 1 : -1)); return; }  // skip steps whose element isn't there
    this.index = index;
    const last = index === this.steps.length - 1;
    this.card.innerHTML = `<div class="tour-count">${index + 1} of ${this.steps.length}</div>
      <h3>${step.title}</h3><p>${step.text}</p>
      <div class="tour-buttons">
        <button type="button" class="tour-skip">${last ? "close" : "skip the tour"}</button>
        <span>${index ? '<button type="button" class="tour-back">back</button>' : ""}
          <button type="button" class="tour-next">${last ? "done" : "next ▸"}</button></span>
      </div>`;
    this.card.querySelector(".tour-skip").addEventListener("click", () => this.end());
    this.card.querySelector(".tour-back")?.addEventListener("click", () => this.go(this.index - 1));
    this.card.querySelector(".tour-next").addEventListener("click", () => this.go(this.index + 1));
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    this.place();
    setTimeout(() => this.place(), 400);  // after the smooth scroll
    this.card.querySelector(".tour-next").focus({ preventScroll: true });
  }

  /** Spotlight the step's element and put the card below it (or above, if there's no room). */
  place() {
    if (this.index < 0) return;
    const el = this._target(this.steps[this.index]);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const pad = 6;
    Object.assign(this.spot.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`,
      height: `${r.height + 2 * pad}px` });
    const c = this.card.getBoundingClientRect();
    const below = r.bottom + pad + 12 + c.height <= window.innerHeight;
    const top = below ? r.bottom + pad + 12 : Math.max(8, r.top - pad - 12 - c.height);
    const left = Math.max(8, Math.min(r.left, window.innerWidth - c.width - 8));
    Object.assign(this.card.style, { left: `${left}px`, top: `${top}px` });
  }
}
