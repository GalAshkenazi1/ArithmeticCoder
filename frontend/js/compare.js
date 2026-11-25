// Compare page (1 v 1): two encoders, one text.
//
// Encoders cut text differently (characters, bytes, words, GPT-2 tokens), so both charts run over
// the characters of the text: a symbol's cost is spread over the characters it covers. Each side's
// play button opens its coding animation below; while it plays, the charts mark the current symbol.

import * as api from "./api.js";
import { charCosts, symbolGroups } from "./char-costs.js";
import { CumulativeChart, MirrorChart } from "./compare-charts.js";
import { EncoderPicker, pickerElements } from "./encoder-picker.js";
import { avatarSvg, persona } from "./encoders.js";
import { displayChar, escapeHtml } from "./format.js";
import { initGlossary } from "./glossary.js";
import { Ladder } from "./ladder.js";
import { initViewToggle } from "./view-mode.js";

// series colours: the categorical palette's first two dark steps (validated on this surface).
// The colour belongs to the side (top / bottom), so swapping encoders swaps their colours with them.
const COLORS = { top: "#3987e5", bottom: "#d95926" };
const DEFAULTS = { top: "web_words", bottom: "shakespeare_char" };
const EXAMPLES = [
  { label: "Shakespeare", text: "To be, or not to be, that is the question:",
    note: "Characters against words: the word encoder needs a third of the symbols, but each one is a harder guess." },
  { label: "a children's story", text: "Once upon a time, there was a little cat named Tom.",
    note: "Try the Storyteller Encoder here: it has read thousands of stories that start like this." },
  { label: "web text", text: "Please contact us for more information about our services.",
    note: "Typical web phrasing: the web encoders and GPT-2 have seen it countless times." },
  { label: "code", text: "def __init__(self, name, value=None):",
    note: "Code: the Python Encoder against anything else shows how much the training text matters." },
  { label: "other languages", text: "Grüße aus Zürich! שלום \u{1F44B}",
    note: "Character encoders can't take this at all; bytes pay 2–4 symbols per character; GPT-2 knows some of it." },
];
const ANY_TEXT = ["web_bytes", "gpt2", "web_words", "uniform_bytes"];  // offered when an encoder can't take the text
const HOLD_MS = 280;
const MAX_ANIMATED = 60;
const CACHE_SIZE = 60;

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shortTitle = (model) => persona(model).title.replace(/ Encoder$/, "");

const state = { models: [], text: "", chars: [], generation: 0, debounce: null, cache: new Map() };
const anim = { side: null, modelId: null, playing: false, token: 0, speed: 1 };  // modelId: whose rows the ladder shows

const sides = Object.fromEntries(["top", "bottom"].map((key) => {
  const card = $(`card-${key}`);
  card.style.setProperty("--slot-color", COLORS[key]);
  const side = { key, color: COLORS[key], card, resultEl: card.querySelector(".duel-result"), model: null,
    result: null, error: null, groups: null, costs: null };
  side.picker = new EncoderPicker(pickerElements(card.querySelector(".picker")), { onSelect: (m) => setModel(side, m) });
  const play = $(`play-${key}`);
  play.style.setProperty("--slot-color", COLORS[key]);
  play.addEventListener("click", () => (anim.side === key && anim.playing ? pauseAnim() : openAnimation(key)));
  return [key, side];
}));
const both = () => [sides.top, sides.bottom];
const other = (side) => (side.key === "top" ? sides.bottom : sides.top);

initGlossary();
initViewToggle($("view-toggle"));
const mirror = new MirrorChart($("mirror-scroll"), $("mirror-svg"), $("mirror-tooltip"), { onSeek: seekFromChart });
const cumulative = new CumulativeChart($("cum-area"), $("cum-svg"), $("cum-tooltip"), { onSeek: (c) => seekFromChart(c) });
const ladder = new Ladder($("ladder"));

// ---- choosing encoders -------------------------------------------------------------------------

function unknownChars(model, text) {
  if (!model.vocab) return [];
  const vocab = new Set(model.vocab);
  return [...new Set([...text].filter((c) => !vocab.has(c)))];
}

function showModels() {
  for (const side of both()) {
    side.picker.show(side.model, side.color);
    side.picker.markUsed([other(side).model?.id].filter(Boolean));
  }
  $("play-top").title = `watch the ${persona(sides.top.model).title} encode`;
  $("play-bottom").title = `watch the ${persona(sides.bottom.model).title} encode`;
}

function setModel(side, model) {
  side.model = model;
  showModels();
  encodeAll();
}

