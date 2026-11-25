// Shared display helpers.

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

/** Bits a symbol costs at probability p: -log2(p). */
export const costBits = (p) => -Math.log2(p);

/** A probability the way people say it: "1 in 17", or "95%" when it's likely. */
export function formatOdds(p) {
  if (p >= 0.5) return `${Math.min(99.9, p * 100).toFixed(p > 0.99 ? 1 : 0)}%`;
  const n = 1 / p;
  return `1 in ${n < 10 ? n.toFixed(1).replace(/\.0$/, "") : Math.round(n).toLocaleString("en-US")}`;
}

/** "4.1 bits", "0.07 bits", "13 bits": the cost of a symbol with probability p. */
export function formatCost(p) {
  const bits = costBits(p);
  return `${bits < 1 ? bits.toFixed(2) : bits < 10 ? bits.toFixed(1) : Math.round(bits)} bits`;
}

const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";

/** 12 -> "¹²" */
export const sup = (n) => String(n).split("").map((d) => SUPERSCRIPT[d]).join("");

/** The best binary fraction for display: "3/2²" for short ones, "23-bit fraction" for long ones. */
export function fractionLabel(bits) {
  if (!bits) return "0";
  if (bits.length > 12) return `${bits.length}-bit fraction`;
  return `${BigInt("0b" + bits)}/2${sup(bits.length)}`;
}

/**
 * Shorten a long decimal label ("0.77352819...") around the digits that matter: the ones after
 * the prefix it shares with the other end of the window. `shared` = digits shared after "0.".
 */
export function formatDecimal(label, shared) {
  if (!label.startsWith("0.") || label.length <= 9) return label;
  const digits = label.slice(2);
  if (shared <= 3) return label.slice(0, 9);
  return `0.${digits.slice(0, 2)}…${digits.slice(shared - 1, shared + 2)}`;
}

/** Rough width of text in px (good enough to keep SVG labels from colliding). */
export const textWidth = (text, size = 11, mono = true) => text.length * size * (mono ? 0.62 : 0.56);

export const escapeHtml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Create an SVG element with attributes. */
export function svgEl(tag, attrs = {}, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}
