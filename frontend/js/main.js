// Encode page: pick an encoder, type, watch the coding animation, read the bits, and watch the
// receiver decode them. Encoding is causal, so when you keep typing, the rows of the unchanged start
// stay and only the new symbols animate in.

import * as api from "./api.js";
import { BpcGraph } from "./bpc-graph.js";
import { EncoderPicker } from "./encoder-picker.js";
import { avatarSvg, persona } from "./encoders.js";
import { displayChar, escapeHtml } from "./format.js";
import { initGlossary } from "./glossary.js";
import { Ladder } from "./ladder.js";
import { Output } from "./output.js";
import { Tour } from "./tour.js";
import { initViewToggle } from "./view-mode.js";

const FIRST_TEXT = "Word";  // the PDF's example word
const ANY_TEXT = ["web_bytes", "gpt2", "uniform_bytes"];  // offered when an encoder can't take the text
const HOLD_MS = 280;       // pause after each row at 1x
const MAX_ANIMATED = 60;   // longer backlogs (a pasted paragraph) are shown without animation

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const state = {
  models: [], model: null, vocab: null, result: null,
  playToken: 0, playing: false, speed: 1,
  encodeController: null, decodeController: null, debounce: null,
  recvToken: 0, recvPlaying: false,
};

initGlossary();
initViewToggle($("view-toggle"));
const ladder = new Ladder($("ladder"));
const receiver = new Ladder($("receiver-ladder"), { mode: "decode" });
const graph = new BpcGraph($("graph"), $("graph-svg"), $("graph-tooltip"), { onSeek: seek });
const output = new Output({ bits: $("bits"), stats: $("stats"), decodeStatus: $("decode-status"), copy: $("btn-copy") });
const picker = new EncoderPicker(
  { card: $("encoder-card"), menu: $("encoder-menu"), avatar: $("encoder-avatar"), name: $("encoder-name"), sub: $("encoder-sub") },
  { onSelect: selectModel },
);

// ---- playback ------------------------------------------------------------------------------

const total = () => state.result?.trace.length ?? 0;

function syncCursor() {
  graph.setCursor(ladder.count);
  output.setCursor(ladder.count);
  renderHeadline();
  $("step-label").textContent = `${ladder.count} / ${total()}`;
  $("btn-play").innerHTML = state.playing ? "&#10074;&#10074;" : "&#9654;";
  $("btn-play").title = state.playing ? "pause" : "play";
}

async function playTo(target) {
  const token = ++state.playToken;
  state.playing = true;
  syncCursor();
  while (token === state.playToken && ladder.count < Math.min(target, total())) {
    const animate = target - ladder.count <= MAX_ANIMATED;
    await ladder.appendRow(animate);
    syncCursor();
    if (animate) await sleep(HOLD_MS / state.speed);
  }
  if (token === state.playToken) state.playing = false;
  syncCursor();
}

function pause() {
  state.playToken++;
  state.playing = false;
}

function seek(n) {
  pause();
  n = Math.max(0, Math.min(n, total()));
  if (n < ladder.count) ladder.truncate(n);
  while (ladder.count < n) ladder.appendRow(false);
  syncCursor();
}

$("btn-play").addEventListener("click", () => {
  if (state.playing) { pause(); syncCursor(); return; }
  if (ladder.count >= total()) ladder.truncate(0);  // at the end: play again from the start
  playTo(total());
});
$("btn-replay").addEventListener("click", () => { pause(); ladder.truncate(0); syncCursor(); playTo(total()); });
$("btn-back").addEventListener("click", () => seek(ladder.count - 1));
$("btn-forward").addEventListener("click", () => { pause(); playTo(ladder.count + 1); });
document.querySelectorAll("#speed button").forEach((btn) => btn.addEventListener("click", () => {
  state.speed = ladder.speed = receiver.speed = Number(btn.dataset.speed);
  document.querySelectorAll("#speed button").forEach((b) => b.classList.toggle("active", b === btn));
}));

// ---- the result, up front ---------------------------------------------------------------------