$("btn-swap").addEventListener("click", () => {
  [sides.top.model, sides.bottom.model] = [sides.bottom.model, sides.top.model];
  if (anim.side) anim.side = anim.side === "top" ? "bottom" : "top";  // the animation follows its encoder
  showModels();
  encodeAll();
});

// ---- encoding ----------------------------------------------------------------------------------

async function encodeOne(model, text) {
  const unknown = unknownChars(model, text);
  if (unknown.length) return { error: unknownMessage(model, unknown) };
  const key = `${model.id}\u0000${text}`;
  if (state.cache.has(key)) return { result: state.cache.get(key) };
  try {
    const result = await api.encode(model.id, text);
    state.cache.set(key, result);
    if (state.cache.size > CACHE_SIZE) state.cache.delete(state.cache.keys().next().value);
    return { result };
  } catch (error) {
    return { error: error.detail?.unknown_chars ? unknownMessage(model, error.detail.unknown_chars) : error.message };
  }
}

function unknownMessage(model, chars) {
  const list = chars.map((c) => `'${displayChar(c)}'`).join(" ");
  return `Can't encode this text: ${list} ${chars.length === 1 ? "isn't" : "aren't"} among its ${model.vocab_size} characters.`;
}

function scheduleEncode(delay = 260) {
  clearTimeout(state.debounce);
  state.debounce = setTimeout(encodeAll, delay);
}

async function encodeAll() {
  const generation = ++state.generation;
  const text = $("text-input").value;
  const models = both().map((s) => s.model);
  const slow = models.some((m) => m.tokenizer === "gpt2" && !state.cache.has(`${m.id}\u0000${text}`));
  $("busy").hidden = false;
  $("busy").textContent = slow ? "encoding (GPT-2 takes a few seconds)…" : "encoding…";
  const outcomes = await Promise.all(models.map((m) => encodeOne(m, text)));
  if (generation !== state.generation) return;  // a newer edit is on its way
  $("busy").hidden = true;
  state.text = text;
  state.chars = [...text];
  both().forEach((side, i) => {
    if (side.model !== models[i]) return;
    side.result = outcomes[i].result ?? null;
    side.error = outcomes[i].error ?? null;
    side.groups = side.result ? symbolGroups(text, side.result.trace) : null;
    side.costs = side.result ? charCosts(text, side.result.trace) : null;
  });
  render();
  writeUrl();
  if (anim.side) refreshAnimation();
}

function render() {
  const unable = state.models.filter((m) => unknownChars(m, state.text).length).map((m) => m.id);
  for (const side of both()) {
    side.picker.markUnable(unable);
    side.card.classList.toggle("failed", Boolean(side.error));
    if (side.error) {
      const fallback = ANY_TEXT.map((id) => state.models.find((m) => m.id === id && m.available))
        .find((m) => m && m !== other(side).model);
      side.resultEl.innerHTML = `<span class="bad">${escapeHtml(side.error)}</span>` +
        (fallback ? ` <button type="button" class="fix">use the ${escapeHtml(persona(fallback).title)}</button>` : "");
      side.resultEl.querySelector(".fix")?.addEventListener("click", () => setModel(side, fallback));
    }
    else if (side.result) {
      const s = side.result.stats;
      side.resultEl.innerHTML = `<b>${s.payload_bits}</b> bits · <b>${s.bpc.toFixed(2)}</b> bits/char · ` +
        `${s.symbols} symbol${s.symbols === 1 ? "" : "s"}`;
    } else side.resultEl.textContent = "";
    $(`play-${side.key}`).disabled = !side.result || !side.result.trace.length;
  }
  const chartSide = (side) => (side.result ? { color: side.color, short: shortTitle(side.model), groups: side.groups } : null);
  const words = wordWinners();
  mirror.setData({ top: chartSide(sides.top), bottom: chartSide(sides.bottom) }, state.chars, words);
  const series = both().filter((s) => s.result).map((s) => ({ color: s.color, short: shortTitle(s.model),
    cumulative: s.costs.cumulative }));
  cumulative.setData(series, state.chars, charCosts(state.text, []).utf8Cumulative);
  $("verdict").innerHTML = verdict();
  $("insight").innerHTML = insight(words);
}

