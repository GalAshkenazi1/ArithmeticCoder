// Wiring: header (status pill, model switcher, shared key), the two chat panels, and the centre
// panel (zoom canvas, bit tracker). All data comes from the backend API.

import * as api from "./api.js";
import { BitTracker } from "./bit-tracker.js";
import { ChatPanel } from "./chat.js";
import { ZoomCanvas } from "./zoom-canvas.js";

const PRESETS = [
  { text: "To be, or not to be, that is the question:", tag: "in Shakespeare's style" },
  { text: "O Romeo, Romeo! wherefore art thou Romeo?", tag: "in the training text" },
  { text: "Please send the quarterly report by Friday; thanks!", tag: "modern English" },
  { text: "The Eiffel Tower was completed in 1889 and is 330 metres (1,083 ft) tall.", tag: "encyclopedic, ASCII models" },
  { text: "for i in range(10): print(f\"{i} squared is {i ** 2}\")", tag: "Python, ASCII models" },
];

const $ = (id) => document.getElementById(id);
const state = { models: [], session: null, busy: false };

// ---- centre panel --------------------------------------------------------------------------
const tracker = new BitTracker($("bit-tracker"), { onSeek: (i) => zoom.seek(i) });
const zoom = new ZoomCanvas($("zoom-canvas"), {
  onStep: (i) => {
    tracker.show(i);
    $("step-slider").value = i;
    $("step-label").textContent = `${Math.min(i + 1, zoom.length)} / ${zoom.length}`;
  },
});

function showEncoding(response) {
  const from = response.sender === "alice" ? "Alice" : "Bob";
  $("zoom-caption").textContent = `${from} -> ${response.receiver === "alice" ? "Alice" : "Bob"}: ` +
    `${response.stats.chars} chars, ${response.stats.compressed_bits} bits`;
  $("step-slider").max = Math.max(0, response.trace.length - 1);
  tracker.setTrace(response.trace);
  zoom.setTrace(response.trace);
  panels.alice.markSelected(response);
  panels.bob.markSelected(response);
  if (response.trace.length) {
    zoom.play();
    setPlayLabel();
  }
}

function setPlayLabel() { $("btn-play").textContent = zoom.playing ? "Pause" : "Play"; }

$("btn-play").addEventListener("click", () => { zoom.playing ? zoom.pause() : zoom.play(); setPlayLabel(); });
$("btn-back").addEventListener("click", () => { zoom.stepBack(); setPlayLabel(); });
$("btn-forward").addEventListener("click", () => { zoom.stepForward(); setPlayLabel(); });
$("step-slider").addEventListener("input", (e) => { zoom.seek(Number(e.target.value)); setPlayLabel(); });
document.querySelectorAll("#speed button").forEach((btn) => btn.addEventListener("click", () => {
  zoom.setSpeed(Number(btn.dataset.speed));
  document.querySelectorAll("#speed button").forEach((b) => b.classList.toggle("active", b === btn));
}));
setInterval(setPlayLabel, 300); // keeps the label right when playback ends by itself

// ---- chat panels ---------------------------------------------------------------------------
async function send(sender, text) {
  if (state.busy) return;
  const from = panels[sender];
  const to = panels[sender === "alice" ? "bob" : "alice"];
  state.busy = true;
  from.setBusy(true);
  try {
    const response = await api.sendMessage(sender, text);
    from.clearInput();
    from.addMessage(response, true);
    to.addMessage(response, false);
    showEncoding(response);
  } catch (error) {
    from.showError(error.message);
  } finally {
    state.busy = false;
    from.setBusy(false);
  }
}

const panels = {
  alice: new ChatPanel($("alice-panel"), "alice", { onSend: (t) => send("alice", t), onSelect: showEncoding, presets: PRESETS }),
  bob: new ChatPanel($("bob-panel"), "bob", { onSend: (t) => send("bob", t), onSelect: showEncoding }),
};

// ---- header: shared session, model switcher, key -------------------------------------------
function renderSession(session, flash) {
  state.session = session;
  $("status-model").textContent = session.model_name;
  $("status-fingerprint").textContent = `0x${session.fingerprint_hex}`;
  $("status-vocab").textContent = session.vocab_size;
  $("key-input").value = session.key;
  panels.alice.setVocab(session.vocab);
  panels.bob.setVocab(session.vocab);
  const select = $("model-switcher");
  select.value = session.model_id;
  select.title = state.models.find((m) => m.id === session.model_id)?.description ?? "";
  if (flash) {
    const pill = $("status-pill");
    pill.classList.remove("flash");
    void pill.offsetWidth; // restart the animation
    pill.classList.add("flash");
  }
}

async function switchTo(modelId, key) {
  try {
    const session = await api.switchModel(modelId, key);
    renderSession(session, true);
    const line = `switched to ${session.model_name} - new shared fingerprint 0x${session.fingerprint_hex}`;
    panels.alice.addSystemLine(line);
    panels.bob.addSystemLine(line);
  } catch (error) {
    panels.alice.showError(error.message);
    if (state.session) $("model-switcher").value = state.session.model_id; // undo the selection
  }
}

function renderModelSwitcher(models) {
  const select = $("model-switcher");
  select.innerHTML = "";
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.name} (${model.vocab_size} chars)`;
    option.title = model.available ? model.description : `${model.description} (files missing)`;
    option.disabled = !model.available;
    select.appendChild(option);
  }
}

$("model-switcher").addEventListener("change", (event) => {
  if (event.target.value !== state.session?.model_id) switchTo(event.target.value, $("key-input").value);
});

$("key-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const key = $("key-input").value.trim();
  if (key && state.session && key !== state.session.key) switchTo(state.session.model_id, key);
});

async function init() {
  try {
    const [models, session] = await Promise.all([api.getModels(), api.getState()]);
    state.models = models.models;
    renderModelSwitcher(models.models);
    renderSession(session, false);
    zoom.draw();
  } catch (error) {
    panels.alice.showError(`could not reach the API: ${error.message}`);
  }
}

init();