function renderHeadline() {
  const r = state.result;
  const el = $("headline");
  if (!r || !r.trace.length) {
    el.innerHTML = '<span class="headline-empty">Type something to see how many bits it needs.</span>';
    return;
  }
  const s = r.stats;
  const done = ladder.count >= r.trace.length;
  const step = r.trace[Math.max(0, ladder.count - 1)];
  const chars = ladder.count ? step.char_end : 0;
  const bits = ladder.count ? step.running_bits.length : 0;
  const plain = s.utf8_bits / s.chars;
  const bpc = done ? s.bpc : chars ? bits / chars : 0;
  el.innerHTML = `<span class="big">${bpc.toFixed(2)}</span>
    <span class="unit"><span class="term" data-term="bpc">bits per character</span>${done ? "" : " so far"}</span>
    <span class="vs">${done
      ? `plain text needs ${plain.toFixed(plain % 1 ? 1 : 0)} · <b>${s.ratio.toFixed(1)}× smaller</b> · ${s.payload_bits} bits for ${s.chars} characters`
      : `${bits} bits sent for the first ${chars} of ${s.chars} characters`}</span>`;
}

// ---- encoding ------------------------------------------------------------------------------

function setBusy(busy, label = "encoding…") {
  $("busy").hidden = !busy;
  $("busy").textContent = label;
}

/** An error, with a button that fixes it when there is one. */
function showError(message, action) {
  $("input-error").innerHTML = message ? `${escapeHtml(message)}${action ? ` <button type="button" class="fix">${escapeHtml(action.label)}</button>` : ""}` : "";
  if (action) $("input-error").querySelector(".fix").addEventListener("click", action.run);
}

function unknownCharsError(chars) {
  const list = chars.map((c) => `'${displayChar(c)}'`).join(" ");
  const message = `The ${persona(state.model).title} only knows ${state.model.vocab_size} characters, and ${list} ` +
    `${chars.length === 1 ? "isn't" : "aren't"} among them.`;
  const fallback = ANY_TEXT.map((id) => state.models.find((m) => m.id === id && m.available)).find(Boolean);
  showError(message, fallback && { label: `switch to the ${persona(fallback).title}`, run: () => selectModel(fallback) });
}

function scheduleEncode(delay = 260) {
  clearTimeout(state.debounce);
  state.debounce = setTimeout(runEncode, delay);
}

async function runEncode() {
  const model = state.model;
  if (!model) return;
  const text = $("text-input").value;
  const unknown = state.vocab ? [...new Set([...text].filter((c) => !state.vocab.has(c)))] : [];
  if (unknown.length) { unknownCharsError(unknown); return; }
  showError("");
  state.encodeController?.abort();
  const controller = state.encodeController = new AbortController();
  const firstUse = state.result?.model_id !== model.id;
  setBusy(true, firstUse && model.id === "gpt2" ? "loading GPT-2 (500 MB) and encoding…" : "encoding…");
  try {
    const result = await api.encode(model.id, text, controller.signal);
    if (!controller.signal.aborted) applyResult(result);
  } catch (error) {
    if (error.name === "AbortError") return;
    if (error.detail?.unknown_chars) unknownCharsError(error.detail.unknown_chars);
    else showError(error.message);
  } finally {
    if (state.encodeController === controller) setBusy(false);
  }
}

function applyResult(result) {
  pause();
  closeReceiver();
  if (state.result?.model_id !== result.model_id) ladder.truncate(0);  // another encoder: start over
  state.result = result;
  ladder.setData(result.text, result.trace);  // keeps the rows of the unchanged leading symbols
  graph.setData(result.text, result.trace);
  output.setData(result);
  $("btn-receiver").disabled = !result.trace.length;
  syncCursor();
  playTo(result.trace.length);
  runDecode(result);
  maybeStartTour();
}

async function runDecode(result) {
  state.decodeController?.abort();
  const controller = state.decodeController = new AbortController();
  if (!result.trace.length) return;
  output.setDecode("running");
  try {
    const { text } = await api.decode(result.model_id, result.bits, result.symbols, controller.signal);
    if (controller.signal.aborted || state.result !== result) return;
    output.setDecode(text === result.text ? { ok: true } : { error: "decoding gave a different text" });
  } catch (error) {
    if (error.name !== "AbortError" && state.result === result) output.setDecode({ error: error.message });
  }
}

function selectModel(model) {
  state.model = model;
  state.vocab = model.vocab ? new Set(model.vocab) : null;
  picker.show(model);
  runEncode();
}

$("text-input").addEventListener("input", () => scheduleEncode());

// ---- the receiver: the same model decodes the bits, row by row ---------------------------------

const recvTotal = () => (state.result ? state.result.trace.length : 0);

function recvSync() {
  const r = state.result;
  const count = receiver.count;
  $("recv-step").textContent = `${count} / ${recvTotal()} symbols`;
  $("recv-play").innerHTML = state.recvPlaying ? "&#10074;&#10074;" : "&#9654;";
  if (!r) return;
  const chars = [...r.text];
  const done = count ? r.trace[count - 1].char_end : 0;
  const start = count ? r.trace[count - 1].char_start : 0;
  $("recv-text").innerHTML = `${escapeHtml(chars.slice(0, start).join(""))}<span class="latest">${escapeHtml(chars.slice(start, done).join(""))}</span>` +
    (count >= recvTotal() ? ' <span class="ok">✓ the whole text</span>' : '<span class="caret">▍</span>');
}