/** Each word of the text, its cost for both encoders, and which one paid less (null: a tie or one failed). */
function wordWinners() {
  const [top, bottom] = [sides.top, sides.bottom];
  const words = [];
  const text = state.chars;
  for (let i = 0; i < text.length;) {
    if (/\s/.test(text[i])) { i++; continue; }
    let j = i;
    while (j < text.length && !/\s/.test(text[j])) j++;
    const cost = (side) => (side.costs ? side.costs.cumulative[j] - side.costs.cumulative[i] : null);
    const a = cost(top);
    const b = cost(bottom);
    const winner = a === null || b === null || Math.abs(a - b) < 0.05 ? null : a < b ? "top" : "bottom";
    words.push({ start: i, end: j, text: text.slice(i, j).join(""), top: a, bottom: b, winner });
    i = j;
  }
  return words;
}

/** "Word by word, the X saves the most on 'question:' (5.2 vs 12.0 bits); the Y on 'To' (...)". */
function insight(words) {
  if (!sides.top.result || !sides.bottom.result || words.length < 2) return "";
  const parts = [];
  for (const [mine, theirs] of [["top", "bottom"], ["bottom", "top"]]) {
    const best = words.filter((w) => w.winner === mine).sort((a, b) => (b[theirs] - b[mine]) - (a[theirs] - a[mine]))[0];
    if (best) {
      parts.push(`<i class="dot" style="background:${sides[mine].color}"></i>the <b>${escapeHtml(persona(sides[mine].model).title)}</b> ` +
        `saves the most on '${escapeHtml(best.text)}' (${best[mine].toFixed(1)} vs ${best[theirs].toFixed(1)} bits)`);
    }
  }
  const wins = (key) => words.filter((w) => w.winner === key).length;
  const tally = `${escapeHtml(shortTitle(sides.top.model))} pays less for ${wins("top")} of the ${words.length} words, ` +
    `${escapeHtml(shortTitle(sides.bottom.model))} for ${wins("bottom")}.`;
  return parts.length ? `Word by word: ${parts.join("; ")}. ${tally}` : "";
}

function verdict() {
  const [a, b] = both();
  if (!state.chars.length) return "";
  if (!a.result || !b.result) {
    const ok = [a, b].find((s) => s.result);
    return ok ? `Only the <b>${escapeHtml(persona(ok.model).title)}</b> can encode this text.` : "";
  }
  const bitsA = a.result.stats.payload_bits;
  const bitsB = b.result.stats.payload_bits;
  if (bitsA === bitsB) return `Both need <b>${bitsA} bits</b>.`;
  const [win, lose] = bitsA < bitsB ? [a, b] : [b, a];
  const saved = lose.result.stats.payload_bits - win.result.stats.payload_bits;
  const pct = Math.round((100 * saved) / lose.result.stats.payload_bits);
  return `<i class="dot" style="background:${win.color}"></i>The <b>${escapeHtml(persona(win.model).title)}</b> needs ` +
    `<b>${saved} fewer bit${saved === 1 ? "" : "s"}</b> (${pct}% less) than the ${escapeHtml(persona(lose.model).title)}.`;
}

// ---- the coding animation (one encoder at a time) -----------------------------------------------

const animSide = () => (anim.side ? sides[anim.side] : null);
const animTotal = () => animSide()?.result?.trace.length ?? 0;

/** Show side's animation panel; the ladder starts over if it was showing another encoder. */
function showAnimationOf(side) {
  anim.side = side.key;
  $("anim").hidden = false;
  $("anim").style.setProperty("--slot-color", side.color);
  $("anim-avatar").innerHTML = avatarSvg(side.model, side.color);
  $("anim-title").textContent = persona(side.model).title;
  if (anim.modelId !== side.model.id) ladder.truncate(0);
  anim.modelId = side.model.id;
  ladder.setData(state.text, side.result.trace);  // keeps the rows of an unchanged start
}

function openAnimation(key) {
  const side = sides[key];
  if (!side.result) return;
  showAnimationOf(side);
  if (ladder.count >= animTotal()) ladder.truncate(0);  // finished before: play again
  $("anim").scrollIntoView({ behavior: "smooth", block: "nearest" });
  playTo(animTotal());
}

/** New text or encoder while the animation is open: keep the rows that are still right, play the rest. */
function refreshAnimation() {
  const side = animSide();
  if (!side.result) { closeAnimation(); return; }
  showAnimationOf(side);
  playTo(animTotal());
}

function closeAnimation() {
  anim.side = anim.modelId = null;  // first: syncCursor must not look for a result that may be gone
  pauseAnim();
  ladder.truncate(0);
  $("anim").hidden = true;
  syncCursor();
}

