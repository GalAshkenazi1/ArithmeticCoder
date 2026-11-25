// The compare page's two charts, both over the characters of the text.
//   MirrorChart:     bits per character. The text runs along the middle; encoder B's bars rise above
//                    it, encoder A's hang below. One bar per symbol, as wide as the characters it
//                    covers, so a word is one wide bar and its height is its cost per character.
//   CumulativeChart: bits used for the first n characters, one line per encoder, plus plain UTF-8.
// Both show a tooltip on hover, seek on click, and mark where the open animation is.

import { displayChar, escapeHtml, svgEl, textWidth } from "./format.js";

const INK = "#f0efec";
const INK_2 = "#c3c2b7";
const MUTED = "#898781";
const GRID = "#1f2735";
const BASELINE = "#383835";
const SURFACE = "#0e1420";
const TEXT_PINK = "#e879b9";
const RAW_BITS = 8;
const MIN_CELL = 11;  // px per character; longer texts scroll sideways

const charLabel = (chars, start, end) => {
  const text = chars.slice(start, end).join("");
  return text.length === 1 ? displayChar(text) : text.replace(/ /g, "␣").replace(/\n/g, "↵");
};

/** A bar with rounded corners at its far end only (square where it meets the baseline). */
function barPath(x, w, base, tip) {
  const r = Math.min(3, w / 2, Math.abs(tip - base));
  const t = tip < base ? tip + r : tip - r;  // where the rounding starts, for bars up or down
  return `M${x},${base} V${t} Q${x},${tip} ${x + r},${tip} H${x + w - r} Q${x + w},${tip} ${x + w},${t} V${base} Z`;
}

/** Where tooltips go: next to the pointer, inside the positioned parent. */
function placeTooltip(tooltip, parent, e, html) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const box = parent.getBoundingClientRect();
  const tip = tooltip.getBoundingClientRect();
  let left = e.clientX - box.left + 14;
  if (left + tip.width > box.width) left = e.clientX - box.left - tip.width - 14;
  tooltip.style.left = `${Math.max(0, left)}px`;
  tooltip.style.top = `${Math.max(0, Math.min(e.clientY - box.top - tip.height / 2, box.height - tip.height))}px`;
}

function sideRow(side, c, chars) {
  if (!side) return "";
  const g = side.groups.find((group) => group.start <= c && c < group.end);
  if (!g) return "";
  let how = "";
  if (g.steps.length > 1) how = ` (${g.steps.length} symbols)`;
  else if (g.end - g.start > 1) how = ` (share of '${escapeHtml(charLabel(chars, g.start, g.end))}')`;
  return `<i class="dot" style="background:${side.color}"></i>${escapeHtml(side.short)}: <b>${g.perChar.toFixed(2)} bits</b>${how}`;
}

export class MirrorChart {
  static M = { left: 34, right: 10, top: 10, bottom: 10, band: 30 };

