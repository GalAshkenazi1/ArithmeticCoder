# Encoded length by model

100 Shakespeare-style sentences, 5,761 characters (mean 57.6 chars). Raw 8-bit text = 46,088 bits.

| model | mean bits | median bits | total bits | bits/char | % of raw | best on | round-trip ok | encode ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nanoGPT Shakespeare | 147.0 | 137 | 14,702 | 2.55 | 32% | 95 | 100/100 | 112 |
| nanoGPT English | 167.1 | 161 | 16,709 | 2.90 | 36% | 7 | 100/100 | 110 |
| Uniform | 346.0 | 326 | 34,601 | 6.01 | 75% | 0 | 100/100 | 1 |

- **best on**: number of sentences where that model gave the shortest encoding (ties count for each).
- **% of raw**: encoded size relative to 8 bits per character.

Figures: `bits_per_char.png`, `bits_vs_length.png`, `bpc_distribution.png`.
