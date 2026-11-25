# Study 05 - stats (generated)

## Bits per character (real payload)

| model | tokenizer | Web (C4) | Wikipedia | TinyStories | Unicode (web + multilingual) |
|---|---|---:|---:|---:|---:|
| Web-GPT | characters (96) | 2.24 | 2.26 | 2.12 | - |
| Web-Bytes | UTF-8 bytes (256) | 2.26 | 2.29 | 2.15 | 2.76 |
| Web-Words | words + bytes (4,352) | 2.11 | 2.06 | 1.83 | 2.86 |
| GPT-2 (124M) | GPT-2 BPE (50,257) | 1.46 | 1.26 | 1.11 | 1.80 |
| Uniform ASCII | characters, no model | 6.58 | 6.58 | 6.58 | - |
| Uniform Bytes | bytes, no model | 8.00 | 8.00 | 8.00 | 8.65 |
| Wiki-GPT | characters (96) | 2.51 | 1.91 | 2.39 | - |
| Wiki-Bytes | UTF-8 bytes (256) | 2.52 | 1.94 | 2.38 | 3.46 |

## Speed (web text, CPU)

| model | ms per char | chars per symbol |
|---|---:|---:|
| Web-GPT | 6.81 | 1.00 |
| Web-Bytes | 5.96 | 1.00 |
| Web-Words | 2.53 | 2.23 |
| GPT-2 (124M) | 16.35 | 4.58 |
| Uniform ASCII | 0.04 | 1.00 |
| Uniform Bytes | 0.05 | 1.00 |

## Running bits/char on 400-char web messages

| model | 10 chars | 50 | 100 | 380 |
|---|---:|---:|---:|---:|
| Web-GPT | 2.15 | 1.95 | 2.00 | 1.96 |
| Web-Bytes | 2.14 | 1.92 | 1.98 | 1.97 |
| Web-Words | 1.73 | 1.73 | 1.83 | 1.79 |
| GPT-2 (124M) | 1.42 | 1.30 | 1.31 | 1.19 |

## Web-Words: what the symbols are (share of symbols / share of bits)

| text | whole-word symbols | letters of unlisted words (spelled out) | spaces, punctuation, digits (single bytes) |
|---|---:|---:|---:|
| Web (C4) | 23% / 44% | 57% / 41% | 20% / 15% |
| Unicode (web + multilingual) | 23% / 34% | 49% / 50% | 28% / 17% |
