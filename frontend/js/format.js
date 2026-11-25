// Shared display helpers: how characters are shown and how "cost" (surprise) maps to colour.

/** Visible glyph for a character: space and newline get symbols. */
export function displayChar(c) {
  if (c === " ") return "␣"; // open box
  if (c === "\n") return "↵"; // return arrow
  return c;
}

/** Visible label for a symbol (one char, a word like " the", or a raw byte like "\xd7"). */
export function displaySymbol(s) {
  if (s === null || s === undefined) return "";
  if (s.length <= 1) return displayChar(s);
  return s.replace(/\n/g, "↵").replace(/^ /, "␣");
}

/** Bits a character costs at probability p: -log2(p). */
export const costBits = (p) => -Math.log2(p);

/** Colour by cost: cheap (likely) -> emerald/cyan, expensive (surprising) -> amber/rose. */
export function costColor(p) {
  const bits = costBits(p);
  if (bits < 1) return "#10b981";
  if (bits < 2.5) return "#06b6d4";
  if (bits < 4.5) return "#f59e0b";
  return "#f43f5e";
}

/** Text colour that stays readable on costColor(p). */
export function inkOn(p) {
  return costBits(p) < 4.5 ? "#04121c" : "#fff1f2";
}

/** Shorten a long bit string to head ... tail. */
export function shortBits(bits, head = 6, tail = 14) {
  return bits.length <= head + tail + 1 ? bits : `${bits.slice(0, head)}…${bits.slice(-tail)}`;
}

export const escapeHtml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
