// bits/char graph: what each character costs (bars) and the payload's running bits per character
// (line), revealed in step with the animation. x = character position, so every tokenizer fits:
// a symbol spanning several characters spreads its cost over them; several symbols covering one
// character (bytes of an emoji) add up.

import { costBits, displayChar, escapeHtml, formatOdds, svgEl } from "./format.js";

const M = { left: 34, right: 10, top: 12, bottom: 38 };
const RAW_BITS = 8;

export class BpcGraph {
  constructor(container, svg, tooltip, { onSeek } = {}) {
    Object.assign(this, { container, svg, tooltip, onSeek: onSeek ?? (() => {}) });
    this.chars = [];  // code points: the trace's char positions index these
    this.groups = [];
    this.cursor = 0;
    this.hover = -1;
    new ResizeObserver(() => this.draw()).observe(container);
    // phones: a tap shows the tooltip (there is no hover), a tap elsewhere hides it
    svg.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") this._onMove(e); });
    document.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" && this.hover >= 0 && !svg.contains(e.target)) { this.hover = -1; this.tooltip.hidden = true; this.draw(); }
    });
    svg.addEventListener("mousemove", (e) => this._onMove(e));
    svg.addEventListener("mouseleave", () => { this.hover = -1; this.tooltip.hidden = true; this.draw(); });
    svg.addEventListener("click", () => { if (this.hover >= 0) this.onSeek(this.groups[this.hover].last + 1); });
  }

  /** One bar per character span; `last` = index of the last trace step in it. */
  setData(text, trace) {
    this.chars = [...text];
    const groups = [];
    trace.forEach((t, i) => {
      const g = groups[groups.length - 1];
      if (g && g.start === t.char_start && g.end === t.char_end) {
        g.cost += costBits(t.prob);
        g.last = i;
        g.symbols += 1;
        g.probs.push(t.prob);
      } else {
        groups.push({ start: t.char_start, end: t.char_end, cost: costBits(t.prob), last: i, symbols: 1,
          probs: [t.prob], symbol: t.symbol });
      }
    });
    for (const g of groups) {
      g.perChar = g.cost / Math.max(1, g.end - g.start);
      g.bitsSoFar = trace[g.last].running_bits.length;
    }
    this.groups = groups;
    this.draw();
  }

  /** Show everything encoded so far: steps 0..cursor-1. */
  setCursor(cursor) {
    this.cursor = cursor;
    this.draw();
  }

  _scales() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    const n = Math.max(this.chars.length, 8);
    const maxBar = Math.max(0, ...this.groups.map((g) => g.perChar));
    const yMax = Math.min(18, Math.max(RAW_BITS + 1, Math.ceil(maxBar + 0.5)));
    const x = (c) => M.left + (c / n) * (width - M.left - M.right);
    const y = (b) => height - M.bottom - (Math.min(b, yMax) / yMax) * (height - M.top - M.bottom);
    return { width, height, n, yMax, x, y };
  }

  draw() {
    const { svg } = this;
    const { width, height, n, yMax, x, y } = this._scales();
    if (!width || !height) return;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.replaceChildren();

    // recessive grid + y axis (one axis: everything is in bits)
    for (let b = 0; b <= yMax; b += yMax > 12 ? 4 : 2) {
      svg.appendChild(svgEl("line", { x1: M.left, x2: width - M.right, y1: y(b), y2: y(b), stroke: "#1f2735", "stroke-width": 1 }));
      svg.appendChild(svgEl("text", { x: M.left - 6, y: y(b) + 3.5, "text-anchor": "end", "font-size": 10, fill: "#898781" }, String(b)));
    }
    svg.appendChild(svgEl("line", { x1: M.left, x2: width - M.right, y1: y(0), y2: y(0), stroke: "#383835", "stroke-width": 1 }));
    svg.appendChild(svgEl("line", { x1: M.left, x2: width - M.right, y1: y(RAW_BITS), y2: y(RAW_BITS), stroke: "#898781",
      "stroke-width": 1.2, "stroke-dasharray": "5 4" }));
    svg.appendChild(svgEl("text", { x: width - M.right - 2, y: y(RAW_BITS) - 4, "text-anchor": "end", "font-size": 10, fill: "#898781" },
      "plain text"));

    // x axis: the characters themselves when there is room, positions otherwise
    if (this.chars.length && this.chars.length <= Math.floor((width - M.left - M.right) / 9)) {
      this.chars.forEach((c, i) => svg.appendChild(svgEl("text", {
        x: (x(i) + x(i + 1)) / 2, y: height - M.bottom + 14, "text-anchor": "middle", "font-size": 10,
        "font-family": "ui-monospace, Consolas, monospace", fill: i < this._charsShown() ? "#c3c2b7" : "#4b5563",
      }, displayChar(c))));
    } else {
      const step = n <= 60 ? 10 : n <= 150 ? 25 : 50;
      for (let c = 0; c <= n; c += step) {
        svg.appendChild(svgEl("text", { x: x(c), y: height - M.bottom + 14, "text-anchor": "middle", "font-size": 10, fill: "#898781" }, String(c)));
      }
    }
    svg.appendChild(svgEl("text", { x: (M.left + width - M.right) / 2, y: height - 4, "text-anchor": "middle", "font-size": 10, fill: "#6b7280" },
      "character position"));

    // bars (cost per character) for the encoded part
    const visible = this.groups.filter((g) => g.last < this.cursor);
    const current = visible.length - 1;
    visible.forEach((g, i) => {
      const x0 = x(g.start), x1 = x(g.end);
      const gap = x1 - x0 > 5 ? 1 : 0;  // a thin surface gap between neighbouring bars
      const top = y(g.perChar);
      svg.appendChild(svgEl("rect", { x: x0 + gap, y: top, width: Math.max(1, x1 - x0 - 2 * gap), height: Math.max(0, y(0) - top),
        rx: 2, fill: i === current || i === this.hover ? "#b3a9ff" : "#7b6ee6", "fill-opacity": i === current || i === this.hover ? 1 : 0.78 }));
      if (g.perChar > yMax) {  // clipped: mark the top
        svg.appendChild(svgEl("text", { x: (x0 + x1) / 2, y: top - 3, "text-anchor": "middle", "font-size": 9, fill: "#c3c2b7" }, "▲"));
      }
    });

    // running payload bits per character (the green line)
    if (visible.length) {
      const points = visible.map((g) => `${x(g.end)},${y(g.bitsSoFar / Math.max(1, g.end))}`);
      svg.appendChild(svgEl("polyline", { points: `${x(0)},${y(visible[0].bitsSoFar / Math.max(1, visible[0].end))} ${points.join(" ")}`,
        fill: "none", stroke: "#0ca30c", "stroke-width": 2, "stroke-linejoin": "round" }));
      const last = visible[visible.length - 1];
      const lastY = y(last.bitsSoFar / Math.max(1, last.end));
      svg.appendChild(svgEl("circle", { cx: x(last.end), cy: lastY, r: 4, fill: "#0ca30c", stroke: "#0e1420", "stroke-width": 2 }));
      const value = (last.bitsSoFar / Math.max(1, last.end)).toFixed(2);
      svg.appendChild(svgEl("text", { x: Math.min(x(last.end) + 6, width - M.right - 30), y: lastY - 8, "font-size": 11, fill: "#4ade80",
        "font-weight": 600 }, value));
    }
  }

  _charsShown() {
    const visible = this.groups.filter((g) => g.last < this.cursor);
    return visible.length ? visible[visible.length - 1].end : 0;
  }

  _onMove(e) {
    const rect = this.svg.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const { x } = this._scales();
    const visible = this.groups.filter((g) => g.last < this.cursor);
    const i = visible.findIndex((g) => px >= x(g.start) && px < x(g.end));
    if (i !== this.hover) { this.hover = i; this.draw(); }
    if (i < 0) { this.tooltip.hidden = true; return; }
    const g = visible[i];
    const text = this.chars.slice(g.start, g.end).join("");
    const shown = text.length === 1 ? displayChar(text) : text.replace(/ /g, "␣");
    const p = g.probs.length === 1 ? `the model gave it ${formatOdds(g.probs[0])}` : `${g.symbols} symbols`;
    this.tooltip.innerHTML = `<b>'${escapeHtml(shown)}'</b> · ${p}<br>cost <b>${g.cost.toFixed(2)} bits</b>` +
      (g.end - g.start > 1 ? ` (${g.perChar.toFixed(2)} per char)` : "") +
      `<br>bits sent so far: <b>${g.bitsSoFar}</b> = ${(g.bitsSoFar / Math.max(1, g.end)).toFixed(2)} bits/char`;
    this.tooltip.hidden = false;
    const box = this.container.getBoundingClientRect();
    const parent = this.container.parentElement.getBoundingClientRect();
    const left = Math.min(e.clientX - parent.left + 12, parent.width - 250);
    this.tooltip.style.left = `${Math.max(0, left)}px`;
    this.tooltip.style.top = `${e.clientY - parent.top + 14 - (e.clientY - box.top > box.height - 70 ? 80 : 0)}px`;
  }
}
