// The encoded output: the shortest binary fraction's digits so far (the bits sent), their size, and
// a check that decoding those bits alone gives back the exact text.

import { escapeHtml } from "./format.js";

export class Output {
  constructor({ bits, stats, decodeStatus, copy }) {
    Object.assign(this, { bitsEl: bits, statsEl: stats, decodeEl: decodeStatus });
    this.result = null;
    this.cursor = 0;
    copy.addEventListener("click", async () => {
      if (!this.result) return;
      await navigator.clipboard?.writeText(this.result.bits);
      copy.textContent = "copied";
      setTimeout(() => { copy.textContent = "copy"; }, 1200);
    });
  }

  setData(result) {
    this.result = result;
    this.cursor = 0;
    this.setDecode("pending");
    this.render();
  }

  setCursor(cursor) {
    this.cursor = cursor;
    this.render();
  }

  render() {
    const r = this.result;
    if (!r || !r.trace.length) {
      this.bitsEl.innerHTML = '<span class="empty">the bits appear here as you type</span>';
      this.statsEl.innerHTML = "";
      return;
    }
    const step = r.trace[Math.max(0, this.cursor - 1)];
    const bits = this.cursor ? step.running_bits : "";
    const added = this.cursor ? step.bits_added : 0;
    const old = bits.slice(0, bits.length - added);
    const fresh = bits.slice(bits.length - added);
    this.bitsEl.innerHTML = `<span class="point">0.</span>${escapeHtml(old)}<span class="new">${escapeHtml(fresh)}</span>`;

    const s = r.stats;
    const done = this.cursor >= r.trace.length;
    const chars = this.cursor ? step.char_end : 0;
    this.statsEl.innerHTML = done
      ? `<span><b>${s.payload_bits}</b> bits (${s.payload_bytes} bytes)</span>` +
        `<span><b>${s.bpc.toFixed(2)}</b> bits/char</span>` +
        `<span>${s.chars} characters → ${s.symbols} symbol${s.symbols === 1 ? "" : "s"}</span>` +
        `<span>plain UTF-8: ${s.utf8_bits} bits → <b>${s.ratio.toFixed(1)}×</b> smaller</span>`
      : `<span>encoding… <b>${bits.length}</b> bits sent for the first ${chars} of ${s.chars} characters</span>`;
  }

  /** state: "pending" | "running" | {ok: true} | {error} */
  setDecode(state) {
    const el = this.decodeEl;
    el.className = "decode-status";
    if (state === "pending") el.textContent = "";
    else if (state === "running") el.textContent = "checking: decoding the bits…";
    else if (state.ok) {
      el.classList.add("ok");
      el.textContent = `✓ the receiver decodes these ${this.result.bits.length} bits (plus the symbol count) back into exactly your text`;
    } else {
      el.classList.add("bad");
      el.textContent = `✗ ${state.error}`;
    }
  }
}
