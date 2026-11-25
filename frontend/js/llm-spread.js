// The start page's "all together" animation, one symbol at a time:
//   1. the text so far goes into the language model;
//   2. the model gives every possible next symbol a probability (the bars);
//   3. the probabilities spread over the current range as slices, each as wide as its probability;
//   4. the real next symbol's slice is chosen, and it zooms out to become the new range.
// Everything is drawn in one SVG with a fixed viewBox, so it scales with the stage. Wide stages lay
// the pieces out left to right; narrow ones (phones) stack them, so the text stays readable.

import { avatarSvg, persona } from "./encoders.js";
import { displaySymbol, formatCost, formatDecimal, formatOdds, svgEl } from "./format.js";

const TOP_K = 5;  // bars for the likeliest symbols, plus one for "everything else"
const MONO = "ui-monospace, Consolas, monospace";
const VIOLET = "#9085e9";
const PINK = "#d55181";
const NARROW_BELOW = 560;  // px of stage width

/** Where everything goes, side by side (wide) or stacked (narrow). */
const LAYOUTS = {
  wide: {
    W: 640, H: 340,
    textCaption: [16, 28], textBox: { x: 16, y: 38, w: 140, h: 52 }, prefix: [30, 71, 20],
    arrow1: [160, 64, 194, 64],
    model: { x: 200, y: 24, w: 184, h: 80, face: [210, 42, 1.1], title: [262, 56, 13], sub: [262, 72, 11], status: [262, 90, 10.5] },
    arrow2: [388, 64, 418, 64],
    barsCaption: [432, 28], bars: { x: 446, w: 118, y0: 40, dy: 20, label: 13, odds: 10 },
    spreadPath: "M 486 166 C 486 190, 380 182, 320 204",
    rangeCaption: [24, 196, "the range: every message that starts with the text so far"],
    line: { x0: 24, x1: 616, y: 236 }, seg: { y: 246, h: 32 },
    choice: [320, 300, 13], bits: [320, 322, 12],
  },
  narrow: {
    W: 360, H: 470,
    textCaption: [16, 22], textBox: { x: 16, y: 30, w: 136, h: 48 }, prefix: [28, 61, 19],
    arrow1: [156, 54, 174, 54],
    model: { x: 178, y: 22, w: 166, h: 64, face: [184, 34, 0.95], title: [228, 47, 12], sub: [228, 61, 10], status: [228, 76, 9.5] },
    arrow2: [261, 90, 261, 108],
    barsCaption: [16, 122], bars: { x: 54, w: 190, y0: 132, dy: 22, label: 14, odds: 11 },
    spreadPath: "M 150 268 C 150 290, 180 286, 180 304",
    rangeCaption: [16, 324, "the range"],
    line: { x0: 16, x1: 344, y: 356 }, seg: { y: 366, h: 34 },
    choice: [180, 426, 12.5], bits: [180, 450, 11],
  },
};

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Animate fn(e) for e from 0 to 1 over ms (eased); ends early when stale() says so. */
function tween(ms, fn, stale) {
  return new Promise((resolve) => {
    const start = performance.now();
    const frame = (now) => {
      if (stale()) { resolve(); return; }
      const t = Math.min(1, (now - start) / ms);
      fn(ease(t));
      if (t < 1) requestAnimationFrame(frame); else resolve();
    };
    requestAnimationFrame(frame);
  });
}

const mix = (a, b, e) => a + (b - a) * e;
const setAttrs = (el, attrs) => { for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v); };

export class SpreadAnimation {
  constructor(container) {
    this.container = container;
    this.svg = svgEl("svg", { class: "spread-svg", role: "img", "aria-label": "the language model's probabilities spread over the range" });
    container.appendChild(this.svg);
    this.L = LAYOUTS.wide;
  }

  _lineX(rel) {
    const { x0, x1 } = this.L.line;
    return x0 + rel * (x1 - x0);
  }