function syncCursor() {
  const side = animSide();
  const count = ladder.count;
  $("step-label").textContent = `${count} / ${animTotal()} symbols`;
  $("btn-play").innerHTML = anim.playing ? "&#10074;&#10074;" : "&#9654;";
  for (const s of both()) {
    const playing = anim.side === s.key && anim.playing;
    $(`play-${s.key}`).innerHTML = playing ? "&#10074;&#10074;" : "&#9654;";
    $(`play-${s.key}`).classList.toggle("active", anim.side === s.key);
  }
  if (!side?.result || !count) {
    mirror.setHighlight(null);
    cumulative.setMarker(null);
    return;
  }
  const t = side.result.trace[count - 1];
  const group = side.groups.find((g) => g.start <= t.char_start && t.char_start < g.end);
  mirror.setHighlight(group ? { side: side.key, start: group.start, end: group.end } : null);
  cumulative.setMarker(t.char_end);
}

async function playTo(target) {
  const token = ++anim.token;
  anim.playing = true;
  syncCursor();
  while (token === anim.token && ladder.count < Math.min(target, animTotal())) {
    const animate = target - ladder.count <= MAX_ANIMATED;
    await ladder.appendRow(animate);
    syncCursor();
    if (animate) await sleep(HOLD_MS / anim.speed);
  }
  if (token === anim.token) anim.playing = false;
  syncCursor();
}

function pauseAnim() {
  anim.token++;
  anim.playing = false;
  syncCursor();
}

function seek(n) {
  pauseAnim();
  n = Math.max(0, Math.min(n, animTotal()));
  if (n < ladder.count) ladder.truncate(n);
  while (ladder.count < n) ladder.appendRow(false);
  syncCursor();
}

/** A click on a chart: show that side's animation up to the end of the clicked character. */
function seekFromChart(c, key) {
  key = key ?? anim.side ?? "top";
  const side = sides[key];
  if (!side.result) return;
  if (anim.side !== key) showAnimationOf(side);
  seek(side.costs.stepsAt[Math.min(c, side.costs.chars.length)]);
}

$("btn-play").addEventListener("click", () => {
  if (anim.playing) { pauseAnim(); return; }
  if (ladder.count >= animTotal()) ladder.truncate(0);
  playTo(animTotal());
});
$("btn-replay").addEventListener("click", () => { pauseAnim(); ladder.truncate(0); playTo(animTotal()); });
$("btn-back").addEventListener("click", () => seek(ladder.count - 1));
$("btn-forward").addEventListener("click", () => { pauseAnim(); playTo(ladder.count + 1); });
$("anim-close").addEventListener("click", closeAnimation);
document.querySelectorAll("#speed button").forEach((btn) => btn.addEventListener("click", () => {
  anim.speed = ladder.speed = Number(btn.dataset.speed);
  document.querySelectorAll("#speed button").forEach((b) => b.classList.toggle("active", b === btn));
}));

// ---- input, URL, start -------------------------------------------------------------------------

$("text-input").addEventListener("input", () => { $("example-note").textContent = ""; scheduleEncode(); });
for (const example of EXAMPLES) {
  const button = document.createElement("button");
  button.type = "button";
  button.innerHTML = `<b>${escapeHtml(example.label)}</b>`;
  button.title = example.text;
  button.addEventListener("click", () => {
    $("text-input").value = example.text;
    $("example-note").textContent = example.note;
    document.querySelectorAll("#examples button").forEach((b) => b.classList.toggle("active", b === button));
    clearTimeout(state.debounce);
    encodeAll();
  });
  $("examples").appendChild(button);
}

function writeUrl() {
  const params = new URLSearchParams({ models: `${sides.top.model.id},${sides.bottom.model.id}`, text: $("text-input").value });
  history.replaceState(null, "", `?${params}`);
}

async function init() {
  try {
    const { models } = await api.getModels();
    state.models = models;
    for (const side of both()) side.picker.setModels(models);
    const params = new URLSearchParams(location.search);
    const find = (id) => models.find((m) => m.id === id && m.available);
    const wanted = [...new Set((params.get("models") ?? "").split(",").filter(Boolean))].map(find).filter(Boolean);
    sides.top.model = wanted[0] ?? find(DEFAULTS.top) ?? models.find((m) => m.available);
    sides.bottom.model = wanted[1] ?? [find(DEFAULTS.bottom), find(DEFAULTS.top), ...models.filter((m) => m.available)]
      .find((m) => m && m !== sides.top.model);
    showModels();
    $("text-input").value = params.get("text") ?? EXAMPLES[0].text;
    if (!params.has("text")) {
      $("example-note").textContent = EXAMPLES[0].note;
      $("examples").querySelector("button").classList.add("active");
    }
    encodeAll();
  } catch (error) {
    $("input-error").textContent = `could not reach the API: ${error.message}`;
  }
}

init();
