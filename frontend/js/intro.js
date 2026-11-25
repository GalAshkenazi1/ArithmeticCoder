// Start page: characters, symbols and bits, in five animated steps with live examples.
// Every stage plays when it scrolls into view and can be replayed; the numbers come from the real
// encoders (the API), so they match what the other pages show.

import * as api from "./api.js";
import { FAMILIES, avatarSvg, persona, sortModels } from "./encoders.js";
import { displayChar, displaySymbol, escapeHtml, formatCost, formatOdds } from "./format.js";
import { initGlossary } from "./glossary.js";
import { SpreadAnimation } from "./llm-spread.js";

const HAMLET = "To be, or not to be, that is the question:";
const CHAR_EXAMPLES = ["Unbelievably lovely!", "the weather", "café", "Grüße 👋"];  // one text for bytes and symbols
const CUTS = [["char", "wiki_small", "Characters"], ["bytes", "web_bytes", "Bytes"], ["words", "web_words", "Words"],
  ["gpt2", "gpt2", "GPT-2 tokens"]];
const GUESS_TEXT = "To be, or not to be";  // the last symbol is the guessed one
const GUESSERS = ["shakespeare_char", "python_small", "web_bytes"];
const FAIR = ["shakespeare_char", "web_bytes", "web_words", "gpt2", "uniform_bytes"];
const ODDS_PRESETS = [["a sure guess (9 in 10)", 0.9], ["a coin flip (1 in 2)", 0.5], ["a random byte (1 in 256)", 1 / 256],
  ["a surprise (1 in 10,000)", 1e-4]];

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chipLabel = (label) => label.replace(/ /g, "␣").replace(/\n/g, "↵") || "∅";
const state = { models: [], cut: { text: CHAR_EXAMPLES[0], index: 0, auto: null } };
const byId = (id) => state.models.find((m) => m.id === id && m.available);
const canEncode = (model, text) => !model.vocab || [...text].every((c) => model.vocab.includes(c));

// the same request is made once per page (several chapters share results)
const cache = new Map();
const cached = (key, make) => {
  if (!cache.has(key)) cache.set(key, make().catch((e) => { cache.delete(key); throw e; }));
  return cache.get(key);
};
const encode = (modelId, text) => cached(`e:${modelId}:${text}`, () => api.encode(modelId, text));
const tokenize = (modelId, text) => cached(`t:${modelId}:${text}`, () => api.tokenize(modelId, text));

/** A named animation: calling it again restarts it; stale() tells an old run to stop. */
const players = {};
function player(name, body) {
  let token = 0;
  const play = () => { const mine = ++token; return body(() => mine !== token); };
  players[name] = play;
  return play;
}
document.querySelectorAll("[data-replay]").forEach((b) => b.addEventListener("click", () => players[b.dataset.replay]?.()));

/** Run fn once, when el first scrolls into view. */
function onView(el, fn, threshold = 0.3) {
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { io.disconnect(); fn(); }
  }, { threshold });
  io.observe(el);
}

/** Restart a CSS animation on el (by removing and re-adding the "play" class). */
function restartCss(el) {
  el.classList.remove("play");
  void el.offsetWidth;  // reflow, so the animation starts again
  el.classList.add("play");
}

function chips(container, items, buttonFor) {
  container.innerHTML = "";
  for (const item of items) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = typeof item === "string" ? item : item[0];
    b.addEventListener("click", () => {
      container.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      buttonFor(item);
    });
    container.appendChild(b);
  }
  container.querySelector("button")?.classList.add("active");
}

// ---- hero: plain text against an encoder ---------------------------------------------------------

