// Interval-zoom animation engine.
//
// For each encoding step the bar shows the current window [l, h) split into the model's
// probabilities (in the coder's real slot order). The chosen character's slot then stretches
// to the full width: that slot *is* the next window. Positions come straight from the trace
// (exact cdf / total), so the picture is the encoder's real arithmetic.

import { costColor, displayChar, inkOn, shortBits } from "./format.js";

const HOLD_SHARE = 0.35;   // part of a step spent showing the split before zooming
const BASE_STEP_MS = 1100; // one step at 1x speed
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export class ZoomCanvas {
  constructor(canvas, { onStep } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onStep = onStep ?? (() => {});
    this.trace = [];
    this.index = 0;
    this.playing = false;
    this.speed = 1;
    this.anim = null; // { kind: "step", start, index } while animating
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  /** Show a new message's trace, starting at its first character. */
  setTrace(trace) {
    this.trace = trace;
    this.index = 0;
    this.anim = null;
    this.playing = false;
    this.onStep(0);
    this.draw();
  }

  get length() { return this.trace.length; }
  get finished() { return this.index >= this.length; } // index == length: the final window

  play() {
    if (!this.length) return;
    if (this.finished) this.seek(0);
    this.playing = true;
    this._startStep();
  }

  pause() { this.playing = false; }

  setSpeed(speed) { this.speed = speed; }

  /** Jump to a step (shown before its zoom). */
  seek(index) {
    this.playing = false;
    this.anim = null;
    this.index = Math.max(0, Math.min(index, this.length));
    this.onStep(Math.min(this.index, this.length - 1));
    this.draw();
  }

  stepBack() { this.seek(this.index - 1); }

  /** Animate the current step's zoom once, then stop on the next step. */
  stepForward() {
    if (this.finished) return;
    this.playing = false;
    if (this.anim) { this._finishStep(); return; }
    this._startStep();
  }

  _startStep() {
    if (this.finished) { this.playing = false; return; }
    this.anim = { start: performance.now(), index: this.index };
    requestAnimationFrame((now) => this._tick(now));
  }

  _tick(now) {
    if (!this.anim) return;
    const t = (now - this.anim.start) / (BASE_STEP_MS / this.speed);
    if (t >= 1) { this._finishStep(); return; }
    this.draw(t);
    requestAnimationFrame((n) => this._tick(n));
  }

  _finishStep() {
    this.anim = null;
    this.index += 1;
    if (!this.finished) this.onStep(this.index);
    this.draw();
    if (this.playing) this._startStep();
  }

  // ---- drawing -------------------------------------------------------------------------

  /** Draw the current step; t in [0, 1) is the animation progress (undefined = static). */
  draw(t) {
    const { canvas, ctx } = this;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== Math.round(width * dpr)) canvas.width = Math.round(width * dpr);
    if (canvas.height !== Math.round(height * dpr)) canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // the bar grows with the canvas (up to a cap); the drawing is centred vertically in the space.
    // 72px = header line above the bar + two axis lines below it
    const barHeight = Math.max(44, Math.min(130, height - 72));
    ctx.translate(0, Math.max(0, (height - barHeight - 72) / 2));
    const bar = { x: 8, y: 28, w: width - 16, h: barHeight };
    if (!this.length) {
      this._emptyBar(bar, "the interval [0, 1) - every possible message starts here");
      return;
    }
    if (this.finished) {
      this._finalState(bar);
      return;
    }

    const step = this.trace[this.index];
    let view = [0, 1]; // part of the current window that is visible (zooms toward the chosen slot)
    let fade = 1;
    if (t !== undefined) {
      if (t < HOLD_SHARE) {
        fade = Math.min(1, t / (HOLD_SHARE * 0.5)); // new split fades in
      } else {
        const e = easeInOutCubic((t - HOLD_SHARE) / (1 - HOLD_SHARE));
        view = [step.sub_l_rel * e, 1 + (step.sub_h_rel - 1) * e];
      }
    }
    this._segments(bar, step, view, fade, t);
    this._axis(bar, this.index, t !== undefined && t > 0.92);
    this._header(width, step);
  }

  _emptyBar(bar, caption) {
    const { ctx } = this;
    ctx.fillStyle = "#1e293b";
    roundRect(ctx, bar.x, bar.y, bar.w, bar.h, 6);
    ctx.fill();
    ctx.fillStyle = "#64748b";
    ctx.font = "12px ui-sans-serif, system-ui";
    ctx.textAlign = "center";
    ctx.fillText(fitText(ctx, caption, bar.w - 16), bar.x + bar.w / 2, bar.y + bar.h / 2 + 4);
    ctx.textAlign = "left";
    ctx.fillText("0", bar.x, bar.y + bar.h + 18);
    ctx.textAlign = "right";
    ctx.fillText("1", bar.x + bar.w, bar.y + bar.h + 18);
  }

  _segments(bar, step, [a, b], fade, t) {
    const { ctx } = this;
    const X = (rel) => bar.x + ((rel - a) / (b - a)) * bar.w;
    ctx.save();
    ctx.beginPath();
    ctx.rect(bar.x, bar.y - 4, bar.w, bar.h + 8);
    ctx.clip();
    ctx.globalAlpha = fade;
    for (const seg of step.top_segments) {
      const x0 = X(seg.rel_start);
      const x1 = X(seg.rel_end);
      if (x1 < bar.x || x0 > bar.x + bar.w) continue;
      const w = Math.max(0.5, x1 - x0 - 2); // 2px surface gap between fills
      ctx.fillStyle = seg.char === null ? "#334155" : costColor(seg.prob);
      roundRect(ctx, x0 + 1, bar.y, w, bar.h, 4);
      ctx.fill();
      if (seg.is_selected) {
        const pulse = t === undefined ? 1 : 0.6 + 0.4 * Math.sin(t * Math.PI * 4) ** 2;
        ctx.save();
        ctx.shadowColor = "#a5f3fc";
        ctx.shadowBlur = 14 * pulse;
        ctx.strokeStyle = "#ecfeff";
        ctx.lineWidth = 2;
        roundRect(ctx, x0 + 1, bar.y, w, bar.h, 4);
        ctx.stroke();
        ctx.restore();
      }
      this._segmentLabel(seg, x0 + 1, w, bar);
    }
    ctx.restore();
  }

  _segmentLabel(seg, x, w, bar) {
    const { ctx } = this;
    const words = { " ": "space", "\n": "newline" };
    const label = seg.char === null ? (w > 34 ? `+${seg.count}` : "")
      : (words[seg.char] && w > 70 ? words[seg.char] : displayChar(seg.char));
    if (!label || w < 13) return;
    ctx.fillStyle = seg.char === null ? "#94a3b8" : inkOn(seg.prob);
    ctx.font = `${seg.is_selected ? "bold " : ""}14px ui-monospace, Consolas, monospace`;
    ctx.textAlign = "center";
    ctx.fillText(label, x + w / 2, bar.y + bar.h / 2 + 2);
    if (seg.char !== null && w > 44) {
      ctx.font = "10px ui-sans-serif, system-ui";
      ctx.fillText(`${(seg.prob * 100).toFixed(seg.prob < 0.1 ? 1 : 0)}%`, x + w / 2, bar.y + bar.h / 2 + 18);
    }
  }

  /** Window bounds under the bar, in binary: before the zoom of step i, or after it. */
  _axis(bar, i, after) {
    const { ctx } = this;
    const source = after ? this.trace[i] : this.trace[i - 1];
    const half = bar.w / 2 - 6; // each label gets half the bar, so they never meet
    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.fillStyle = "#94a3b8";
    ctx.textAlign = "left";
    ctx.fillText(source ? fitBits(ctx, "l = 0.", source.l_bits_after, half) : "l = 0", bar.x, bar.y + bar.h + 16);
    ctx.textAlign = "right";
    const h = !source ? "h = 1" : source.h_bits_after === "1" ? "h = 1" : fitBits(ctx, "h = 0.", source.h_bits_after, half);
    ctx.fillText(h, bar.x + bar.w, bar.y + bar.h + 16);
    ctx.textAlign = "center";
    ctx.fillStyle = "#64748b";
    const width = source ? `width 2^${source.log2_width_after.toFixed(1)}` : "width 1";
    ctx.fillText(fitText(ctx, width, bar.w), bar.x + bar.w / 2, bar.y + bar.h + 32);
  }

  _header(width, step) {
    const { ctx } = this;
    ctx.font = "12px ui-sans-serif, system-ui";
    ctx.textAlign = "left";
    ctx.fillStyle = "#cbd5e1";
    const left = fitText(ctx, `step ${step.step_index + 1}/${this.length}: encode '${displayChar(step.char)}'`, (width - 16) * 0.55);
    ctx.fillText(left, 8, 16);
    // right side: full sentence if it fits next to the left text, else just the probability
    const room = width - 16 - ctx.measureText(left).width - 16;
    const full = `P = ${(step.prob * 100).toFixed(2)}%  ->  ${(-Math.log2(step.prob)).toFixed(2)} bits of surprise`;
    const short = `P = ${(step.prob * 100).toFixed(2)}%`;
    ctx.textAlign = "right";
    ctx.fillStyle = "#94a3b8";
    ctx.fillText(fitText(ctx, ctx.measureText(full).width <= room ? full : short, room), width - 8, 16);
  }

  _finalState(bar) {
    const { ctx } = this;
    const last = this.trace[this.length - 1];
    ctx.fillStyle = "#0e7490";
    roundRect(ctx, bar.x, bar.y, bar.w, bar.h, 6);
    ctx.fill();
    ctx.fillStyle = "#ecfeff";
    ctx.font = "13px ui-sans-serif, system-ui";
    ctx.textAlign = "center";
    const k = last.running_bits.length;
    const title = `final interval - the shortest binary fraction inside it has ${k} bits`;
    ctx.fillText(fitText(ctx, ctx.measureText(title).width <= bar.w - 16 ? title : `final interval: ${k} bits`, bar.w - 16),
      bar.x + bar.w / 2, bar.y + bar.h / 2 - 4);
    ctx.font = "12px ui-monospace, Consolas, monospace";
    ctx.fillText(fitBits(ctx, "r = 0.", last.running_bits, bar.w - 16), bar.x + bar.w / 2, bar.y + bar.h / 2 + 16);
    this._axis(bar, this.length - 1, true);
    ctx.font = "12px ui-sans-serif, system-ui";
    ctx.textAlign = "left";
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(fitText(ctx, `done: ${this.length} characters encoded`, bar.w), 8, 16);
  }
}

/** Truncate text with an ellipsis so it fits maxWidth (in the current ctx font). */
function fitText(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (ctx.measureText(text.slice(0, mid) + "…").width <= maxWidth) lo = mid;
    else hi = mid - 1;
  }
  return lo ? text.slice(0, lo) + "…" : "";
}

/** label + bits, shortened to head...tail until it fits maxWidth (the tail is where l and h differ). */
function fitBits(ctx, label, bits, maxWidth) {
  for (let tail = 16; tail >= 4; tail -= 2) {
    const text = label + shortBits(bits, 4, tail);
    if (ctx.measureText(text).width <= maxWidth) return text;
  }
  return fitText(ctx, label + shortBits(bits, 1, 3), maxWidth);
}

function roundRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, radius);
}
