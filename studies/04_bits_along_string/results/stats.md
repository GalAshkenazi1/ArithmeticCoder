# Study 04 - stats (generated)

## Running real bits/char by message length (own kind of text)

| model | text | 10 chars | 20 chars | 50 chars | 100 chars | 200 chars | 400 chars | 1st char | first 10 | after 128 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Shakespeare-GPT | Shakespeare | 2.82 | 2.78 | 2.74 | 2.68 | 2.66 | 2.72 | 4.89 | 2.99 | 2.73 |
| English-GPT | Gutenberg novels | 2.91 | 2.66 | 2.63 | 2.55 | 2.61 | 2.63 | 4.99 | 2.96 | 2.67 |
| Wiki-GPT | Wikipedia | 2.01 | 2.10 | 2.11 | 2.07 | 2.08 | 2.06 | 4.13 | 2.08 | 2.02 |
| TinyStories-GPT | TinyStories | 1.30 | 1.13 | 1.02 | 1.04 | 1.05 | 1.01 | 3.97 | 1.36 | 0.96 |
| Web-GPT | Web (C4) | 2.59 | 2.27 | 2.08 | 2.08 | 2.06 | 2.07 | 4.45 | 2.68 | 2.06 |
| Python-GPT | Python code | 2.90 | 2.35 | 1.91 | 1.69 | 1.45 | 1.49 | 8.91 | 3.00 | 1.36 |

## Web-GPT on every kind of text (ideal bits)

| text | 1st char | first 10 chars | after 128 chars | 400-char message (real bits/char) |
|---|---:|---:|---:|---:|
| Shakespeare | 4.97 | 3.87 | 3.10 | 3.12 |
| Gutenberg novels | 8.15 | 2.90 | 2.41 | 2.40 |
| Wikipedia | 6.90 | 2.99 | 2.21 | 2.32 |
| TinyStories | 4.17 | 2.57 | 2.10 | 2.10 |
| Web (C4) | 4.45 | 2.68 | 2.06 | 2.07 |
| Python code | 8.65 | 4.72 | 3.49 | 3.57 |

## Cost by position inside a word (bits/char)

| model | 1st letter | 2nd letter | 3rd letter | 4th letter | 5th+ letter | space | newline | punctuation/other | share of bits on 1st letters | share of chars that are 1st letters |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Shakespeare-GPT | 4.34 | 2.34 | 2.66 | 2.58 | 3.07 | 0.77 | 0.83 | 4.29 | 30% | 19% |
| English-GPT | 4.35 | 2.27 | 2.45 | 2.53 | 2.74 | 0.73 | 2.17 | 5.09 | 31% | 19% |
| Wiki-GPT | 4.29 | 2.21 | 2.10 | 1.76 | 1.29 | 0.51 | 1.87 | 4.00 | 34% | 16% |
| TinyStories-GPT | 2.60 | 1.01 | 0.65 | 0.39 | 0.25 | 0.25 | 1.78 | 1.45 | 52% | 20% |
| Web-GPT | 4.36 | 2.18 | 2.21 | 1.67 | 1.13 | 0.57 | 1.52 | 4.64 | 36% | 17% |
| Python-GPT | 4.31 | 1.83 | 1.21 | 0.84 | 1.06 | 0.27 | 1.19 | 2.19 | 35% | 12% |

## Staircase example (first 64 chars of one TinyStories message)

| model | payload bits | characters that cost 0 extra bits |
|---|---:|---:|
| TinyStories-GPT | 66 | 39 of 64 |
| Web-GPT | 131 | 26 of 64 |
| Wiki-GPT | 126 | 29 of 64 |
| Uniform ASCII | 418 | 0 of 64 |
