// "The encoders" page, by family: pick a family (characters, bytes and words, pretrained,
// baselines) to read how it works and see its encoders; pick an encoder for its training data,
// symbols and typical sentences.

import * as api from "./api.js";
import { FAMILIES, avatarSvg, familyOf, persona, sortModels, tokenizerLabel } from "./encoders.js";
import { escapeHtml } from "./format.js";
import { initGlossary } from "./glossary.js";

/** How each kind of tokenizer cuts text (a family shows the kinds it contains). */
const KINDS = {
  char: {
    title: "Characters",
    symbol: "one character",
    alphabet: "65 or 96 characters",
    anyText: "No: é, emoji and Hebrew are out",
    perSymbol: "1 character",
    how: "Spells every word letter by letter. Most bits go on first letters.",
  },
  bytes: {
    title: "Bytes",
    symbol: "one UTF-8 byte",
    alphabet: "256 bytes",
    anyText: "Yes",
    perSymbol: "an English letter; é is 2, an emoji 4",
    how: "Like characters, but any text works. Non-English text needs more symbols.",
  },
  words: {
    title: "Words + byte escape",
    symbol: "a common word (like ␣the), or a byte",
    alphabet: "4,096 words + 256 bytes",
    anyText: "Yes: unknown words are spelled in bytes",
    perSymbol: "about 2 characters",
    how: "A known word is one guess. Rare words, names and numbers fall back to bytes.",
  },
  gpt2: {
    title: "GPT-2 tokens (BPE)",
    symbol: "a word or a word piece",
    alphabet: "50,257 tokens",
    anyText: "Yes",
    perSymbol: "about 4 characters",
    how: "Common words are one token; rare ones split into a few pieces.",
  },
  uniform: {
    title: "No model (uniform)",
    symbol: "a character or a byte",
    alphabet: "96 characters or 256 bytes",
    anyText: "Byte version only",
    perSymbol: "1 character or byte",
    how: "Every symbol equally likely: 6.58 or 8 bits each, whatever you type.",
  },
};

/** What each family is about (shown when the family is picked). */
const FAMILY_INFO = {
  characters: {
    kinds: ["char"],
    intro: "One symbol per character. Same small model, different training text: each is best at its own kind of text.",
    catch: "Characters outside the alphabet can't be encoded.",
  },
  "bytes-words": {
    kinds: ["bytes", "words"],
    intro: "Two ways to take any text, both trained on the web: bytes, or whole words with a byte fallback.",
    catch: "Bytes pay extra for non-English text; words pay extra for unknown words.",
  },
  pretrained: {
    kinds: ["gpt2"],
    intro: "OpenAI's GPT-2: 40× bigger than our models, trained on 40 GB of web text. It guesses best.",
    catch: "Slow on a CPU, and it sees only the last 256 tokens.",
  },
  baselines: {
    kinds: ["uniform"],
    intro: "No model: every symbol equally likely. The bar the trained encoders must beat.",
    catch: "The byte version is exactly plain text: 8 bits per byte.",
  },
};

// the encoder to compare a typical sentence with (the first that can encode it)
const COMPARE_PARTNERS = ["gpt2", "web_words", "web_bytes", "shakespeare_char"];

const $ = (id) => document.getElementById(id);
const state = { models: [], family: null, selected: null, symbols: new Map(), costs: new Map() };

const kindOf = (model) => (model.kind === "uniform" ? "uniform" : model.tokenizer);
const chipLabel = (label) => label.replace(/ /g, "␣").replace(/\n/g, "↵") || "∅";
const canEncode = (model, text) => !model.vocab || [...text].every((c) => model.vocab.includes(c));
const membersOf = (familyId) => sortModels(state.models).filter((m) => persona(m).family === familyId);
const byId = (id) => state.models.find((m) => m.id === id);

