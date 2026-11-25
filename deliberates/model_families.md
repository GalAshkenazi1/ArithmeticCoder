# Characters, symbols and bits, and how the encoder families differ

Every encoder in the showcase is the same arithmetic coder with a different model in front of it.
What separates them is **what one symbol is** and **how well the model predicts it**. This note
explains the three units everything is measured in, then the four families.

All numbers below were measured with the showcase encoders.

## The three units

### Character: what you read

One character is one letter, digit, space or sign as a person sees it: `a`, `é`, `ש` and `👋` are
one character each. `Grüße aus Zürich! 👋` is 19 characters.

The text is stored as **bytes** (UTF-8). English letters take 1 byte; `é`, `ü`, `ß` and Hebrew
letters take 2; an emoji takes 4. So `Grüße aus Zürich! 👋` is 19 characters but 25 bytes. Plain
text costs 8 bits per byte: 8 bits per character for English, more for anything else (10.5 for
this text).

### Symbol: what the model predicts

The **tokenizer** cuts the text into symbols. At each step the model gives a probability to every
possible next symbol, and the coder narrows its interval to the chosen symbol's slice: one row of
the coding animation per symbol.

What one symbol is depends on the family. The same 37-character sentence, cut four ways:

| family | one symbol is | `Unbelievably, the weather was lovely!` | symbols |
|---|---|---|---:|
| Characters | a character | `U n b e l i e v a b l y , ␣ t h e ␣ w e a t h e r …` | 37 |
| Bytes | a UTF-8 byte | the same as characters (it's all ASCII) | 37 |
| Words | a known word, or a byte | `U n b e l i e v a b l y , ␣the ␣weather ␣was ␣lovely !` | 18 |
| GPT-2 | a token (word or word piece) | `Un bel iev ably , ␣the ␣weather ␣was ␣lovely !` | 10 |

(`␣` is a space. The word model doesn't know "Unbelievably", so it spells it out byte by byte.)

### Bit: what comes out

A bit is one binary digit of the output. The encoded message is a single binary fraction,
`0.1111011…`, and its digits are the bits that get sent.

**A symbol the model gave probability P costs −log₂ P bits.** The reason: the interval starts as
`[0, 1)`, and each bit of output pins it down by half. Choosing a symbol of probability P shrinks
the interval to P of its width, which is log₂(1/P) halvings.

| the model gave it | cost |
|---|---:|
| 1 in 2 (50%) | 1 bit |
| 1 in 4 | 2 bits |
| 1 in 256 (a byte, no knowledge) | 8 bits |
| 9 in 10 | 0.15 bits |
| 1 in 100 | 6.6 bits |
| 1 in 10,000 | 13.3 bits |

A rule of thumb: "1 in N" costs about log₂ N bits. A good guess is almost free, a surprise is
expensive.

**Costs are fractions, but bits come out whole.** The coder writes a bit only once the interval is
narrow enough to fix it, so bits arrive in bursts. That's why some rows in the animation say
"+0 bits" and others "+5 bits". The total is the sum of the costs, rounded up, within about
2 bits. "Word" with the Shakespearian Encoder:

| symbol | P | cost | bits written |
|---|---:|---:|---:|
| `W` | 5.9% | 4.08 | 4 |
| `o` | 4.4% | 4.50 | 5 |
| `r` | 23% | 2.09 | 0 |
| `d` | 43% | 1.23 | 3 |
| total | | 11.90 | **12** |

## Why the yardstick is bits per character

Bits per *symbol* would be misleading, because a symbol means something different in every
family. What you send is bits, and what you wrote is characters, so the fair comparison is bits
per character of the text. `To be, or not to be, that is the question:` (42 characters):

| encoder | symbols | bits | bits per symbol | **bits per char** |
|---|---:|---:|---:|---:|
| Shakespearian (characters) | 42 | 90 | 2.14 | **2.14** |
| Web Byte (bytes) | 42 | 84 | 2.00 | **2.00** |
| Web Word (words) | 13 | 87 | 6.69 | **2.07** |
| GPT-2 (tokens) | 13 | 52 | 4.00 | **1.24** |
| No-Model ASCII (baseline) | 42 | 274 | 6.52 | **6.52** |
| No-Model Byte (baseline) | 42 | 335 | 7.98 | **7.98** |
| plain UTF-8 | | 336 | | 8.00 |

**Fewer symbols doesn't mean fewer bits.** The word model uses a third as many symbols as the
Shakespearian one, yet almost the same bits: each word is a harder guess (6.7 bits each) than a
single letter. A bigger symbol packs in more information, so it costs more to predict.

Another example: GPT-2 encodes "Word" as one token, but it gives that token only a 1-in-10,000
chance with no context, so it costs 13 bits. That's more than the Shakespearian Encoder's 12 bits
for four separate letters.

## The four families

### Characters

One symbol per character, from a fixed alphabet of 65 characters (Shakespeare's) or 96
(printable ASCII). All five use the same small nanoGPT design, so **what they learned from is
their personality**:

| encoder | trained on | alphabet | size | held-out cost* |
|---|---|---:|---:|---:|
| Shakespearian | Tiny Shakespeare (plays) | 65 | 0.8M | 2.69 |
| Victorian Novelist | five Gutenberg novels | 65 | 0.8M | 2.51 |
| Encyclopedia | WikiText-2 (Wikipedia) | 96 | 3.2M | 2.05 |
| Storyteller | TinyStories (children's stories) | 96 | 3.2M | 1.11 |
| Python | the Python standard library | 96 | 3.2M | 1.50 |

\* bits per character on unseen text from *its own* corpus. These can't be compared across rows:
children's stories are simply more predictable than Wikipedia.

- **Each one is cheapest on its own kind of text.** On the Hamlet line, the Shakespearian Encoder
  needs 2.14 bits/char, the Encyclopedia 2.48, Python 2.88.
- **The bits go on word beginnings.** Once a model has seen how a word starts, the rest is mostly
  predictable. In study 04, the first letters of words were about a sixth of all characters but
  cost a third to a half of all bits.
- **The catch:** a character outside the alphabet can't be encoded at all. None of them can take
  `Grüße`.

### Bytes and words

Two ways to take *any* text, both trained on the same web text (C4).

- **Web Byte:** one symbol per UTF-8 byte (256 symbols). It is really a character model with a
  bigger alphabet: on English it costs the same (2.00 bits/char on the Hamlet line). Characters
  outside ASCII are 2–4 symbols each, and each has to be predicted. `Grüße aus Zürich! 👋` becomes
  25 symbols at 7.3 bits/char, barely under plain text's 10.5.
- **Web Word:** each of 4,096 common words (usually with its leading space, like `␣the`) is one
  symbol; anything else is spelled out in bytes. It pays for a known word once instead of letter
  by letter: 1.70 bits/char on the "Unbelievably" sentence, against 2.19 for bytes.
- **The catch:** words it doesn't know, names, numbers and even capitals fall back to bytes. "Word"
  at the start of a text isn't in its list, so it's spelled `W o r d`.

### Pretrained (GPT-2)

OpenAI's GPT-2 small: 124M parameters, trained on 40 GB of web text, with 50,257 tokens learned
by byte-pair encoding (common words are one token, rarer ones a few pieces; about 4 characters
per token in English). It wins everywhere: 1.24 bits/char on the Hamlet line, 1.43 on the
"Unbelievably" sentence, and 4.3 on the German-Hebrew-emoji text, where everything else is near
plain text.

**That's mostly size and data, not the tokenizer.** GPT-2 is about 40 times bigger than our models
and saw thousands of times more text. The catches: it's slow on a CPU (about 15 tokens a second),
it only sees the last 256 tokens, and its first token is expensive because there is no context
yet.

### Baselines (no model)

Every symbol gets the same probability, so the cost per symbol is fixed whatever you type:

- **No-Model ASCII:** 96 characters, log₂ 96 = 6.58 bits per character.
- **No-Model Byte:** 256 bytes, 8 bits per byte. That's exactly plain UTF-8, the dashed line in
  the charts.

They show what the arithmetic coder alone gives you. The gap from 8 to 6.58 is only the smaller
alphabet; everything below 6.58 is what a model knows about language.

## All four side by side

| | Characters | Bytes and words | Pretrained | Baselines |
|---|---|---|---|---|
| one symbol | a character | a byte / a word | a token | a character or byte |
| alphabet | 65 or 96 | 256 / 4,352 | 50,257 | 96 or 256 |
| any text? | no | yes | yes | byte version only |
| characters per symbol | 1 | ~1 / ~2 | ~4 | 1 |
| English, bits per char | 2–3 | ~2 | ~1.2–1.5 | 6.58 or 8 |
| speed | fast | fast | slow | instant |

## Where each idea shows up in the showcase

- **Encode page:**
  - Each row of the animation is one symbol.
  - The boxes under the line are the model's probabilities for every possible next symbol, and
    the chosen box's width is P.
  - "+N bits" is how many whole bits that symbol made the coder write.
  - The green dot is the shortest binary fraction inside the current interval: the bits so far.
- **Compare page:**
  - The bars are bits per character. A word's bar is as wide as the word.
  - The lines are the running total of bits.
  - Both are per character, so any two encoders line up.
- **Encoders page:** what each family's symbol is, and how each encoder cuts its typical
  sentences.

Three encoders were taken out of the showcase because another one already covers them:
- **Web Encoder:** the same web text as Web Byte, at the same cost, but it can't take Unicode.
- **Encyclopedia Byte Encoder:** the same Wikipedia text as the Encyclopedia Encoder, at the same
  cost.
- **65-character No-Model Encoder:** the same idea as No-Model ASCII, with a smaller alphabet.

They are still in `model_bank/` for the studies (`"showcase": false` in their `model.json`).
