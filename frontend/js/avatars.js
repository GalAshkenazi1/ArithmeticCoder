// A character for each encoder, drawn as a small SVG (viewBox 40 x 40, clipped to a circle by CSS:
// .avatar has border-radius 50% and overflow hidden). Each drawing is one of the AVATARS below;
// encoders.js picks one per model.

const SKIN = "#f1c7a1";
const SKIN_DARK = "#d9a77c";
const INK = "#1b1f2a";

const body = (fill) => `<path d="M4.5 41 C5.5 31.5 12 27.4 20 27.4 C28 27.4 34.5 31.5 35.5 41 Z" fill="${fill}"/>`;
const neck = `<rect x="17.5" y="21.5" width="5" height="7" rx="1.6" fill="${SKIN_DARK}"/>`;
const head = `<circle cx="20" cy="17" r="7.2" fill="${SKIN}"/>`;
const eyes = (y = 16.8) => `<circle cx="17.3" cy="${y}" r="0.95" fill="${INK}"/><circle cx="22.7" cy="${y}" r="0.95" fill="${INK}"/>`;
const smile = (y = 20.4) => `<path d="M17.7 ${y} Q20 ${y + 1.9} 22.3 ${y}" fill="none" stroke="${INK}" stroke-width="0.9" stroke-linecap="round"/>`;
const person = (bodyFill, extra = "") => body(bodyFill) + neck + head + extra;

/** Pixel art for the byte encoders: one string per row of a 16 x 16 grid (2.5 px cells). */
function pixels(rows, colors) {
  return rows.map((row, y) => [...row].map((c, x) => (colors[c]
    ? `<rect x="${x * 2.5}" y="${y * 2.5}" width="2.55" height="2.55" fill="${colors[c]}"/>` : "")).join("")).join("");
}

const PIXEL_PERSON = [
  "................",
  "................",
  ".....hhhhhh.....",
  "....hhhhhhhh....",
  "....hssssssh....",
  "....ssssssss....",
  "....sesssses....",
  "....ssssssss....",
  "....ssmmmmss....",
  ".....ssssss.....",
  "......nnnn......",
  "...bbbbbbbbbb...",
  "..bbbbbbbbbbbb..",
  ".bbbbbbbbbbbbbb.",
  ".bbbbwbbbbwbbbb.",
  "bbbbbbbbbbbbbbbb",
];
const PIXEL_SCHOLAR = [
  "................",
  "..kkkkkkkkkkkk..",
  "....kkkkkkkk.t..",
  "....hhhhhhhh.t..",
  "....hssssssh.t..",
  "....ssssssss....",
  "....gggssggg....",
  "....gegssgeg....",
  "....gggssggg....",
  "....ssmmmmss....",
  ".....ssssss.....",
  "...bbbbnnbbbb...",
  "..bbbbbbbbbbbb..",
  ".bbbbbbbbbbbbbb.",
  ".bbbbbbbbbbbbbb.",
  "bbbbbbbbbbbbbbbb",
];
const PIXEL_COLORS = { h: "#3a2a1e", s: SKIN, n: SKIN_DARK, e: INK, m: "#b04a5a", w: "#9cc3f5", k: "#1d2130", t: "#e0b44a", g: "#aab4c4" };