const playHero = player("hero", async (stale) => {
  const chars = [...HAMLET];
  const plainTotal = 8 * new TextEncoder().encode(HAMLET).length;
  let r;
  try { r = await encode("shakespeare_char", HAMLET); } catch (e) { $("race-result").textContent = `could not reach the API: ${e.message}`; return; }
  for (let i = 0; i <= chars.length; i++) {
    if (stale()) return;
    const plain = 8 * new TextEncoder().encode(chars.slice(0, i).join("")).length;
    const bits = i ? r.trace[i - 1].running_bits : "";
    $("hero-typed").innerHTML = `${escapeHtml(chars.slice(0, i).join(""))}<span class="caret">▍</span>`;
    $("race-plain").style.width = `${(100 * plain) / plainTotal}%`;
    $("race-enc").style.width = `${(100 * bits.length) / plainTotal}%`;
    $("race-plain-v").textContent = `${plain} bits`;
    $("race-enc-v").textContent = `${bits.length} bits`;
    $("race-bits").textContent = bits ? `0.${bits}` : "";
    $("race-result").textContent = "";
    await sleep(75);
  }
  $("race-result").innerHTML = `${plainTotal} bits → <b>${r.stats.payload_bits} bits</b>: <b>${r.stats.ratio.toFixed(1)}× smaller</b>.`;
});

// ---- 1. characters and bytes ----------------------------------------------------------------------

function renderChars(text) {
  const enc = new TextEncoder();
  const chars = [...text];
  let byteIndex = 0;
  const charGap = 0.1;
  const bytesStart = chars.length * charGap + 0.3;
  $("char-tiles").innerHTML = chars.map((ch, i) => {
    const bytes = [...enc.encode(ch)];
    return `<div class="ct" style="animation-delay:${(i * charGap).toFixed(2)}s">
        <div class="ct-char">${escapeHtml(displayChar(ch))}</div>
        <div class="ct-bytes">${bytes.map((b) => {
          const d = bytesStart + 0.07 * byteIndex++;
          return `<span class="ct-byte" style="animation-delay:${d.toFixed(2)}s"><span class="hex">${b.toString(16).padStart(2, "0")}</span>` +
            `<span class="bin" style="animation-delay:${(d + 0.6).toFixed(2)}s">${b.toString(2).padStart(8, "0")}</span></span>`;
        }).join("")}</div>
      </div>`;
  }).join("");
  const nBytes = enc.encode(text).length;
  $("chars-counter").style.animationDelay = `${(bytesStart + 0.07 * nBytes + 0.8).toFixed(2)}s`;
  $("chars-counter").innerHTML = `${chars.length} character${chars.length === 1 ? "" : "s"} → ${nBytes} byte${nBytes === 1 ? "" : "s"} → ` +
    `<b>${nBytes * 8} bits</b> of plain text`;
  restartCss($("stage-chars"));
  state.cut.text = text;  // the same text, cut into symbols below
  if (state.models.length) showCut(state.cut.index);
}
players.chars = () => renderChars($("chars-input").value || CHAR_EXAMPLES[0]);
chips($("chars-examples"), CHAR_EXAMPLES, (text) => { $("chars-input").value = text; renderChars(text); });
$("chars-input").value = CHAR_EXAMPLES[0];
$("chars-input").addEventListener("input", () => {
  $("chars-examples").querySelectorAll("button").forEach((b) => b.classList.remove("active"));
  if ($("chars-input").value) renderChars($("chars-input").value);
});

// ---- 2. symbols: the same text, cut four ways ----------------------------------------------------------