  /** The fixed parts: the text box, the model, the arrows and the captions. */
  _scene(model) {
    const L = this.L;
    const svg = this.svg;
    svg.setAttribute("viewBox", `0 0 ${L.W} ${L.H}`);
    svg.replaceChildren();
    const defs = svgEl("defs");
    defs.innerHTML = `<marker id="spread-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M0,0 L10,5 L0,10 z" fill="#59647a"/></marker>
      <clipPath id="spread-avatar-clip"><circle cx="20" cy="20" r="20"/></clipPath>`;
    svg.appendChild(defs);
    const caption = ([x, y, text]) => svg.appendChild(svgEl("text", { x, y, "font-size": 11, fill: "#898781" }, text));
    const arrow = ([x1, y1, x2, y2]) => svg.appendChild(svgEl("line", { x1, y1, x2, y2, stroke: "#59647a", "stroke-width": 1.5,
      "marker-end": "url(#spread-arrow)" }));

    // 1. the text so far
    caption([...L.textCaption, "the text so far"]);
    const tb = L.textBox;
    svg.appendChild(svgEl("rect", { x: tb.x, y: tb.y, width: tb.w, height: tb.h, rx: 10, fill: "#0e1420", stroke: "#2f3a4e" }));
    this.prefix = svgEl("text", { x: L.prefix[0], y: L.prefix[1], "font-size": L.prefix[2], "font-family": MONO, fill: "#f0efec" });
    svg.appendChild(this.prefix);
    arrow(L.arrow1);

    // 2. the language model
    const m = L.model;
    this.modelBox = svgEl("rect", { x: m.x, y: m.y, width: m.w, height: m.h, rx: 14, fill: "#151c2b", stroke: "#3a4560", "stroke-width": 1.5 });
    svg.appendChild(this.modelBox);
    const face = svgEl("g", { transform: `translate(${m.face[0]} ${m.face[1]}) scale(${m.face[2]})`, "clip-path": "url(#spread-avatar-clip)" });
    face.innerHTML = avatarSvg(model).replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "");
    svg.appendChild(face);
    svg.appendChild(svgEl("text", { x: m.title[0], y: m.title[1], "font-size": m.title[2], "font-weight": 650, fill: "#f0efec" },
      persona(model).title.replace(/ Encoder$/, "")));
    svg.appendChild(svgEl("text", { x: m.sub[0], y: m.sub[1], "font-size": m.sub[2], fill: "#c3c2b7" }, "language model"));
    this.status = svgEl("text", { x: m.status[0], y: m.status[1], "font-size": m.status[2], fill: "#898781" }, "");
    svg.appendChild(this.status);
    arrow(L.arrow2);

    // 3. its probabilities
    caption([...L.barsCaption, "next-symbol probabilities"]);
    this.bars = svgEl("g");
    svg.appendChild(this.bars);

