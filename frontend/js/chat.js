// Chat panel for one user (Alice or Bob): history bubbles, presets, composer, inline errors.

import { displayChar, escapeHtml } from "./format.js";

export class ChatPanel {
  /**
   * @param root   the panel's <section>
   * @param user   "alice" | "bob"
   * @param opts   { onSend(text), onSelect(response), presets: [{text, tag}] }
   */
  constructor(root, user, { onSend, onSelect, presets = [] }) {
    this.root = root;
    this.user = user;
    this.history = root.querySelector(".history");
    this.input = root.querySelector(".composer input");
    this.button = root.querySelector(".composer button");
    this.errorLine = root.querySelector(".error-line");
    this.onSelect = onSelect;
    this.vocab = null;

    root.querySelector(".composer").addEventListener("submit", (event) => {
      event.preventDefault();
      const text = this.input.value;
      if (!text.trim()) return;
      const unknown = this.unknownChars(text);
      if (unknown.length) {
        this.showError(`not in the model's vocabulary: ${unknown.map((c) => `'${displayChar(c)}'`).join(" ")}`);
        return;
      }
      onSend(text);
    });
    this.input.addEventListener("input", () => this.showError(""));

    const presetBox = root.querySelector(".presets");
    presetBox.innerHTML = presets.map((p, i) =>
      `<button type="button" class="preset" data-i="${i}">${escapeHtml(p.text)}${p.tag ? `<span class="tag">${escapeHtml(p.tag)}</span>` : ""}</button>`,
    ).join("");
    presetBox.querySelectorAll(".preset").forEach((el) =>
      el.addEventListener("click", () => { this.input.value = presets[Number(el.dataset.i)].text; this.input.focus(); }));
  }

  /** Characters the current model can't encode (checked locally before sending). */
  unknownChars(text) {
    if (!this.vocab) return [];
    return [...new Set([...text].filter((c) => !this.vocab.has(c)))];
  }

  setVocab(chars) { this.vocab = new Set(chars); }

  setBusy(busy) {
    this.button.disabled = busy;
    this.input.disabled = busy;
  }

  clearInput() { this.input.value = ""; }

  showError(message) { this.errorLine.textContent = message; }

  /** Add a message bubble; `sent` is true on the sender's side. Clicking it replays its encoding. */
  addMessage(response, sent) {
    const s = response.stats;
    const meta = sent
      ? `<span class="badge">${s.bpc.toFixed(2)} bpc</span><span class="badge">${s.wire_bytes} B on the wire</span>`
      : `<span class="badge">${s.bpc.toFixed(2)} bpc</span><span class="badge">&#10003; reconstructed exactly from ${s.wire_bytes} wire bytes</span>`;
    const bubble = document.createElement("div");
    bubble.className = `bubble ${sent ? "sent" : "received"}`;
    bubble.innerHTML = `${escapeHtml(sent ? response.text : response.decoded_text)}<div class="meta">${meta}</div>`;
    bubble.addEventListener("click", () => this.onSelect(response));
    bubble.response = response;
    this.history.appendChild(bubble);
    this.history.scrollTop = this.history.scrollHeight;
  }

  addSystemLine(text) {
    const line = document.createElement("div");
    line.className = "system-line";
    line.textContent = text;
    this.history.appendChild(line);
    this.history.scrollTop = this.history.scrollHeight;
  }

  /** Outline the bubble whose encoding is currently shown. */
  markSelected(response) {
    this.history.querySelectorAll(".bubble").forEach((b) => b.classList.toggle("selected", b.response === response));
  }
}