const die = (pips) => `<g transform="rotate(-12 20 20)">
    <rect x="10" y="10" width="20" height="20" rx="4.6" fill="#efece6" stroke="#b8b2a6" stroke-width="0.8"/>
    ${pips.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="1.9" fill="${INK}"/>`).join("")}
  </g>`;

export const AVATARS = {
  // Shakespeare: high forehead, hair at the sides, moustache and goatee, white ruff, gold earring
  shakespeare: () => person("#4a3426", `
    <ellipse cx="20" cy="27.4" rx="8.8" ry="3.1" fill="#f4efe2" stroke="#cfc6b2" stroke-width="0.6"/>
    ${[13.5, 15.5, 17.5, 19.5, 21.5, 23.5, 25.5].map((x) => `<line x1="${x}" y1="25.6" x2="${x + 0.4}" y2="29.2" stroke="#d6ccb6" stroke-width="0.5"/>`).join("")}
    <path d="M12.9 14.5 C12 19 12.4 23.5 15.2 25.6 C14.7 22 14.9 18.5 15.7 15.2 Z" fill="#6b4a2e"/>
    <path d="M27.1 14.5 C28 19 27.6 23.5 24.8 25.6 C25.3 22 25.1 18.5 24.3 15.2 Z" fill="#6b4a2e"/>
    <path d="M14 13.2 C14.8 11.4 16 10.6 17.2 10.4" fill="none" stroke="#6b4a2e" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M26 13.2 C25.2 11.4 24 10.6 22.8 10.4" fill="none" stroke="#6b4a2e" stroke-width="1.2" stroke-linecap="round"/>
    ${eyes(16.6)}
    <path d="M20 17.6 L19.3 19.6 L20.6 19.6" fill="none" stroke="#c48d66" stroke-width="0.7" stroke-linejoin="round"/>
    <path d="M16.8 21.4 Q18.6 20.1 20 21 Q21.4 20.1 23.2 21.4 Q21.2 21.8 20 21.4 Q18.8 21.8 16.8 21.4 Z" fill="#6b4a2e"/>
    <path d="M18.7 22.4 Q20 22 21.3 22.4 L20 25.2 Z" fill="#6b4a2e"/>
    <circle cx="12.8" cy="20" r="0.9" fill="none" stroke="#e0b44a" stroke-width="0.7"/>`),

  // Victorian novelist: top hat, mutton chops, big moustache, cravat
  victorian: () => person("#232a38", `
    <path d="M16.4 27.6 L20 33.2 L23.6 27.6 Z" fill="#efe9dc"/>
    <path d="M17.2 29 L20 30.4 L17.2 31.8 Z M22.8 29 L20 30.4 L22.8 31.8 Z" fill="#8f2d3a"/><circle cx="20" cy="30.4" r="0.9" fill="#6d2230"/>
    <path d="M12.9 15.5 C12.7 20 14 23 16.7 23.9 L16.3 18.6 Z" fill="#7a5a3c"/>
    <path d="M27.1 15.5 C27.3 20 26 23 23.3 23.9 L23.7 18.6 Z" fill="#7a5a3c"/>
    ${eyes(16.6)}
    <path d="M15.7 21.1 Q18 19.3 20 20.6 Q22 19.3 24.3 21.1 Q22.4 22 20 21.3 Q17.6 22 15.7 21.1 Z" fill="#7a5a3c"/>
    <rect x="10.4" y="9.6" width="19.2" height="2.3" rx="1.15" fill="#15161b"/>
    <rect x="13.4" y="0.6" width="13.2" height="9.8" rx="1" fill="#1d1e24"/>
    <rect x="13.4" y="7.4" width="13.2" height="1.8" fill="#6d2a33"/>`),

  // Encyclopedia: a scholar with round glasses and a mortarboard
  scholar: () => person("#2b3a67", `
    <path d="M16.6 27.6 L20 31.5 L23.4 27.6 Z" fill="#efe9dc"/>
    <path d="M12.9 16 C12.8 11 16.2 9.6 20 9.6 C23.8 9.6 27.2 11 27.1 16 C25 13.4 22.2 12.8 20 12.9 C17.8 12.8 15 13.4 12.9 16 Z" fill="#5a3d28"/>
    <circle cx="17.2" cy="17" r="2.25" fill="rgba(200,230,255,0.25)" stroke="#262a33" stroke-width="0.9"/>
    <circle cx="22.8" cy="17" r="2.25" fill="rgba(200,230,255,0.25)" stroke="#262a33" stroke-width="0.9"/>
    <line x1="19.45" y1="16.8" x2="20.55" y2="16.8" stroke="#262a33" stroke-width="0.8"/>
    <circle cx="17.2" cy="17" r="0.8" fill="${INK}"/><circle cx="22.8" cy="17" r="0.8" fill="${INK}"/>
    ${smile(20.8)}
    <path d="M14.2 10.5 L25.8 10.5 L25.2 13.1 L14.8 13.1 Z" fill="#1b1f2a"/>
    <polygon points="7.4,9.2 20,4.6 32.6,9.2 20,13.6" fill="#252a3d" stroke="#3a4157" stroke-width="0.5"/>
    <path d="M20 9 L29.6 10.3 L29.6 15.6" stroke="#e0b44a" stroke-width="0.9" fill="none"/>
    <rect x="28.7" y="15.2" width="1.8" height="3.1" rx="0.6" fill="#e0b44a"/>`),

  // Storyteller: a grandmother with a bun, half-moon glasses and an open picture book
  storyteller: () => person("#a8577a", `
    <path d="M12.8 17.6 C12.1 10.6 16 8.9 20 8.9 C24 8.9 27.9 10.6 27.2 17.6 C26 13.6 23.4 12.6 20 12.7 C16.6 12.6 14 13.6 12.8 17.6 Z" fill="#d9d6d0"/>
    <circle cx="20" cy="7.8" r="3" fill="#d9d6d0"/>
    ${eyes(16.9)}
    <path d="M15.4 17.6 Q17.3 19.4 19.2 17.6 M20.8 17.6 Q22.7 19.4 24.6 17.6" fill="none" stroke="#6b5a4a" stroke-width="0.8"/>
    <circle cx="15.9" cy="20" r="1.2" fill="#f19a9a" fill-opacity="0.65"/><circle cx="24.1" cy="20" r="1.2" fill="#f19a9a" fill-opacity="0.65"/>
    ${smile(20.6)}
    <path d="M8.5 31 L20 33.2 L31.5 31 L31.5 40 L20 41.6 L8.5 40 Z" fill="#f6f1e4" stroke="#b9ad92" stroke-width="0.6"/>
    <line x1="20" y1="33.2" x2="20" y2="41.6" stroke="#b9ad92" stroke-width="0.7"/>
    <path d="M11 33.6 L17.6 34.8 M11 35.8 L17.6 37 M22.4 34.8 L29 33.6 M22.4 37 L29 35.8" stroke="#c9bfa8" stroke-width="0.6"/>
    <circle cx="25.6" cy="37.6" r="1.3" fill="#e66767" fill-opacity="0.8"/>`),

  // Web: a streamer with a headset
  web: () => person("#c64b78", `
    <path d="M12.8 16 C12.5 10.6 16 8.7 20.5 8.9 C24.5 9.1 27.6 11 27.2 16 C25.5 12.9 22 12.1 18.5 12.7 C16 13.1 14 14.3 12.8 16 Z" fill="#2b2320"/>
    <path d="M11.7 18 C11.1 9.6 15 6.9 20 6.9 C25 6.9 28.9 9.6 28.3 18" fill="none" stroke="#2d3340" stroke-width="2"/>
    <rect x="10" y="15.3" width="3.7" height="6.2" rx="1.6" fill="#3a4152"/>
    <rect x="26.3" y="15.3" width="3.7" height="6.2" rx="1.6" fill="#3a4152"/>
    <path d="M11.9 21.2 C12.6 24.1 15.1 24.7 17.6 23.5" fill="none" stroke="#2d3340" stroke-width="1"/>
    <circle cx="17.8" cy="23.4" r="0.95" fill="#2d3340"/>
    ${eyes(16.9)}${smile(20.3)}`),

  // Python: a geek in a hoodie, spiky hair, thick glasses, laptop with the Python colours
  geek: () => person("#2e4a3a", `
    <path d="M16 27.8 L17 33 M24 27.8 L23 33" stroke="#cfd8cf" stroke-width="0.7"/>
    <path d="M12.6 15.6 L12.3 11.6 L14.6 12.3 L14.8 8.9 L17.2 10.7 L18.6 7.7 L20.4 10.3 L22.4 7.9 L23.4 10.9 L26 9.5 L25.8 12.5 L27.7 12.7 L27.4 15.6 C25 12.9 22 12.5 20 12.7 C17.6 12.5 14.8 13.1 12.6 15.6 Z" fill="#3b2a1f"/>
    <rect x="14.1" y="15" width="5.1" height="3.9" rx="1" fill="rgba(180,220,255,0.3)" stroke="#111" stroke-width="1.3"/>
    <rect x="20.8" y="15" width="5.1" height="3.9" rx="1" fill="rgba(180,220,255,0.3)" stroke="#111" stroke-width="1.3"/>
    <line x1="19.2" y1="16.4" x2="20.8" y2="16.4" stroke="#111" stroke-width="1.1"/>
    <circle cx="16.6" cy="17" r="0.8" fill="${INK}"/><circle cx="23.4" cy="17" r="0.8" fill="${INK}"/>
    <path d="M17.6 20.8 Q20 23 22.4 20.8 Z" fill="#fff" stroke="${INK}" stroke-width="0.7" stroke-linejoin="round"/>
    <rect x="9.6" y="29.6" width="20.8" height="12" rx="1.6" fill="#b8c0cc" stroke="#8d96a5" stroke-width="0.6"/>
    <path d="M18.6 32.4 h2.2 a1.4 1.4 0 0 1 1.4 1.4 v1.2 h-3.6 a1.4 1.4 0 0 1 0 -2.6 Z" fill="#3776ab"/>
    <path d="M21.4 37.8 h-2.2 a1.4 1.4 0 0 1 -1.4 -1.4 v-1.2 h3.6 a1.4 1.4 0 0 1 0 2.6 Z" fill="#ffd43b"/>`),

  // Byte encoders: pixel people (made of bytes)
  pixel: () => pixels(PIXEL_PERSON, { ...PIXEL_COLORS, b: "#3987e5" }),
  pixelScholar: () => pixels(PIXEL_SCHOLAR, { ...PIXEL_COLORS, b: "#199e70" }),

  // Web words: a reporter in a fedora with a press card
  reporter: () => person("#b48a58", `
    <path d="M16.6 27.6 L20 32.4 L23.4 27.6 Z" fill="#efe9dc"/>
    <path d="M19.2 28.4 L20.8 28.4 L21.4 34 L20 35.6 L18.6 34 Z" fill="#7a2730"/>
    <path d="M14.6 28.4 L18.4 34.6 L16.2 28 Z M25.4 28.4 L21.6 34.6 L23.8 28 Z" fill="#9a7445"/>
    ${eyes(16.9)}${smile(20.4)}
    <ellipse cx="20" cy="11.3" rx="11.4" ry="2.2" fill="#4a4540"/>
    <path d="M13.4 11.2 C13.4 6.4 15.5 4.6 20 4.6 C24.5 4.6 26.6 6.4 26.6 11.2 Z" fill="#57514a"/>
    <path d="M17.4 5.7 Q20 7.5 22.6 5.7" stroke="#3f3a34" stroke-width="0.8" fill="none"/>
    <rect x="13.4" y="8.7" width="13.2" height="1.9" fill="#2a2622"/>
    <g transform="rotate(9 24.2 7.4)"><rect x="22.3" y="5.8" width="3.9" height="3" fill="#f4f0e6"/>
      <line x1="22.9" y1="6.9" x2="25.6" y2="6.9" stroke="#7a2730" stroke-width="0.5"/><line x1="22.9" y1="7.9" x2="25" y2="7.9" stroke="#8d96a5" stroke-width="0.4"/></g>`),

  // GPT-2: a robot
  robot: () => `${body("#6f7a8e")}
    <rect x="17.3" y="21.5" width="5.4" height="7" rx="1" fill="#59647a"/>
    <line x1="20" y1="7.2" x2="20" y2="3.6" stroke="#8b95a7" stroke-width="1.2"/><circle cx="20" cy="3" r="1.6" fill="#3987e5"/>
    <rect x="9.2" y="12.6" width="2.3" height="5.2" rx="0.8" fill="#8b95a7"/><rect x="28.5" y="12.6" width="2.3" height="5.2" rx="0.8" fill="#8b95a7"/>
    <rect x="11" y="7" width="18" height="16.2" rx="4.2" fill="#c9d1dd" stroke="#8b95a7" stroke-width="0.8"/>
    <rect x="13.2" y="10.8" width="13.6" height="6.2" rx="3.1" fill="#1b2433"/>
    <circle cx="16.9" cy="13.9" r="1.6" fill="#7dd3fc"/><circle cx="23.1" cy="13.9" r="1.6" fill="#7dd3fc"/>
    <rect x="16" y="18.8" width="8" height="2.4" rx="1.1" fill="#8b95a7"/>
    <path d="M18 18.9 v2.2 M20 18.9 v2.2 M22 18.9 v2.2" stroke="#c9d1dd" stroke-width="0.6"/>
    <rect x="15.4" y="31" width="9.2" height="5.4" rx="1.4" fill="#59647a"/><circle cx="18" cy="33.7" r="1.1" fill="#7dd3fc"/><circle cx="22" cy="33.7" r="1.1" fill="#e66767"/>`,

  // baselines: chance, not a model
  die5: () => die([[15, 15], [25, 15], [20, 20], [15, 25], [25, 25]]),
  die6: () => die([[15, 14.6], [25, 14.6], [15, 20], [25, 20], [15, 25.4], [25, 25.4]]),
  coin: () => `<circle cx="20" cy="20" r="11.2" fill="#e0b44a" stroke="#b8862a" stroke-width="1.2"/>
    <circle cx="20" cy="20" r="8.7" fill="none" stroke="#b8862a" stroke-width="0.7"/>
    <text x="20" y="23.9" text-anchor="middle" font-size="10.5" font-weight="700" font-family="ui-monospace, Consolas, monospace" fill="#7a5615">01</text>`,

  // fallback for models without a character: a plain silhouette
  person: (color) => `<circle cx="20" cy="16" r="6.5" fill="${color}"/><path d="M8.5 33c1.8-6.2 6.2-9.3 11.5-9.3S29.7 26.8 31.5 33" fill="${color}"/>`,
};

/** The full avatar: a tinted disc, the character, and a ring in the encoder's colour. */
export function drawAvatar(name, color) {
  const art = (AVATARS[name] ?? AVATARS.person)(color);
  return `<svg viewBox="0 0 40 40" aria-hidden="true">
    <circle cx="20" cy="20" r="20" fill="${color}" fill-opacity="0.22"/>${art}
    <circle cx="20" cy="20" r="19.2" fill="none" stroke="${color}" stroke-width="1.6"/>
  </svg>`;
}
