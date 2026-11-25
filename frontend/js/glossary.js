// Hover (or focus) definitions for the showcase's words. Mark a word with
//   <span class="term" data-term="symbol">symbol</span>
// anywhere, including HTML added later: one delegated listener shows the popover.

export const TERMS = {
  character: ["character", "One letter, digit, space or sign as you read it. 'é' and '👋' are one character each."],
  byte: ["byte", "How plain text is stored (UTF-8): 1 byte for an English letter, 2 for é or a Hebrew letter, 4 for an emoji. Each byte is 8 bits."],
  symbol: ["symbol", "What the model predicts, one at a time: a character, a byte, a whole word or a GPT-2 token, depending on the encoder."],
  bit: ["bit", "One binary digit of the output. Each bit halves the range of numbers still possible, so a symbol with a 1-in-N chance costs about log₂ N bits."],
  bpc: ["bits per character", "Bits sent ÷ characters of the text. It's the fair way to compare encoders that cut text differently. Plain text is 8."],
  cost: ["cost", "−log₂ P: the bits a symbol with probability P adds. 1 in 2 costs 1 bit, 1 in 256 costs 8, a sure thing costs almost nothing."],
  interval: ["interval", "The range of numbers still possible. It starts as [0, 1) and shrinks to the chosen symbol's slice at every step."],
  "best-binary": ["shortest binary fraction", "The shortest binary number inside the current interval, like 0.1011. Its digits are the bits sent so far."],
  "bits-sent": ["bits sent", "The digits of the final binary fraction: what actually travels. About the sum of all the symbols' costs, rounded up."],
  probability: ["probability", "How likely the model thinks a symbol is next. Its box on the line is exactly that wide."],
  encoder: ["encoder", "A language model plus a way of cutting text into symbols. The arithmetic coder is the same for all of them."],
};

let popover = null;
let shownBy = null;  // the click that opened the popover (so the same click doesn't close it again)

/** Put the popover with html next to the rectangle r (viewport coordinates). */
function place(html, r) {
  popover ??= Object.assign(document.createElement("div"), { className: "term-popover", role: "tooltip" });
  popover.innerHTML = html;
  document.body.appendChild(popover);
  const p = popover.getBoundingClientRect();
  const left = Math.max(8, Math.min(r.left + r.width / 2 - p.width / 2, window.innerWidth - p.width - 8));
  const top = r.bottom + 8 + p.height > window.innerHeight ? r.top - p.height - 8 : r.bottom + 8;
  popover.style.left = `${left + window.scrollX}px`;
  popover.style.top = `${top + window.scrollY}px`;
}

function show(el) {
  const entry = TERMS[el.dataset.term];
  if (entry) place(`<b>${entry[0]}</b><br>${entry[1]}`, el.getBoundingClientRect());
}

function hide() { popover?.remove(); }

/** A popover at the point of a click or tap: for things phones can't hover (it closes on the next tap). */
export function showTipAt(html, event) {
  shownBy = event;
  place(html, { left: event.clientX, right: event.clientX, top: event.clientY - 6, bottom: event.clientY + 6, width: 0, height: 12 });
}

/** Make every .term (now and later) show its definition on hover and keyboard focus. */
export function initGlossary() {
  const termOf = (e) => e.target.closest?.(".term[data-term]");
  document.addEventListener("mouseover", (e) => { const el = termOf(e); if (el) show(el); });
  document.addEventListener("mouseout", (e) => { if (termOf(e)) hide(); });
  document.addEventListener("focusin", (e) => { const el = termOf(e); if (el) show(el); });
  document.addEventListener("focusout", (e) => { if (termOf(e)) hide(); });
  // phones: a tap opens a definition, a tap anywhere else closes it
  document.addEventListener("click", (e) => {
    if (e === shownBy) return;
    const el = termOf(e);
    if (el) show(el); else hide();
  });
  new MutationObserver(() => document.querySelectorAll(".term:not([tabindex])").forEach((el) => el.setAttribute("tabindex", "0")))
    .observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll(".term").forEach((el) => el.setAttribute("tabindex", "0"));
}

/** HTML for a defined word: term("symbol", "symbols"). */
export const term = (key, text = TERMS[key]?.[0] ?? key) => `<span class="term" data-term="${key}">${text}</span>`;