  constructor(scroller, svg, tooltip, { onSeek } = {}) {
    Object.assign(this, { scroller, svg, tooltip, onSeek: onSeek ?? (() => {}) });
    this.sides = { top: null, bottom: null };
    this.chars = [];
    this.hover = -1;
    this.highlight = null;  // { side: "top" | "bottom", start, end }
    new ResizeObserver(() => this.draw()).observe(scroller);
    scroller.addEventListener("scroll", () => this.draw());  // the side labels stay at the visible left edge
    // phones: a tap shows the tooltip (there is no hover), a tap elsewhere hides it
    svg.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") this._onMove(e); });
    document.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" && this.hover >= 0 && !svg.contains(e.target)) { this.hover = -1; this.tooltip.hidden = true; this.draw(); }
    });
    svg.addEventListener("mousemove", (e) => this._onMove(e));
    svg.addEventListener("mouseleave", () => { this.hover = -1; this.tooltip.hidden = true; this.draw(); });
    svg.addEventListener("click", () => { if (this.hover >= 0) this.onSeek(this.hover + 1, this.hoverSide); });
  }

  /**
   * sides: { top, bottom }, each { color, short, groups } or null (that encoder can't encode the text).
   * words: [{ start, end, text, top, bottom, winner }]: each word is tinted by the side that paid less.
   */
  setData(sides, chars, words = []) {
    this.sides = sides;
    this.chars = chars;
    this.words = words;
    this.hover = -1;
    this.tooltip.hidden = true;
    this.scroller.scrollLeft = 0;
    this.draw();
  }

  setHighlight(highlight) {
    this.highlight = highlight;
    this.draw();
    if (!highlight) return;
    const { x } = this._geometry();  // keep the current symbol in view when the chart scrolls
    const left = x(highlight.start) - 40;
    const right = x(highlight.end) + 40;
    if (left < this.scroller.scrollLeft || right > this.scroller.scrollLeft + this.scroller.clientWidth) {
      this.scroller.scrollLeft = left;
    }
  }

  _geometry() {
    const M = MirrorChart.M;
    const n = Math.max(this.chars.length, 1);
    const available = this.scroller.clientWidth;
    const cell = Math.max((available - M.left - M.right) / n, MIN_CELL);
    const width = Math.max(available, M.left + M.right + cell * n);
    const height = this.scroller.clientHeight;
    const half = (height - M.top - M.bottom - M.band) / 2;
    const midTop = M.top + half;
    const midBottom = midTop + M.band;
    const sides = [this.sides.top, this.sides.bottom].filter(Boolean);
    const top = Math.max(RAW_BITS + 1, ...sides.flatMap((s) => s.groups.map((g) => g.perChar)));
    const max = Math.min(20, Math.ceil(top + 0.5));
    const h = (v) => (Math.min(v, max) / max) * half;
    return { M, n, cell, width, height, half, midTop, midBottom, max, h, x: (c) => M.left + c * cell };
  }

  draw() {
    const svg = this.svg;
    const g = this._geometry();
    const { M, cell, width, height, midTop, midBottom, max, h, x } = g;
    if (!this.scroller.clientWidth || !height) return;
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.replaceChildren();
    const right = width - M.right;

    // grid both ways from the text band, and the plain-byte reference
    for (let v = 4; v <= max; v += 4) {
      for (const [y, anchor] of [[midTop - h(v), "up"], [midBottom + h(v), "down"]]) {
        svg.appendChild(svgEl("line", { x1: M.left, x2: right, y1: y, y2: y, stroke: v === RAW_BITS ? MUTED : GRID,
          "stroke-dasharray": v === RAW_BITS ? "5 4" : "", "stroke-width": v === RAW_BITS ? 1.1 : 1 }));
        svg.appendChild(svgEl("text", { x: M.left - 6, y: y + 3.5, "text-anchor": "end", "font-size": 10, fill: MUTED,
          "data-side": anchor }, String(v)));
      }
    }
    for (const y of [midTop, midBottom]) svg.appendChild(svgEl("line", { x1: M.left, x2: right, y1: y, y2: y, stroke: BASELINE }));

    // hovered column, and the animation's current symbol in the text band
    if (this.hover >= 0) {
      svg.appendChild(svgEl("rect", { x: x(this.hover), y: M.top, width: cell, height: height - M.top - M.bottom, fill: "#1d2638" }));
    }
    // each word, tinted by the encoder that paid less for it (a band behind it, a bar on that side)
    for (const w of this.words ?? []) {
      const side = w.winner && this.sides[w.winner];
      if (!side) continue;
      svg.appendChild(svgEl("rect", { x: x(w.start) + 1, y: midTop + 3, width: (w.end - w.start) * cell - 2, height: M.band - 6,
        rx: 4, fill: side.color, "fill-opacity": 0.16 }));
      svg.appendChild(svgEl("rect", { x: x(w.start) + 2, y: w.winner === "top" ? midTop + 3 : midBottom - 5,
        width: (w.end - w.start) * cell - 4, height: 2, rx: 1, fill: side.color }));
    }
    if (this.highlight) {
      svg.appendChild(svgEl("rect", { x: x(this.highlight.start), y: midTop + 2, width: (this.highlight.end - this.highlight.start) * cell,
        height: M.band - 4, rx: 4, fill: "rgba(144,133,233,0.28)" }));
    }

    // bars: one per symbol group, above the text for the top encoder and below it for the bottom one
    for (const [key, side] of Object.entries(this.sides)) {
      if (!side) continue;
      const up = key === "top";
      for (const group of side.groups) {
        const gap = cell > 6 ? 2 : 1;
        const x0 = x(group.start) + gap / 2;
        const w = (group.end - group.start) * cell - gap;
        const base = up ? midTop - 1 : midBottom + 1;
        const tip = up ? base - h(group.perChar) : base + h(group.perChar);
        const lit = this.highlight?.side === key && this.highlight.start === group.start;
        svg.appendChild(svgEl("path", { d: barPath(x0, w, base, tip), fill: side.color,
          "fill-opacity": this.highlight && !lit ? 0.45 : 0.9, stroke: lit ? INK : "none", "stroke-width": 1.5 }));
        if (group.perChar > max) {
          svg.appendChild(svgEl("text", { x: x0 + w / 2, y: up ? tip - 3 : tip + 10, "text-anchor": "middle", "font-size": 8,
            fill: INK_2 }, up ? "▲" : "▼"));
        }
      }
    }

    if (RAW_BITS <= max) {  // what the dashed line means, at the visible right edge, on a backing
      const text = "8 bits = one plain byte";
      const w = textWidth(text, 10, false) + 8;
      const lx = Math.min(right, this.scroller.scrollLeft + this.scroller.clientWidth - M.right) - w;
      const ly = midTop - h(RAW_BITS);
      svg.appendChild(svgEl("rect", { x: lx, y: ly - 14, width: w, height: 13, rx: 3, fill: SURFACE, "fill-opacity": 0.88 }));
      svg.appendChild(svgEl("text", { x: lx + w - 4, y: ly - 4, "text-anchor": "end", "font-size": 10, fill: MUTED }, text));
    }

    // the text itself, one character per column
    const size = Math.min(15, cell * 1.15);
    this.chars.forEach((ch, i) => svg.appendChild(svgEl("text", {
      x: x(i) + cell / 2, y: midTop + M.band / 2 + size * 0.36, "text-anchor": "middle", "font-size": size,
      "font-family": "ui-monospace, Consolas, monospace", fill: ch === " " || ch === "\n" ? "#8a4f6e" : TEXT_PINK,
    }, displayChar(ch))));

    // which encoder is on which side (direct labels, on a backing so bars don't run through them)
    const label = (text, y, color) => {
      const w = textWidth(text, 11, false) + 22;
      const lx = this.scroller.scrollLeft + M.left + 4;
      svg.appendChild(svgEl("rect", { x: lx, y: y - 11, width: w, height: 16, rx: 4, fill: SURFACE, "fill-opacity": 0.88 }));
      svg.appendChild(svgEl("rect", { x: lx + 5, y: y - 6.5, width: 9, height: 9, rx: 2, fill: color }));
      svg.appendChild(svgEl("text", { x: lx + 18, y: y + 1.5, "font-size": 11, fill: INK_2, "font-weight": 600 }, text));
    };
    if (this.sides.top) label(this.sides.top.short, M.top + 10, this.sides.top.color);
    if (this.sides.bottom) label(this.sides.bottom.short, height - M.bottom - 6, this.sides.bottom.color);
  }

  _onMove(e) {
    const rect = this.svg.getBoundingClientRect();
    const { M, cell } = this._geometry();
    const { midTop } = this._geometry();
    const c = Math.floor((e.clientX - rect.left - M.left) / cell);
    const index = c >= 0 && c < this.chars.length ? c : -1;
    this.hoverSide = e.clientY - rect.top < midTop + M.band / 2 ? "top" : "bottom";  // which encoder a click opens
    if (index !== this.hover) { this.hover = index; this.draw(); }
    if (index < 0) { this.tooltip.hidden = true; return; }
    const rows = [sideRow(this.sides.top, index, this.chars), sideRow(this.sides.bottom, index, this.chars)].filter(Boolean);
    const word = (this.words ?? []).find((w) => w.start <= index && index < w.end);
    if (word && word.top !== null && word.bottom !== null) {
      const who = word.winner ? `${escapeHtml(this.sides[word.winner].short)} pays less` : "a tie";
      rows.push(`<span class="muted">the word '${escapeHtml(word.text)}': ${word.top.toFixed(1)} vs ${word.bottom.toFixed(1)} bits, ${who}</span>`);
    }
    placeTooltip(this.tooltip, this.scroller.closest(".chart"), e,
      `<b>'${escapeHtml(displayChar(this.chars[index]))}'</b> · character ${index + 1}<br>${rows.join("<br>")}`);
  }
}