const formatParams = (n) => (n >= 1e8 ? `${Math.round(n / 1e6)}M` : `${(n / 1e6).toFixed(1)}M`);
const formatChars = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} million` : n.toLocaleString("en-US"));

// ---- families ----------------------------------------------------------------------------------

function renderFamilyCards() {
  $("families").innerHTML = FAMILIES.map((family) => {
    const members = membersOf(family.id);
    if (!members.length) return "";
    return `<button type="button" class="family-card" data-family="${family.id}" role="tab">
        <span class="family-title">${escapeHtml(family.title)}</span>
        <span class="family-tagline">${escapeHtml(family.tagline)}</span>
        <span class="family-faces">${members.map((m) => `<span class="avatar" title="${escapeHtml(persona(m).title)}">${avatarSvg(m)}</span>`).join("")}</span>
        <span class="family-count">${members.length} encoder${members.length === 1 ? "" : "s"}</span>
      </button>`;
  }).join("");
  $("families").querySelectorAll(".family-card").forEach((el) => el.addEventListener("click", () => selectFamily(el.dataset.family)));
}

function kindFacts(kind) {
  const k = KINDS[kind];
  return `<article class="kind-facts">
      <h4>${escapeHtml(k.title)}</h4>
      <dl>
        <div><dt>one symbol</dt><dd>${escapeHtml(k.symbol)}</dd></div>
        <div><dt>alphabet</dt><dd>${escapeHtml(k.alphabet)}</dd></div>
        <div><dt>any text?</dt><dd>${escapeHtml(k.anyText)}</dd></div>
        <div><dt>per symbol</dt><dd>${escapeHtml(k.perSymbol)}</dd></div>
      </dl>
      <p>${escapeHtml(k.how)}</p>
    </article>`;
}

function memberCard(model) {
  const p = persona(model);
  const facts = [model.dataset?.name, model.training?.val_bits_per_char ? `${model.training.val_bits_per_char.toFixed(2)} bits/char on its own text` : ""]
    .filter(Boolean).join(" · ");
  return `<button type="button" class="member" data-id="${model.id}" ${model.available ? "" : "disabled"}>
      <span class="avatar">${avatarSvg(model)}</span>
      <span class="member-text">
        <span class="title">${escapeHtml(p.title)}</span>
        <span class="meta">${escapeHtml(model.name)} · ${escapeHtml(tokenizerLabel(model))}</span>
        <span class="meta">${escapeHtml(facts || model.description)}</span>
      </span>
    </button>`;
}

function selectFamily(familyId, modelId) {
  const family = FAMILIES.find((f) => f.id === familyId) ?? FAMILIES[0];
  const members = membersOf(family.id);
  const info = FAMILY_INFO[family.id];
  state.family = family;
  $("families").querySelectorAll(".family-card").forEach((el) => el.setAttribute("aria-selected", String(el.dataset.family === family.id)));
  $("family").innerHTML = `
    <h2>${escapeHtml(family.title)}</h2>
    <p class="family-intro">${escapeHtml(info?.intro ?? family.tagline)}</p>
    ${info ? `<div class="kind-facts-row">${info.kinds.map(kindFacts).join("")}</div>
      <p class="family-catch"><b>The catch:</b> ${escapeHtml(info.catch)}</p>` : ""}
    <h3>The encoders in this family</h3>
    <div class="members">${members.map(memberCard).join("")}</div>`;
  $("family").querySelectorAll(".member").forEach((el) => el.addEventListener("click", () => selectModel(el.dataset.id, true)));
  const target = members.find((m) => m.id === modelId && m.available) ?? members.find((m) => m.available);
  if (target) selectModel(target.id, false);
}

// ---- one encoder ---------------------------------------------------------------------------------

function selectModel(id, scroll) {
  const model = byId(id);
  if (!model?.available) return;
  state.selected = model;
  history.replaceState(null, "", `#${state.family.id}/${model.id}`);
  $("family").querySelectorAll(".member").forEach((el) => el.setAttribute("aria-current", String(el.dataset.id === model.id)));
  renderDetail(model);
  if (scroll) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

