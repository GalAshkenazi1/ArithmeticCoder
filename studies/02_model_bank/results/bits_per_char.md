# Bits per character: every model on every kind of text

12 held-out snippets of ~250 chars per corpus (validation split, never trained on), each encoded as one message with the real coder. Lower is better; **bold** = best for that text; '-' = the model's vocabulary can't encode that text (digits, brackets, ...).

| model | Shakespeare | Gutenberg novels | Wikipedia | TinyStories | Web (C4) | Python code |
|---|---:|---:|---:|---:|---:|---:|
| English-GPT | 3.36 | 2.57 | - | - | - | - |
| Python-GPT | 3.86 | 3.37 | 3.63 | 3.37 | 3.55 | **1.36** |
| Shakespeare-GPT | **2.67** | 2.96 | - | - | - | - |
| TinyStories-GPT | 4.10 | 2.95 | 3.98 | **1.06** | 3.89 | 7.01 |
| Web-GPT | 3.06 | **2.42** | 2.26 | 2.12 | **2.24** | 3.63 |
| Wiki-GPT | 3.35 | 2.69 | **1.91** | 2.39 | 2.51 | 4.83 |
| Uniform ASCII | 6.58 | 6.58 | 6.58 | 6.58 | 6.58 | 6.58 |