async function recvPlayTo(target) {
  const token = ++state.recvToken;
  state.recvPlaying = true;
  recvSync();
  while (token === state.recvToken && receiver.count < Math.min(target, recvTotal())) {
    await receiver.appendRow(true);
    recvSync();
    await sleep(HOLD_MS / state.speed);
  }
  if (token === state.recvToken) state.recvPlaying = false;
  recvSync();
}

function openReceiver() {
  const r = state.result;
  if (!r?.trace.length) return;
  pause();
  $("receiver").hidden = false;
  $("receiver-avatar").innerHTML = avatarSvg(state.model);
  $("recv-bits").textContent = `0.${r.bits} (${r.bits.length} bits) + the symbol count (${r.symbols})`;
  receiver.truncate(0);
  receiver.setData(r.text, r.trace);
  $("receiver").scrollIntoView({ behavior: "smooth", block: "start" });
  recvPlayTo(recvTotal());
}

function closeReceiver() {
  state.recvToken++;
  state.recvPlaying = false;
  receiver.truncate(0);
  $("receiver").hidden = true;
}

$("btn-receiver").addEventListener("click", openReceiver);
$("recv-close").addEventListener("click", closeReceiver);
$("recv-replay").addEventListener("click", () => { receiver.truncate(0); recvPlayTo(recvTotal()); });
$("recv-play").addEventListener("click", () => {
  if (state.recvPlaying) { state.recvToken++; state.recvPlaying = false; recvSync(); return; }
  if (receiver.count >= recvTotal()) receiver.truncate(0);
  recvPlayTo(recvTotal());
});

// ---- the guided tour (once, then on request) --------------------------------------------------

const tour = new Tour([
  { target: "#text-input", title: "Type anything",
    text: "It's encoded as you type." },
  { target: "#encoder-card", title: "Pick an encoder",
    text: "An encoder is a language model plus a way to cut text into symbols. Each one learned from a different kind of text." },
  { target: () => document.querySelector("#ladder .row"), title: "One row per symbol",
    text: "The line is every number still possible. The boxes are the model's guesses for the next symbol, each as wide as its probability. The chosen box (violet) is stretched into the next row." },
  { target: () => document.querySelector("#ladder .row .word"), title: "What each symbol cost",
    text: "“1 in 17 → 4.1 bits”: the model gave this letter a 1-in-17 chance, so it costs about log₂ 17 = 4.1 bits. Likely letters are nearly free." },
  { target: "#bits", title: "The bits sent",
    text: "The green dot on each row is the shortest binary fraction inside the chosen box. Its digits are the bits sent; they arrive in bursts." },
  { target: "#graph", title: "Cost of each character",
    text: "Each bar is what one character cost. Plain text costs 8 bits per character: the dashed line." },
  { target: "#headline", title: "The result",
    text: "Bits per character, against 8 for plain text. Press “watch the receiver decode it” to see the bits turned back into your text." },
  { target: "#view-toggle", title: "Simple or detailed",
    text: "Detailed also shows each interval's exact bounds and the binary fraction. Hover any dotted word for a definition." },
], "arith.tour.encode");

function maybeStartTour() {
  if (tour.seen || tour.index >= 0 || maybeStartTour.started) return;
  maybeStartTour.started = true;
  setTimeout(() => { if (ladder.count) tour.start(); else maybeStartTour.started = false; }, 1800);
}
$("btn-tour").addEventListener("click", () => tour.start());

// ---- start -----------------------------------------------------------------------------------

async function init() {
  renderHeadline();
  try {
    const { models, default: defaultId } = await api.getModels();
    state.models = models;
    picker.setModels(models);
    // links from the other pages bring ?model=<id>&text=<text>
    const params = new URLSearchParams(location.search);
    const fromLink = params.has("text") || params.has("model");
    $("text-input").value = params.get("text") ?? FIRST_TEXT;
    if (fromLink) maybeStartTour.started = true;  // arriving from a link to a specific example: no tour this time
    const wanted = models.find((m) => m.id === params.get("model") && m.available);
    selectModel(wanted ?? models.find((m) => m.id === defaultId) ?? models.find((m) => m.available));
  } catch (error) {
    showError(`could not reach the API: ${error.message}`);
  }
}

init();