async function showCut(index, { user = false } = {}) {
  const cut = state.cut;
  if (user && cut.auto) { clearInterval(cut.auto); cut.auto = null; }
  cut.index = index;
  const [, modelId] = CUTS[index];
  const model = byId(modelId);
  $("cut-tabs").querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-selected", String(i === index)));
  const text = cut.text;
  const nChars = [...text].length;
  if (!model) { $("cut-text").innerHTML = '<span class="muted">this encoder isn\'t installed</span>'; return; }
  if (!canEncode(model, text)) {
    const bad = new Set([...text].filter((c) => !model.vocab.includes(c)));
    $("cut-text").innerHTML = [...text].map((c, i) => `<span class="chip ${bad.has(c) ? "bad" : i % 2 ? "b" : "a"}" style="animation-delay:${i * 18}ms">` +
      `${escapeHtml(chipLabel(c))}</span>`).join("");
    $("cut-counter").innerHTML = `<span class="bad-text">Can't: ${[...bad].map((c) => `'${escapeHtml(c)}'`).join(" ")} ` +
      `${bad.size === 1 ? "isn't" : "aren't"} in its alphabet.</span>`;
    restartCss($("cut-text"));
    return;
  }
  try {
    const data = await tokenize(model.id, text);
    if (cut.index !== index || cut.text !== text) return;
    const n = data.symbols.length;
    $("cut-text").innerHTML = data.symbols.map((s, i) => `<span class="chip ${i % 2 ? "b" : "a"}${s.label.startsWith("\\x") ? " raw" : ""}" ` +
      `style="animation-delay:${i * 25}ms" title="symbol ${s.id}">${escapeHtml(chipLabel(s.label))}</span>`).join("");
    $("cut-counter").innerHTML = `${nChars} characters → <b>${n} symbol${n === 1 ? "" : "s"}</b>`;
    restartCss($("cut-text"));
  } catch (e) {
    $("cut-counter").textContent = e.message;
  }
}

function startCutCycle() {
  const cut = state.cut;
  if (cut.auto) return;
  showCut(cut.index);
  cut.auto = setInterval(() => showCut((cut.index + 1) % CUTS.length), 3000);
}

// ---- 3. bits: halving, and the price of a 1-in-N guess ---------------------------------------------

const playHalving = player("bits", async (stale) => {
  const target = 0.7;
  let lo = 0, hi = 1, bits = "";
  $("halving").innerHTML = "";
  $("halving-out").innerHTML = `Finding <b>0.7</b>: left half (0) or right half (1)?`;
  for (let k = 1; k <= 4; k++) {
    await sleep(k === 1 ? 500 : 900);
    if (stale()) return;
    const mid = (lo + hi) / 2;
    const bit = target >= mid ? "1" : "0";
    const row = document.createElement("div");
    row.className = "hv-row";
    const span = hi - lo;
    row.innerHTML = `<span class="hv-range">[${+lo.toFixed(4)}, ${+hi.toFixed(4)})</span>
      <div class="hv-bar"><div class="hv-half" data-bit="0">0</div><div class="hv-half" data-bit="1">1</div>
        <span class="hv-dot" style="left:${(100 * (target - lo)) / span}%"></span></div>
      <span class="hv-bit">bit ${k}: <b>${bit}</b></span>`;
    $("halving").appendChild(row);
    await sleep(350);
    if (stale()) return;
    row.querySelector(`.hv-half[data-bit="${bit}"]`).classList.add("on");
    bits += bit;
    [lo, hi] = bit === "1" ? [mid, hi] : [lo, mid];
    $("halving-out").innerHTML = `<code>0.${bits}</code>: ${k} bit${k === 1 ? "" : "s"} → 1/${2 ** k} of the line.`;
  }
});

function setOdds(p) {
  $("odds-label").textContent = formatOdds(p);
  $("odds-slice").style.width = `max(2px, ${100 * p}%)`;
  const bits = -Math.log2(p);
  $("odds-cost").textContent = formatCost(p);
  const full = Math.floor(bits);
  const cells = Math.min(16, Math.ceil(bits));
  $("odds-cells").innerHTML = Array.from({ length: cells }, (_, i) =>
    `<i style="--fill:${i < full ? 1 : bits - full}"></i>`).join("") + (bits > 16 ? " …" : "");
}
const sliderToP = (v) => Math.min(0.95, 10 ** (-v / 100));
$("odds-slider").addEventListener("input", () => setOdds(sliderToP(Number($("odds-slider").value))));
chips($("odds-presets"), ODDS_PRESETS, ([, p]) => { $("odds-slider").value = String(Math.round(-100 * Math.log10(p))); setOdds(p); });
$("odds-presets").querySelectorAll("button").forEach((b) => b.classList.remove("active"));
setOdds(sliderToP(Number($("odds-slider").value)));

