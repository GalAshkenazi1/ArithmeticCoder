// Bit tracker: the message with the current character highlighted, its probability, the running
// shortest binary fraction (new bits highlighted), the "+0 bits" pill, and one tick per step.

import { costColor, displayChar, escapeHtml } from "./format.js";

const MAX_BITS_SHOWN = 96;

export class BitTracker {
  constructor(root, { onSeek } = {}) {
    this.prefix = root.querySelector(".tracker-prefix");
    this.prob = root.querySelector(".tracker-prob");
    this.bits = root.querySelector(".tracker-bits");
    this.pill = root.querySelector(".tracker-pill");
    this.ticks = root.querySelector(".tracker-ticks");
    this.onSeek = onSeek ?? (() => {});
    this.trace = [];
    this.clear();
  }

  clear() {
    this.prefix.textContent = "";
    this.prob.textContent = "";
    this.bits.textContent = "";
    this.pill.textContent = "";
    this.pill.className = "tracker-pill";
    this.ticks.innerHTML = "";
  }

  /** New message: draw its tick strip (height = bits added at that step). */
  setTrace(trace) {
    this.trace = trace;
    const last = trace[trace.length - 1];
    this.message = last ? last.prefix + last.char : "";
    this.clear();
    if (!trace.length) {
      this.prefix.textContent = "(empty message: 0 payload bits)";
      return;
    }
    const most = Math.max(1, ...trace.map((t) => t.bits_added));
    this.ticks.innerHTML = trace.map((t, i) => {
      const h = t.bits_added === 0 ? 3 : 6 + (32 * t.bits_added) / most;
      const color = t.bits_added === 0 ? "#10b981" : costColor(t.prob);
      return `<div class="tick" data-i="${i}" title="'${escapeHtml(displayChar(t.char))}': +${t.bits_added} bits"
                   style="height:${h}px;background:${color}"></div>`;
    }).join("");
    this.ticks.querySelectorAll(".tick").forEach((el) =>
      el.addEventListener("click", () => this.onSeek(Number(el.dataset.i))));
  }

  /** Show step i. */
  show(i) {
    const t = this.trace[i];
    if (!t) return;
    this.prefix.innerHTML =
      `<span class="done">${escapeHtml(t.prefix)}</span>` +
      `<span class="current">${escapeHtml(displayChar(t.char))}</span>` +
      `<span class="todo">${escapeHtml(this.message.slice(i + 1))}</span>`;

    const surprise = -Math.log2(t.prob);
    this.prob.innerHTML = `P('${escapeHtml(displayChar(t.char))}' | prefix) = <b class="text-slate-200">${(t.prob * 100).toFixed(2)}%</b>` +
      ` &nbsp;&middot;&nbsp; surprise ${surprise.toFixed(2)} bits &nbsp;&middot;&nbsp; interval width 2^${t.log2_width_after.toFixed(1)}`;

    const bits = t.running_bits;
    const old = bits.slice(0, bits.length - t.bits_added);
    const added = bits.slice(bits.length - t.bits_added);
    const oldShown = old.length + added.length > MAX_BITS_SHOWN ? "…" + old.slice(-(MAX_BITS_SHOWN - added.length)) : old;
    this.bits.innerHTML = `r = 0.${escapeHtml(oldShown)}<span class="new">${added}</span>` +
      ` <span class="text-slate-500">(${bits.length} bits)</span>`;

    if (t.bits_added === 0) {
      this.pill.textContent = "+0 bits added! (predicted by model)";
      this.pill.className = "tracker-pill zero";
    } else {
      this.pill.textContent = `+${t.bits_added} bit${t.bits_added === 1 ? "" : "s"}`;
      this.pill.className = "tracker-pill some";
    }
    this.ticks.querySelectorAll(".tick").forEach((el, j) => el.classList.toggle("current", j === i));
  }
}
