// Per-character view of an encoding, so encoders that cut text differently can be compared.
//
// A symbol costs -log2(P) bits. A symbol that spans several characters (a word, a GPT-2 token)
// spreads its cost evenly over them; several symbols on one character (the bytes of "é" or of an
// emoji) add up. Positions are code points, like the trace's char_start / char_end.

import { costBits } from "./format.js";

/**
 * The trace as bars over the text: one per symbol, spanning its characters. Symbols that share
 * characters (the bytes of "é", a GPT-2 token ending mid-emoji) merge into one bar.
 * @returns {{ start: number, end: number, cost: number, perChar: number, steps: number[] }[]}
 */
export function symbolGroups(text, trace) {
  const n = [...text].length;
  const groups = [];
  trace.forEach((t, i) => {
    const start = Math.min(t.char_start, n);
    const end = Math.min(Math.max(t.char_end, start + 1), n);
    if (start >= n) return;
    const last = groups[groups.length - 1];
    if (last && start < last.end) {
      last.end = Math.max(last.end, end);
      last.cost += costBits(t.prob);
      last.steps.push(i);
    } else {
      groups.push({ start, end, cost: costBits(t.prob), steps: [i] });
    }
  });
  for (const g of groups) g.perChar = g.cost / (g.end - g.start);
  return groups;
}

/**
 * @returns {{ chars: string[], perChar: number[], cumulative: number[], stepsAt: number[],
 *             covering: number[][], utf8Cumulative: number[] }}
 *   perChar[c]      bits charged to character c
 *   cumulative[c]   bits for the first c characters (cumulative[0] = 0)
 *   stepsAt[c]      symbols fully encoded once the first c characters are (char_end <= c)
 *   covering[c]     trace indices of the symbols covering character c
 *   utf8Cumulative  the same text as plain UTF-8 (8 bits per byte)
 */
export function charCosts(text, trace) {
  const chars = [...text];
  const n = chars.length;
  const perChar = new Array(n).fill(0);
  const covering = Array.from({ length: n }, () => []);
  trace.forEach((t, i) => {
    const start = Math.min(t.char_start, n);
    const end = Math.min(Math.max(t.char_end, start + 1), n);
    if (start >= n) return;  // an empty symbol at the very end (nothing to charge)
    const share = costBits(t.prob) / (end - start);
    for (let c = start; c < end; c++) {
      perChar[c] += share;
      covering[c].push(i);
    }
  });
  const cumulative = [0];
  const utf8Cumulative = [0];
  const encoder = new TextEncoder();
  chars.forEach((ch, c) => {
    cumulative.push(cumulative[c] + perChar[c]);
    utf8Cumulative.push(utf8Cumulative[c] + 8 * encoder.encode(ch).length);
  });
  // char_end never decreases along the trace, so "symbols done by character c" is a running count
  const stepsAt = [];
  let done = 0;
  for (let c = 0; c <= n; c++) {
    while (done < trace.length && trace[done].char_end <= c) done++;
    stepsAt.push(c === n ? trace.length : done);
  }
  return { chars, perChar, cumulative, stepsAt, covering, utf8Cumulative };
}
