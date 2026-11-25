// How each model is presented as an "encoder": a persona name and avatar, a colour, and its family.
// Unknown models fall back to "<name> Encoder" in the family their tokenizer suggests, so new
// models in the bank show up automatically. (Models marked "showcase": false in model.json, the
// ones redundant next to another, never reach the frontend.)

import { drawAvatar } from "./avatars.js";

export const FAMILIES = [
  { id: "characters", title: "Characters", tagline: "one symbol per character, from a fixed alphabet" },
  { id: "bytes-words", title: "Bytes and words", tagline: "any text: UTF-8 bytes, or whole words with a byte fallback" },
  { id: "pretrained", title: "Pretrained", tagline: "a big model trained by someone else: GPT-2" },
  { id: "baselines", title: "Baselines", tagline: "no model at all: every symbol equally likely" },
];

const PERSONAS = {
  shakespeare_char: { title: "Shakespearian Encoder", color: "#9085e9", family: "characters", avatar: "shakespeare" },
  english_char: { title: "Victorian Novelist Encoder", color: "#d95926", family: "characters", avatar: "victorian" },
  wiki_small: { title: "Encyclopedia Encoder", color: "#199e70", family: "characters", avatar: "scholar" },
  stories_small: { title: "Storyteller Encoder", color: "#c98500", family: "characters", avatar: "storyteller" },
  python_small: { title: "Python Encoder", color: "#0ca30c", family: "characters", avatar: "geek" },
  web_bytes: { title: "Web Byte Encoder", color: "#3987e5", family: "bytes-words", avatar: "pixel" },
  web_words: { title: "Web Word Encoder", color: "#e66767", family: "bytes-words", avatar: "reporter" },
  gpt2: { title: "GPT-2 Encoder", color: "#3987e5", family: "pretrained", avatar: "robot" },
  uniform_bytes: { title: "No-Model Byte Encoder", color: "#898781", family: "baselines", avatar: "coin" },
  uniform_ascii: { title: "No-Model ASCII Encoder", color: "#898781", family: "baselines", avatar: "die6" },
};

const ORDER = Object.keys(PERSONAS);

/** Models in presentation order: the personas above first (in that order), then the rest by id. */
export function sortModels(models) {
  const rank = (m) => (ORDER.includes(m.id) ? ORDER.indexOf(m.id) : ORDER.length);
  return [...models].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
}

/** The family of a model the personas don't know, from its tokenizer. */
function guessFamily(model) {
  if (model.kind === "uniform") return "baselines";
  return { char: "characters", bytes: "bytes-words", words: "bytes-words", gpt2: "pretrained" }[model.tokenizer] ?? "characters";
}

export function persona(model) {
  return PERSONAS[model.id] ?? { title: `${model.name} Encoder`, color: "#9085e9", family: guessFamily(model), avatar: "person" };
}

export const familyOf = (model) => FAMILIES.find((f) => f.id === persona(model).family) ?? FAMILIES[0];

/** "65 characters", "UTF-8 bytes", "4,352 words + bytes", "GPT-2 BPE, 50,257 tokens" */
export function tokenizerLabel(model) {
  const n = model.vocab_size.toLocaleString("en-US");
  return { char: `${n} characters`, bytes: "UTF-8 bytes", words: `${n} words + bytes`,
    gpt2: `BPE, ${n} tokens` }[model.tokenizer] ?? `${n} symbols`;
}

/** The encoder's avatar; color overrides its own (e.g. a compare slot's series colour). */
export function avatarSvg(model, color) {
  const p = persona(model);
  return drawAvatar(p.avatar, color ?? p.color);
}