// ---- 4. guessing: a real model's guesses for the next letter ---------------------------------------

async function showGuess(modelId) {
  const model = byId(modelId);
  if (!model) return;
  $("guess-who").querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === modelId)));
  $("guess-typed").innerHTML = `${escapeHtml(GUESS_TEXT.slice(0, -1))}<span class="caret">▍</span>`;
  $("guess-bars").innerHTML = '<span class="muted">asking the model…</span>';
  try {
    const r = await encode(modelId, GUESS_TEXT);
    const step = r.trace[r.trace.length - 1];
    const known = step.top_segments.filter((s) => s.char !== null).sort((a, b) => b.prob - a.prob).slice(0, 8);
    const rest = 1 - known.reduce((sum, s) => sum + s.prob, 0);
    const actual = step.top_segments.find((s) => s.is_selected);
    $("guess-bars").innerHTML = known.map((s) => `<button type="button" class="gb${s.is_selected ? " actual" : ""}" data-p="${s.prob}"
        data-c="${escapeHtml(s.char)}"><span class="gb-sym">${escapeHtml(displaySymbol(s.char))}</span>
        <span class="gb-track"><span class="gb-fill" style="--w:${Math.max(0.4, 100 * s.prob)}%"></span></span>
        <span class="gb-val">${escapeHtml(formatOdds(s.prob))} → ${formatCost(s.prob)}</span></button>`).join("") +
      `<div class="gb rest"><span class="gb-sym">…</span><span class="gb-track"><span class="gb-fill" style="--w:${Math.max(0.4, 100 * rest)}%"></span></span>
        <span class="gb-val">${(100 * rest).toFixed(1)}% for everything else</span></div>`;
    restartCss($("guess-bars"));
    const note = (s) => (s.is_selected
      ? `The real next letter, '${escapeHtml(displaySymbol(s.char))}': ${escapeHtml(formatOdds(s.prob))} → <b>${formatCost(s.prob)}</b>.`
      : `'${escapeHtml(displaySymbol(s.char))}' instead: ${escapeHtml(formatOdds(s.prob))} → <b>${formatCost(s.prob)}</b>.`);
    $("guess-note").innerHTML = note(actual);
    $("guess-bars").querySelectorAll("button.gb").forEach((b) => b.addEventListener("click", () => {
      $("guess-note").innerHTML = note({ char: b.dataset.c, prob: Number(b.dataset.p), is_selected: b.classList.contains("actual") });
    }));
  } catch (e) {
    $("guess-bars").textContent = e.message;
  }
}

// ---- 5. all together: "Word", step by step --------------------------------------------------------

const spread = new SpreadAnimation($("spread"));
const playTogether = player("together", async (stale) => {
  let r;
  try { r = await encode("shakespeare_char", "Word"); } catch (e) { $("narration").textContent = e.message; return; }
  if (stale()) return;
  $("narration").innerHTML = "";
  await spread.play(byId("shakespeare_char"), r, stale, (i) => {
    const t = r.trace[i];
    const li = document.createElement("li");
    li.innerHTML = `<b class="sym">${escapeHtml(t.symbol)}</b> ${escapeHtml(formatOdds(t.prob))} → ${formatCost(t.prob)} · ` +
      `<span class="${t.bits_added ? "" : "free"}">${t.bits_added} bit${t.bits_added === 1 ? "" : "s"} sent</span>`;
    $("narration").appendChild(li);
  });
  if (stale()) return;
  const li = document.createElement("li");
  li.className = "total";
  li.innerHTML = `total: <b>${r.stats.payload_bits} bits</b> instead of ${r.stats.utf8_bits}`;
  $("narration").appendChild(li);
});

// ---- 6. a fair comparison: symbols vs bits --------------------------------------------------------