export class CumulativeChart {
  static M = { left: 46, right: 104, top: 24, bottom: 30 };  // right: room for the line-end labels

  constructor(area, svg, tooltip, { onSeek } = {}) {
    Object.assign(this, { area, svg, tooltip, onSeek: onSeek ?? (() => {}) });
    this.series = [];
    this.chars = [];
    this.utf8 = [0];
    this.marker = null;
    this.hover = -1;
    new ResizeObserver(() => this.draw()).observe(area);
    // phones: a tap shows the tooltip (there is no hover), a tap elsewhere hides it
    svg.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") this._onMove(e); });
    document.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" && this.hover >= 0 && !svg.contains(e.target)) { this.hover = -1; this.tooltip.hidden = true; this.draw(); }
    });
    svg.addEventListener("mousemove", (e) => this._onMove(e));
    svg.addEventListener("mouseleave", () => { this.hover = -1; this.tooltip.hidden = true; this.draw(); });
    svg.addEventListener("click", () => { if (this.hover >= 0) this.onSeek(this.hover); });
  }

  /** series: [{ color, short, cumulative }] (cumulative[c] = bits for the first c characters). */
  setData(series, chars, utf8Cumulative) {
    Object.assign(this, { series, chars, utf8: utf8Cumulative });
    this.hover = -1;
    this.tooltip.hidden = true;
    this.draw();
  }

  /** The animation's position: a guide after the first c characters (null: none). */
  setMarker(c) {
    this.marker = c;
    this.draw();
  }

  _geometry() {
    const M = CumulativeChart.M;
    const width = this.area.clientWidth;
    const height = this.area.clientHeight;
    const n = Math.max(this.chars.length, 1);
    // scaled to the encoders (plain UTF-8 is usually far above them and would flatten both lines)
    const encoders = Math.max(...this.series.map((s) => s.cumulative[this.chars.length] ?? 0), 0);
    const plain = this.utf8[this.chars.length] ?? 0;
    const top = encoders ? Math.max(encoders, Math.min(encoders * 1.6, plain)) : Math.max(plain, 1);
    const raw = (top * 1.04) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw);
    const max = Math.ceil((top * 1.04) / step) * step;
    const x = (c) => M.left + (c / n) * (width - M.left - M.right);
    const y = (v) => height - M.bottom - (v / max) * (height - M.top - M.bottom);
    return { M, width, height, n, max, step, x, y };
  }

  draw() {
    const svg = this.svg;
    const { M, width, height, n, max, step, x, y } = this._geometry();
    if (!width || !height) return;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.replaceChildren();
    for (let v = 0; v <= max + 1e-9; v += step) {
      svg.appendChild(svgEl("line", { x1: M.left, x2: width - M.right, y1: y(v), y2: y(v), stroke: v ? GRID : BASELINE }));
      svg.appendChild(svgEl("text", { x: M.left - 6, y: y(v) + 3.5, "text-anchor": "end", "font-size": 10, fill: MUTED },
        String(Math.round(v * 10) / 10)));
    }
    svg.appendChild(svgEl("text", { x: M.left - 6, y: M.top - 12, "text-anchor": "end", "font-size": 10, fill: MUTED }, "bits"));
    const tickStep = n <= 20 ? 5 : n <= 60 ? 10 : n <= 150 ? 25 : 50;
    for (let c = 0; c <= n; c += tickStep) {
      svg.appendChild(svgEl("text", { x: x(c), y: height - M.bottom + 14, "text-anchor": "middle", "font-size": 10, fill: MUTED }, String(c)));
    }
    svg.appendChild(svgEl("text", { x: width - M.right, y: height - M.bottom + 14, "text-anchor": "start", "font-size": 10,
      fill: "#6b7280", dx: 6 }, "chars"));
    const len = this.chars.length;
    if (!len) return;

    // plain UTF-8, the reference both encoders should beat: drawn until it leaves the top of the plot
    const exit = this.utf8.findIndex((v) => v > max);
    const shown = exit < 0 ? this.utf8 : this.utf8.slice(0, exit + 1);
    const points = shown.map((v, c) => [x(c), y(v)]);
    if (exit > 0) {  // end exactly on the top edge
      const [v0, v1] = [this.utf8[exit - 1], this.utf8[exit]];
      points[exit] = [x(exit - 1 + (max - v0) / (v1 - v0)), y(max)];
    }
    svg.appendChild(svgEl("polyline", { points: points.map((pt) => pt.join(",")).join(" "), fill: "none",
      stroke: MUTED, "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
    const ends = [];
    if (exit < 0) ends.push({ text: `plain ${this.utf8[len]}`, y: y(this.utf8[len]), color: null });
    else {
      const [ex] = points[points.length - 1];
      const text = `plain UTF-8 ↑ (${this.utf8[len]} bits at the end)`;
      const fitsRight = ex + 6 + textWidth(text, 10, false) <= width - 4;
      svg.appendChild(svgEl("text", { x: fitsRight ? ex + 6 : ex - 6, y: M.top + 10, "text-anchor": fitsRight ? "start" : "end",
        "font-size": 10, fill: MUTED }, text));
    }

    if (this.marker !== null && this.marker > 0 && this.marker < len) {
      svg.appendChild(svgEl("line", { x1: x(this.marker), x2: x(this.marker), y1: M.top, y2: y(0), stroke: "#9085e9",
        "stroke-dasharray": "3 3" }));
    }
    for (const s of this.series) {
      svg.appendChild(svgEl("polyline", { points: s.cumulative.map((v, c) => `${x(c)},${y(v)}`).join(" "), fill: "none",
        stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round" }));
      svg.appendChild(svgEl("circle", { cx: x(len), cy: y(s.cumulative[len]), r: 4, fill: s.color, stroke: SURFACE, "stroke-width": 2 }));
      ends.push({ text: `${s.short} ${s.cumulative[len].toFixed(1)}`, y: y(s.cumulative[len]), color: s.color });
    }
    // line-end labels, nudged apart so they never overlap, kept inside the plot
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 15);
    for (let i = ends.length - 1; i >= 0; i--) ends[i].y = Math.min(ends[i].y, i === ends.length - 1 ? y(0) : ends[i + 1].y - 15);
    for (const end of ends) {
      svg.appendChild(svgEl("text", { x: x(len) + 8, y: end.y + 4, "font-size": 11, fill: end.color ? INK_2 : MUTED,
        "font-weight": end.color ? 600 : 400 }, end.text));
    }

    if (this.hover >= 0) {
      const c = this.hover;
      svg.appendChild(svgEl("line", { x1: x(c), x2: x(c), y1: M.top, y2: y(0), stroke: "#59647a" }));
      for (const s of this.series) {
        svg.appendChild(svgEl("circle", { cx: x(c), cy: y(s.cumulative[c]), r: 4, fill: s.color, stroke: SURFACE, "stroke-width": 2 }));
      }
    }
  }

  _onMove(e) {
    const rect = this.svg.getBoundingClientRect();
    const { M, width, n, x } = this._geometry();
    const px = e.clientX - rect.left;
    const len = this.chars.length;
    const c = !len || px < x(0) - 8 || px > x(n) + 8 ? -1
      : Math.max(0, Math.min(len, Math.round(((px - M.left) / (width - M.left - M.right)) * n)));
    if (c !== this.hover) { this.hover = c; this.draw(); }
    if (c < 0) { this.tooltip.hidden = true; return; }
    const head = c ? `first <b>${c}</b> char${c === 1 ? "" : "s"}: '${escapeHtml(charLabel(this.chars, Math.max(0, c - 12), c))}'` : "start";
    const rows = this.series.map((s) => `<i class="dot" style="background:${s.color}"></i>${escapeHtml(s.short)}: ` +
      `<b>${s.cumulative[c].toFixed(1)} bits</b>${c ? ` (${(s.cumulative[c] / c).toFixed(2)}/char)` : ""}`);
    rows.push(`<i class="dot ref"></i>plain UTF-8: <b>${this.utf8[c]} bits</b>`);
    placeTooltip(this.tooltip, this.area.parentElement, e, `${head}<br>${rows.join("<br>")}`);
  }
}
