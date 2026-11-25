// Coding animation: one number line per encoded symbol, stacked top to bottom.
//
// Row i shows the window before symbol i, split into the model's probabilities (the boxes under the
// line, in the coder's real slot order). The chosen symbol's box is violet; its bounds are labelled
// above the line. Row i+1 is that box stretched to the full width (the funnel shows the zoom). The
// green dot is the best binary fraction: the shortest binary number inside the chosen slice.
//
// Decode mode shows the receiver instead: the word column holds only what has been decoded so far,
// and the green dot is the received number, which falls inside exactly one box per row.

import { displayChar, displaySymbol, escapeHtml, formatCost, formatDecimal, formatOdds, fractionLabel, svgEl,
  textWidth } from "./format.js";
import { showTipAt } from "./glossary.js";

const ROW_H = 84;      // px; boxes end exactly at the bottom, so the next row's funnel starts there
const LINE_Y = 46;
const BOX_Y = 56;
const BOX_H = 28;
const PAD = 12;
const WORD_BEFORE = 9;  // characters of context shown before the current symbol in the word column
const WORD_AFTER = 6;
const BASE_ZOOM_MS = 650;

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export class Ladder {
  /**
   * wordBefore / wordAfter: characters of context around the current symbol in the word column.
   * mode: "encode" (the sender's view) or "decode" (the receiver's: no text ahead, the received number).
   */
  constructor(container, { wordBefore = WORD_BEFORE, wordAfter = WORD_AFTER, mode = "encode" } = {}) {
    this.container = container;
    this.wordBefore = wordBefore;
    this.wordAfter = wordAfter;
    this.mode = mode;
    this.text = "";
    this.chars = [];     // the text as code points: the trace's char_start / char_end index these
    this.trace = [];
    this.rows = [];      // rendered row elements, rows[i] shows trace[i]
    this.speed = 1;
    this.width = 0;
    new ResizeObserver(() => this._relayout()).observe(container);
    container.addEventListener("click", (e) => this._tapBox(e));
    this._empty();
  }

  get count() { return this.rows.length; }

  /** New text/trace. Rows of the unchanged leading symbols are kept; returns how many were kept. */
  setData(text, trace) {
    let keep = 0;
    while (keep < Math.min(this.rows.length, trace.length)
      && trace[keep].symbol_id === this.trace[keep].symbol_id
      && trace[keep].char_start === this.trace[keep].char_start) keep++;
    this.text = text;
    this.chars = [...text];
    this.trace = trace;
    this.truncate(keep);
    this.rows.forEach((row, i) => this._fillWord(row, i));  // later text may have changed
    if (!trace.length) this._empty();
    return keep;
  }

  /** Remove rows from index n on. */
  truncate(n) {
    while (this.rows.length > n) this.rows.pop().remove();
    this._markLatest();
    if (!this.rows.length) this._empty();
  }

  /** Add the next row; with animate, it grows out of the previous row's chosen slice. */
  async appendRow(animate = true) {
    const i = this.rows.length;
    if (i >= this.trace.length) return;
    this.container.querySelector(".ladder-empty")?.remove();
    const row = this._renderRow(i);
    this.rows.push(row);
    this.container.appendChild(row);
    this._markLatest();
    this.container.scrollTop = this.container.scrollHeight;  // only the ladder scrolls, not the page
    if (animate) await this._zoomIn(row, i);
  }

  /** A click or tap on a row: say which box it hit and what that symbol costs (phones show no SVG titles). */
  _tapBox(e) {
    const row = e.target.closest(".row");
    const i = this.rows.indexOf(row);
    const svg = row?.querySelector("svg");
    if (i < 0 || !svg) return;
    const rel = (e.clientX - svg.getBoundingClientRect().left - PAD) / (this.width - 2 * PAD);
    const seg = this.trace[i].top_segments.find((s) => s.rel_start <= rel && rel < s.rel_end);
    if (!seg) return;
    const what = seg.char === null ? `${seg.count} other symbols, together ${formatOdds(seg.prob)}`
      : `<b>'${escapeHtml(displaySymbol(seg.char))}'</b>: ${escapeHtml(formatOdds(seg.prob))} → ${formatCost(seg.prob)}`;
    showTipAt(`${what}${seg.is_selected ? "<br>the symbol that came next" : ""}`, e);
  }

  // ---- rendering ---------------------------------------------------------------------------

  _width() {
    const style = getComputedStyle(this.container);
    const inner = this.container.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    const wordCol = parseFloat(style.getPropertyValue("--word-col")) || 150;  // set in app.css
    return Math.max(160, inner - wordCol - 2);
  }

  _relayout() {
    const width = this._width();
    if (Math.abs(width - this.width) < 2) return;
    this.width = width;
    const n = this.rows.length;
    this.rows.forEach((row) => row.remove());
    this.rows = [];
    for (let i = 0; i < n; i++) {
      const row = this._renderRow(i);
      this.rows.push(row);
      this.container.appendChild(row);
    }
    this._markLatest();
  }

  _empty() {
    if (this.container.querySelector(".ladder-empty")) return;
    const note = document.createElement("div");
    note.className = "ladder-empty";
    note.textContent = this.mode === "decode" ? "The receiver starts from the same [0, 1) and the same model."
      : "Every message starts as the whole interval [0, 1). Type something to watch it shrink.";
    this.container.appendChild(note);
  }

  _markLatest() {
    this.rows.forEach((row, i) => row.classList.toggle("latest", i === this.rows.length - 1));
  }

  _fillWord(row, i) {
    const t = this.trace[i];
    const chars = this.chars;
    const { wordBefore, wordAfter } = this;
    const before = chars.slice(Math.max(0, t.char_start - wordBefore), t.char_start).join("");
    const current = chars.slice(t.char_start, t.char_end).join("");
    const decode = this.mode === "decode";  // the receiver doesn't know what comes next
    const after = decode ? "" : chars.slice(t.char_end, t.char_end + wordAfter).join("");
    const ellBefore = t.char_start > wordBefore ? '<span class="ell">…</span>' : "";
    const ellAfter = !decode && t.char_end + wordAfter < chars.length ? '<span class="ell">…</span>' : "";
    const shown = current.length === 1 ? displayChar(current) : current.replace(/ /g, "␣");
    const sent = t.bits_added === 0
      ? '<span class="free">+0 bits sent</span>' : `+${t.bits_added} bit${t.bits_added === 1 ? "" : "s"} sent`;
    // receiver: the dot fell in this symbol's box, which takes up P of the line
    const box = t.prob >= 0.5 ? `${Math.round(100 * t.prob)}%` : `1/${Math.round(1 / t.prob).toLocaleString("en-US")}`;
    const meta = decode ? `dot in its box: ${box} of the line` : `${escapeHtml(formatOdds(t.prob))} → ${formatCost(t.prob)}`;
    row.querySelector(".word").innerHTML =
      `${ellBefore}<span class="done">${escapeHtml(before)}</span><span class="current">${escapeHtml(shown)}</span>` +
      `<span class="todo">${escapeHtml(after)}</span>${ellAfter}` +
      `<span class="step-meta">${meta}</span>${decode ? "" : `<span class="step-meta">${sent}</span>`}`;
  }

  _renderRow(i) {
    if (!this.width) this.width = this._width();
    const t = this.trace[i];
    const prev = this.trace[i - 1];
    const W = this.width;
    const X = (rel) => PAD + rel * (W - 2 * PAD);

    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = '<div class="word"></div>';
    this._fillWord(row, i);
    const svg = svgEl("svg", { width: W, height: ROW_H, viewBox: `0 0 ${W} ${ROW_H}` });

    // funnel: the previous row's chosen slice, stretched to this row's full line
    if (prev) {
      const x0 = X(prev.sub_l_rel), x1 = X(prev.sub_h_rel);
      svg.appendChild(svgEl("polygon", {
        points: `${x0},0 ${x1},0 ${X(1)},${LINE_Y} ${X(0)},${LINE_Y}`,
        fill: "rgba(144,133,233,0.09)", stroke: "rgba(144,133,233,0.35)", "stroke-width": 1, class: "funnel",
      }));
    }

    const zoom = svgEl("g", { class: "zoom" });  // everything that stretches during the animation
    zoom.appendChild(svgEl("line", { x1: X(0), x2: X(1), y1: LINE_Y, y2: LINE_Y, stroke: "#c3c2b7", "stroke-width": 1.5,
      "vector-effect": "non-scaling-stroke" }));
    for (const x of [X(0), X(1)]) {
      zoom.appendChild(svgEl("line", { x1: x, x2: x, y1: LINE_Y - 6, y2: LINE_Y + 6, stroke: "#c3c2b7", "stroke-width": 1.5,
        "vector-effect": "non-scaling-stroke" }));
    }
    for (const seg of t.top_segments) {
      const x0 = X(seg.rel_start), x1 = X(seg.rel_end);
      const w = x1 - x0;
      if (w < 1.5 && !seg.is_selected) continue;
      const rect = svgEl("rect", { x: x0 + (w > 4 ? 1 : 0), y: BOX_Y, width: Math.max(1, w - (w > 4 ? 2 : 0)), height: BOX_H, rx: 4,
        "vector-effect": "non-scaling-stroke" });
      if (seg.char === null) rect.setAttribute("class", "other");
      if (seg.is_selected) Object.entries({ fill: "#9085e9", stroke: "#c9c2ff", "stroke-width": 1.5 }).forEach(([k, v]) => rect.setAttribute(k, v));
      else if (seg.char === null) Object.entries({ fill: "#1a2130", stroke: "#2c3546", "stroke-width": 1 }).forEach(([k, v]) => rect.setAttribute(k, v));
      else Object.entries({ fill: "rgba(213,81,129,0.10)", stroke: "rgba(213,81,129,0.65)", "stroke-width": 1 }).forEach(([k, v]) => rect.setAttribute(k, v));
      const title = svgEl("title", {}, seg.char === null ? `${seg.count} other symbols: ${formatProb(seg.prob)} together`
        : `'${displaySymbol(seg.char)}': ${formatOdds(seg.prob)} → ${formatCost(seg.prob)}`);
      rect.appendChild(title);
      zoom.appendChild(rect);
    }
    // ticks at the chosen slice's bounds
    for (const rel of [t.sub_l_rel, t.sub_h_rel]) {
      zoom.appendChild(svgEl("line", { x1: X(rel), x2: X(rel), y1: LINE_Y - 7, y2: LINE_Y + 7, stroke: "#9085e9",
        "stroke-width": 2, "vector-effect": "non-scaling-stroke" }));
    }
    svg.appendChild(zoom);

    // labels (not stretched; they fade in once the zoom is done)
    const labels = svgEl("g", { class: "labels" });
    this._boxLabels(labels, t, X);
    this._boundLabels(labels, t, prev, X, W);
    // the best binary fraction (sender) or the received number (receiver): a green dot on the line
    const decode = this.mode === "decode";
    const dotRel = decode ? t.received_rel_before ?? t.r_rel_before : t.r_rel_before;
    const dotX = X(Math.min(1, Math.max(0, dotRel)));
    labels.appendChild(svgEl("circle", { cx: dotX, cy: LINE_Y, r: 5, fill: "#0ca30c", stroke: "#0e1420", "stroke-width": 2 }));
    const best = svgEl("g", { class: decode ? "best-label received" : "best-label" });
    const bestText = decode ? "the received number is in this box" : `best binary ${fractionLabel(t.running_bits)}`;
    const bw = textWidth(bestText, 11, false);
    const bx = Math.min(Math.max(dotX - bw / 2, 2), W - bw - 2);
    best.appendChild(svgEl("line", { x1: dotX, x2: dotX, y1: 16, y2: LINE_Y - 7, stroke: "#0ca30c", "stroke-width": 1.2 }));
    best.appendChild(svgEl("text", { x: bx, y: 12, fill: "#4ade80", "font-size": 11 }, bestText));
    labels.appendChild(best);
    svg.appendChild(labels);

    row.appendChild(svg);
    return row;
  }

  /** Symbol labels inside the boxes, when they fit. */
  _boxLabels(group, t, X) {
    for (const seg of t.top_segments) {
      const w = X(seg.rel_end) - X(seg.rel_start);
      const label = seg.char === null ? (w > 26 ? "…" : "") : displaySymbol(seg.char);
      if (!label || textWidth(label, 12) > w - 4) continue;
      group.appendChild(svgEl("text", {
        x: X((seg.rel_start + seg.rel_end) / 2), y: BOX_Y + BOX_H / 2 + 4, "text-anchor": "middle",
        "font-size": 12, "font-family": "ui-monospace, Consolas, monospace",
        "font-weight": seg.is_selected ? 700 : 400, fill: seg.is_selected ? "#0e1420" : seg.char === null ? "#6b7280" : "#f2b8cf",
      }, label));
    }
  }

  /** Decimal labels above the line: the chosen slice's bounds first, then the window's ends if room. */
  _boundLabels(group, t, prev, X, W) {
    const y = LINE_Y - 12;
    const placed = [];
    const fits = (x0, x1) => x0 >= 0 && x1 <= W && placed.every(([a, b]) => x1 + 6 < a || x0 > b + 6);
    // try each (x, anchor) option in turn; keep the first that fits without touching earlier labels
    const put = (text, options, color, full) => {
      const w = textWidth(text, 11);
      for (const [x, anchor] of options) {
        const x0 = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
        if (!fits(x0, x0 + w)) continue;
        placed.push([x0, x0 + w]);
        const el = svgEl("text", { x, y, "text-anchor": anchor, "font-size": 11, fill: color, class: "dec",
          "font-family": "ui-monospace, Consolas, monospace" }, text);
        el.appendChild(svgEl("title", {}, full));
        group.appendChild(el);
        return true;
      }
      return false;
    };
    const lo = formatDecimal(t.l_dec_after, t.dec_shared_after);
    const hi = formatDecimal(t.h_dec_after, t.dec_shared_after);
    // the chosen bounds hug their ticks (outside first, then inside the slice), so they don't cover each other
    const xl = X(t.sub_l_rel), xh = X(t.sub_h_rel);
    put(lo, [[xl - 3, "end"], [xl + 3, "start"]], "#c9c2ff", t.l_dec_after);
    put(hi, [[xh + 3, "start"], [xh - 3, "end"]], "#c9c2ff", t.h_dec_after);
    const left = prev ? formatDecimal(prev.l_dec_after, prev.dec_shared_after) : "0";
    const right = prev ? formatDecimal(prev.h_dec_after, prev.dec_shared_after) : "1";
    put(left, [[X(0) - 2, "start"]], "#898781", prev ? prev.l_dec_after : "0");
    put(right, [[X(1) + 2, "end"]], "#898781", prev ? prev.h_dec_after : "1");
  }

  // ---- animation ---------------------------------------------------------------------------

  /** Stretch the new row's line + boxes from the previous row's chosen slice to the full width. */
  _zoomIn(row, i) {
    const prev = this.trace[i - 1];
    const zoom = row.querySelector(".zoom");
    const funnel = row.querySelector(".funnel");
    const W = this.width;
    const X = (rel) => PAD + rel * (W - 2 * PAD);
    const from0 = prev ? X(prev.sub_l_rel) : X(0.5) - 2;
    const from1 = prev ? X(prev.sub_h_rel) : X(0.5) + 2;
    row.classList.add("entering");
    if (funnel) funnel.style.opacity = "0";
    const duration = BASE_ZOOM_MS / this.speed;
    return new Promise((resolve) => {
      const start = performance.now();
      const frame = (now) => {
        const e = easeInOut(Math.min(1, (now - start) / duration));
        const x0 = from0 + (X(0) - from0) * e;
        const x1 = from1 + (X(1) - from1) * e;
        const k = (x1 - x0) / (X(1) - X(0));
        zoom.setAttribute("transform", `translate(${x0 - X(0) * k} 0) scale(${k} 1)`);
        if (funnel) funnel.style.opacity = String(e);
        if (e < 1) requestAnimationFrame(frame);
        else {
          zoom.removeAttribute("transform");
          row.classList.remove("entering");
          resolve();
        }
      };
      requestAnimationFrame(frame);
    });
  }
}

function formatProb(p) {
  // "23%", "4.4%", "0.05%", "0.00001%" (one significant digit for tiny probabilities)
  return p >= 0.1 ? `${(p * 100).toFixed(0)}%` : p >= 0.01 ? `${(p * 100).toFixed(1)}%` : `${(p * 100).toPrecision(1)}%`;
}