const playFair = player("fair", async (stale) => {
  const rows = $("fair-rows");
  const models = FAIR.map(byId).filter(Boolean);
  const plainBits = 8 * new TextEncoder().encode(HAMLET).length;
  const nChars = [...HAMLET].length;
  rows.innerHTML = models.map((m) => `<div class="fair-row" data-id="${m.id}">
      <span class="avatar">${avatarSvg(m)}</span>
      <div class="fair-main"><div class="fair-name">${escapeHtml(persona(m).title)}</div>
        <div class="fair-bar"><span class="fair-key">symbols</span><span class="fair-track"><span class="fair-fill sym"></span></span><span class="fair-num sym-n">…</span></div>
        <div class="fair-bar"><span class="fair-key">bits</span><span class="fair-track"><span class="fair-fill bits"></span></span><span class="fair-num bits-n">${m.id === "gpt2" ? "loading GPT-2…" : "…"}</span></div>
      </div>
      <div class="fair-bpc"><b>…</b><span>bits / char</span></div>
    </div>`).join("");
  for (const m of models) {  // one at a time, GPT-2 last: it's slow the first time
    let r;
    try { r = await encode(m.id, HAMLET); } catch { continue; }
    if (stale()) return;
    const row = rows.querySelector(`[data-id="${m.id}"]`);
    row.querySelector(".fair-fill.sym").style.width = `${(100 * r.stats.symbols) / nChars}%`;
    row.querySelector(".fair-fill.bits").style.width = `${(100 * r.stats.payload_bits) / plainBits}%`;
    row.querySelector(".sym-n").textContent = String(r.stats.symbols);
    row.querySelector(".bits-n").textContent = String(r.stats.payload_bits);
    row.querySelector(".fair-bpc b").textContent = r.stats.bpc.toFixed(2);
    row.classList.add("done");
    await sleep(250);
  }
});

// ---- families, and start ---------------------------------------------------------------------------

function renderFamilies() {
  const sorted = sortModels(state.models.filter((m) => m.available));
  $("intro-families").innerHTML = FAMILIES.map((f) => {
    const members = sorted.filter((m) => persona(m).family === f.id);
    if (!members.length) return "";
    return `<a class="family-card" href="encoders.html#${f.id}">
        <span class="family-title">${escapeHtml(f.title)}</span><span class="family-tagline">${escapeHtml(f.tagline)}</span>
        <span class="family-faces">${members.map((m) => `<span class="avatar" title="${escapeHtml(persona(m).title)}">${avatarSvg(m)}</span>`).join("")}</span>
        <span class="family-count">${members.length} encoder${members.length === 1 ? "" : "s"} ▸</span></a>`;
  }).join("");
}

async function init() {
  initGlossary();
  try {
    state.models = (await api.getModels()).models;
  } catch (e) {
    $("race-result").textContent = `could not reach the API: ${e.message}`;
    return;
  }
  const shakespeare = byId("shakespeare_char");
  if (shakespeare) $("race-avatar").innerHTML = avatarSvg(shakespeare);
  renderFamilies();

  $("cut-tabs").innerHTML = CUTS.map(([, id, title], i) => {
    const m = byId(id);
    return `<button type="button" role="tab" data-i="${i}" ${m ? "" : "disabled"}>${m ? `<span class="avatar">${avatarSvg(m)}</span>` : ""}${escapeHtml(title)}</button>`;
  }).join("");
  $("cut-tabs").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => showCut(Number(b.dataset.i), { user: true })));

  $("guess-who").innerHTML = GUESSERS.map(byId).filter(Boolean).map((m) =>
    `<button type="button" data-id="${m.id}"><span class="avatar">${avatarSvg(m)}</span>${escapeHtml(persona(m).title)}</button>`).join("");
  $("guess-who").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => showGuess(b.dataset.id)));

  playHero();
  onView($("stage-chars"), () => { players.chars(); startCutCycle(); });
  onView($("stage-bits"), playHalving);
  onView($("stage-guess"), () => showGuess(GUESSERS[0]));
  onView($("stage-together"), playTogether);
  onView($("stage-fair"), playFair);
}

init();
