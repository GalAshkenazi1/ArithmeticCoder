# Study 03 - stats (generated)

Accuracy check: real payload minus ideal bits per message: mean -0.90, min -8.70, max +0.96 bits over 436 messages.

## Cost by character class (bits/char, all 6 kinds of text pooled)

| class | Wiki-GPT | TinyStories-GPT | Web-GPT | Python-GPT | Uniform ASCII |
|---|---:|---:|---:|---:|---:|
| lowercase | 2.64 | 3.28 | 2.45 | 3.23 | 6.58 |
| Uppercase | 6.25 | 9.43 | 5.50 | 7.00 | 6.58 |
| digit | 3.92 | 10.73 | 4.13 | 5.94 | 6.58 |
| space | 1.25 | 2.54 | 0.84 | 1.54 | 6.58 |
| newline | 7.33 | 8.39 | 8.17 | 1.92 | 6.65 |
| punctuation | 7.17 | 6.54 | 5.68 | 5.99 | 6.58 |
| brackets & symbols | 11.93 | 15.06 | 9.20 | 2.72 | 6.58 |

## Distribution of per-character cost

| model | text | mean | median | p95 | free (<0.1 bit) | >8 bits | bits in costliest 10% of chars |
|---|---|---:|---:|---:|---:|---:|---:|
| Shakespeare-GPT | Shakespeare | 2.67 | 2.42 | 6.42 | 7% | 1.7% | 26% |
| English-GPT | Gutenberg novels | 2.57 | 2.15 | 6.80 | 7% | 2.7% | 29% |
| Wiki-GPT | Wikipedia | 1.91 | 1.00 | 6.23 | 27% | 1.5% | 35% |
| TinyStories-GPT | TinyStories | 1.07 | 0.11 | 4.91 | 49% | 0.7% | 52% |
| Web-GPT | Web (C4) | 2.25 | 1.53 | 6.79 | 21% | 2.9% | 32% |
| Python-GPT | Python code | 1.36 | 0.14 | 6.24 | 48% | 2.4% | 50% |
| Wiki-GPT | Web (C4) | 2.52 | 1.75 | 7.56 | 19% | 4.1% | 33% |
| TinyStories-GPT | Web (C4) | 3.89 | 2.74 | 12.68 | 17% | 15.7% | 33% |
| Python-GPT | Web (C4) | 3.56 | 2.69 | 10.25 | 10% | 11.8% | 31% |
| Uniform ASCII | Web (C4) | 6.58 | 6.58 | 6.58 | 0% | 0.0% | 10% |

## Overconfidence: TinyStories-GPT on Python code

- mean 7.01 bits/char vs uniform 6.58
- 50.1% of characters cost more than uniform; they carry 81% of all bits
- worst: 16.0 bits for '.' after 'from '

## Agreement (Spearman correlation of per-character cost, all shared text)

| | Wiki-GPT | TinyStories-GPT | Web-GPT | Python-GPT |
|---|---:|---:|---:|---:|
| Wiki-GPT | 1.00 | 0.65 | 0.89 | 0.52 |
| TinyStories-GPT | 0.65 | 1.00 | 0.66 | 0.34 |
| Web-GPT | 0.89 | 0.66 | 1.00 | 0.58 |
| Python-GPT | 0.52 | 0.34 | 0.58 | 1.00 |

Sentence in where_models_disagree.png: 'Continuing a theme of his presidency, in 2006 Mosley called for Formula '