function facts(model) {
  const t = model.training ?? {};
  const rows = [];
  if (model.dataset?.chars) rows.push(["Training text", `${formatChars(model.dataset.chars)} characters`]);
  if (t.params) rows.push(["Model size", `${formatParams(t.params)} parameters`]);
  if (model.context_tokens) rows.push(["Context", `the last ${model.context_tokens} symbols (trained on ${t.block_size ?? "more"})`]);
  else if (t.block_size) rows.push(["Context", `the last ${t.block_size} symbols`]);
  if (t.val_bits_per_char) rows.push(["Held-out cost", `${t.val_bits_per_char.toFixed(2)} bits/char on unseen text of its kind`]);
  return rows.length ? `<dl class="facts">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${escapeHtml(v)}</dd></div>`).join("")}</dl>` : "";
}

function trainedOn(model) {
  if (model.kind === "uniform") {
    return `<p>Nothing: any text costs log₂ ${model.vocab_size} = <b>${Math.log2(model.vocab_size).toFixed(2)} bits per symbol</b>.</p>`;
  }
  const d = model.dataset;
  if (!d) return `<p class="muted">Not recorded for this model.</p>${facts(model)}`;
  const name = d.url ? `<a href="${escapeHtml(d.url)}" target="_blank" rel="noopener">${escapeHtml(d.name)}</a>` : escapeHtml(d.name);
  return `<p><b>${name}</b>: ${escapeHtml(d.about)}.</p>${facts(model)}`;
}

function renderDetail(model) {
  const p = persona(model);
  const kind = KINDS[kindOf(model)] ?? KINDS.char;
  $("detail").innerHTML = `
    <header class="detail-head">
      <span class="avatar big">${avatarSvg(model)}</span>
      <div>
        <h2>${escapeHtml(p.title)}</h2>
        <p class="sub">${escapeHtml(model.name)} · ${escapeHtml(tokenizerLabel(model))} · ${escapeHtml(familyOf(model).title)} family</p>
        <p class="desc">${escapeHtml(model.description)}</p>
      </div>
    </header>
    <section><h3>Trained on</h3>${trainedOn(model)}</section>
    <section>
      <h3>Its symbols <span class="count">${model.vocab_size.toLocaleString("en-US")}</span></h3>
      <p>One symbol is <b>${escapeHtml(kind.symbol)}</b>. Any text? ${escapeHtml(kind.anyText)}.</p>
      <div id="symbols" class="symbol-grid ${model.tokenizer === "bytes" ? "bytes" : ""}"><span class="muted">loading…</span></div>
      <p id="symbols-note" class="muted small"></p>
    </section>
    <section>
      <h3>Typical sentences</h3>
      <div class="example-list">${model.examples.map((text, i) => exampleCard(model, text, i)).join("") ||
        '<p class="muted">none recorded</p>'}</div>
    </section>`;
  loadSymbols(model);
  model.examples.forEach((text, i) => loadExample(model, text, i));
}

function exampleCard(model, text, i) {
  const partner = COMPARE_PARTNERS.map(byId).find((m) => m?.available && m.id !== model.id && canEncode(m, text));
  const encodeUrl = `encode.html?${new URLSearchParams({ model: model.id, text })}`;
  const compareUrl = partner ? `compare.html?${new URLSearchParams({ models: `${model.id},${partner.id}`, text })}` : "";
  return `<article class="example-card">
      <div class="example-text">${escapeHtml(text)}</div>
      <div class="example-foot">
        <span class="example-stats" id="stats-${i}">encoding…</span>
        <span class="example-links"><a href="${escapeHtml(encodeUrl)}">watch it encode ▸</a>${partner
          ? `<a href="${escapeHtml(compareUrl)}">compare with the ${escapeHtml(persona(partner).title)} ▸</a>` : ""}</span>
      </div>
    </article>`;
}

async function loadSymbols(model) {
  try {
    if (!state.symbols.has(model.id)) state.symbols.set(model.id, await api.getSymbols(model.id));
    const data = state.symbols.get(model.id);
    if (state.selected !== model) return;
    $("symbols").innerHTML = data.symbols.map((s) =>
      `<span class="sym${s.label.startsWith("\\x") ? " raw" : ""}" title="symbol ${s.id}">${escapeHtml(chipLabel(s.label))}</span>`).join("");
    $("symbols-note").textContent = data.sampled ? `Showing ${data.note}.` :
      model.tokenizer === "bytes" ? "Printable ASCII bytes show as their character, the rest as \\xNN." : "";
  } catch (error) {
    if (state.selected === model) $("symbols").textContent = error.message;
  }
}

async function loadExample(model, text, i) {
  try {
    const key = `${model.id}\u0000${text}`;
    if (!state.costs.has(key)) state.costs.set(key, (await api.encode(model.id, text)).stats);
    if (state.selected !== model) return;
    const s = state.costs.get(key);
    $(`stats-${i}`).innerHTML = `<b>${s.payload_bits} bits</b> · <b>${s.bpc.toFixed(2)}</b> bits/char ` +
      `<span class="muted">(plain text: ${(s.utf8_bits / Math.max(1, s.chars)).toFixed(0)})</span>`;
  } catch (error) {
    if (state.selected === model) $(`stats-${i}`).textContent = error.message;
  }
}

// ---- start ---------------------------------------------------------------------------------------

/** "#family/model", "#family" or (older links) "#model". */
function fromHash() {
  const [first, second] = decodeURIComponent(location.hash.slice(1)).split("/");
  if (FAMILIES.some((f) => f.id === first)) return [first, second];
  const model = byId(first);
  return model ? [persona(model).family, model.id] : ["characters", "shakespeare_char"];
}

async function init() {
  initGlossary();
  try {
    const { models } = await api.getModels();
    state.models = models;
    renderFamilyCards();
    selectFamily(...fromHash());
  } catch (error) {
    $("family").textContent = `could not reach the API: ${error.message}`;
  }
}

window.addEventListener("hashchange", () => {
  const [family, model] = fromHash();
  if (family !== state.family?.id || model !== state.selected?.id) selectFamily(family, model);
});

init();