    // 4. the range
    caption(L.rangeCaption);
    const { x0, x1, y } = L.line;
    svg.appendChild(svgEl("line", { x1: x0, x2: x1, y1: y, y2: y, stroke: "#c3c2b7", "stroke-width": 1.5 }));
    for (const x of [x0, x1]) svg.appendChild(svgEl("line", { x1: x, x2: x, y1: y - 6, y2: y + 6, stroke: "#c3c2b7", "stroke-width": 1.5 }));
    this.lo = svgEl("text", { x: x0, y: y - 10, "font-size": 11, "font-family": MONO, fill: "#c3c2b7" });
    this.hi = svgEl("text", { x: x1, y: y - 10, "font-size": 11, "font-family": MONO, fill: "#c3c2b7", "text-anchor": "end" });
    svg.append(this.lo, this.hi);
    this.spreadArrow = svgEl("path", { d: L.spreadPath, fill: "none", stroke: "#59647a", "stroke-width": 1.5, "stroke-dasharray": "4 4",
      "marker-end": "url(#spread-arrow)", opacity: 0 });
    svg.appendChild(this.spreadArrow);
    this.segments = svgEl("g");
    svg.appendChild(this.segments);
    this.choice = svgEl("text", { x: L.choice[0], y: L.choice[1], "font-size": L.choice[2], fill: "#f0efec", "text-anchor": "middle" });
    this.bitsLine = svgEl("text", { x: L.bits[0], y: L.bits[1], "font-size": L.bits[2], "font-family": MONO, fill: "#4ade80",
      "text-anchor": "middle" });
    svg.append(this.choice, this.bitsLine);
  }

  _range(lo, hi) {
    this.lo.textContent = lo;
    this.hi.textContent = hi;
  }

  /**
   * Play the whole message. result: an /api/encode response; stale(): true once replaced;
   * onStep(i): called after symbol i is encoded (for the narration).
   */
  async play(model, result, stale, onStep = () => {}) {
    this.L = this.container.clientWidth < NARROW_BELOW ? LAYOUTS.narrow : LAYOUTS.wide;
    const { bars: B, line: LINE, seg: SEG } = this.L;
    this._scene(model);
    const chars = [...result.text];
    const trace = result.trace;
    this._range("0", "1");
    this.bitsLine.textContent = "bits sent so far: none yet";
    for (let i = 0; i < trace.length; i++) {
      const t = trace[i];
      const prev = trace[i - 1];
      if (stale()) return;
      this.bars.replaceChildren();
      this.segments.replaceChildren();
      this.bars.setAttribute("opacity", 1);
      this.choice.textContent = "";
      this.spreadArrow.setAttribute("opacity", 0);
      if (prev) this._range(formatDecimal(prev.l_dec_after, prev.dec_shared_after), formatDecimal(prev.h_dec_after, prev.dec_shared_after));

      // 1-2: the text so far goes in, the model thinks
      this.prefix.textContent = `${chars.slice(0, t.char_start).join("")}▍`;
      this.status.textContent = "reading the text…";
      await tween(500, (e) => this.modelBox.setAttribute("stroke", e < 0.5 ? VIOLET : "#3a4560"), stale);
      this.status.textContent = "its guesses →";

      // 3: its probabilities, the likeliest few as bars plus "everything else"
      const known = t.top_segments.filter((s) => s.char !== null);
      const top = [...known].sort((a, b) => b.prob - a.prob).slice(0, TOP_K);
      const rest = 1 - top.reduce((sum, s) => sum + s.prob, 0);
      const rows = [...top.map((s) => ({ seg: s, label: displaySymbol(s.char), p: s.prob })), { seg: null, label: "…", p: rest }];
      const barRects = rows.map((row, k) => {
        const y = B.y0 + k * B.dy;
        this.bars.appendChild(svgEl("text", { x: B.x - 14, y: y + 12, "font-size": B.label, "font-family": MONO, fill: "#f0efec",
          "text-anchor": "middle" }, row.label));
        const rect = svgEl("rect", { x: B.x, y: y + 2, width: 0, height: 13, rx: 3, fill: row.seg ? PINK : "#3a4152" });
        this.bars.appendChild(rect);
        this.bars.appendChild(svgEl("text", { x: B.x + B.w + 6, y: y + 12, "font-size": B.odds, fill: "#c3c2b7" },
          row.seg ? formatOdds(row.p) : "the rest"));
        return { rect, x: B.x, y: y + 2, w: Math.max(2, row.p * B.w), h: 13, selected: Boolean(row.seg?.is_selected) };
      });
      await tween(450, (e) => barRects.forEach((b) => b.rect.setAttribute("width", b.w * e)), stale);
      await sleep(250);
      if (stale()) return;

      // 4: spread: every slice flies from its bar to its place in the range (the rest come out of "…")
      this.spreadArrow.setAttribute("opacity", 1);
      const flying = t.top_segments.map((seg) => {
        const k = top.indexOf(seg);
        const from = barRects[k >= 0 ? k : barRects.length - 1];
        const x0 = this._lineX(seg.rel_start);
        const x1 = this._lineX(seg.rel_end);
        const isTop = k >= 0;
        const rect = svgEl("rect", { rx: 4, fill: isTop ? "rgba(213,81,129,0.16)" : "#1a2130",
          stroke: isTop ? "rgba(213,81,129,0.75)" : "#2c3546", "stroke-width": 1 });
        this.segments.appendChild(rect);
        return { seg, rect, from, to: { x: x0 + (x1 - x0 > 4 ? 1 : 0), y: SEG.y, w: Math.max(1, x1 - x0 - (x1 - x0 > 4 ? 2 : 0)), h: SEG.h } };
      });
      await tween(900, (e) => {
        for (const f of flying) {
          setAttrs(f.rect, { x: mix(f.from.x, f.to.x, e), y: mix(f.from.y, f.to.y, e), width: mix(f.from.w, f.to.w, e),
            height: mix(f.from.h, f.to.h, e) });
        }
        this.bars.setAttribute("opacity", 1 - 0.6 * e);
      }, stale);
      if (stale()) return;
      for (const f of flying) {  // the symbols' labels, where they fit
        const w = f.to.w;
        const label = f.seg.char === null ? "" : displaySymbol(f.seg.char);
        if (label && w > 9 * label.length + 4) {
          this.segments.appendChild(svgEl("text", { x: f.to.x + w / 2, y: SEG.y + SEG.h / 2 + 5, "font-size": 13, "font-family": MONO,
            "text-anchor": "middle", fill: "#f2b8cf" }, label));
        }
      }
      await sleep(350);
      if (stale()) return;

      // 5: the real next symbol's slice is chosen...
      const chosen = flying.find((f) => f.seg.is_selected);
      setAttrs(chosen.rect, { fill: VIOLET, stroke: "#c9c2ff", "stroke-width": 1.5 });
      barRects.find((b) => b.selected)?.rect.setAttribute("fill", VIOLET);
      this.bars.setAttribute("opacity", 1);
      this.segments.querySelectorAll("text").forEach((el) => {
        const x = Number(el.getAttribute("x"));
        if (x >= chosen.to.x && x <= chosen.to.x + chosen.to.w) el.setAttribute("fill", "#ffffff");
      });
      this.choice.textContent = `'${displaySymbol(t.symbol)}' had ${formatOdds(t.prob)} → costs ${formatCost(t.prob)}`;
      await sleep(700);
      if (stale()) return;

      // 6: ...and becomes the new range
      this.segments.querySelectorAll("text").forEach((el) => el.remove());
      const c = chosen.to;
      await tween(700, (e) => {
        setAttrs(chosen.rect, { x: mix(c.x, LINE.x0, e), width: mix(c.w, LINE.x1 - LINE.x0, e) });
        for (const f of flying) if (f !== chosen) f.rect.setAttribute("opacity", 1 - e);
      }, stale);
      if (stale()) return;
      this._range(formatDecimal(t.l_dec_after, t.dec_shared_after), formatDecimal(t.h_dec_after, t.dec_shared_after));
      this.bitsLine.textContent = t.running_bits
        ? `bits sent so far: 0.${t.running_bits}  (+${t.bits_added})` : "bits sent so far: none yet";
      onStep(i);
      await sleep(600);
    }
    if (stale()) return;
    this.prefix.textContent = result.text;
    this.status.textContent = "done";
    this.bars.replaceChildren();
    this.segments.replaceChildren();
    this.spreadArrow.setAttribute("opacity", 0);
    this.choice.textContent = `the whole message: ${result.stats.payload_bits} bits instead of ${result.stats.utf8_bits}`;
  }
}
