# Multi-language identifier corpus — statistics

Union of **3,732,017** distinct ASCII identifiers across 6 ecosystems.

| Language | Distinct IDs | Mean len | Median len | Source |
|---|---:|---:|---:|---|
| ruby | 1,424,035 | 16.6 | 13 | RubyGems — 8,079 unpacked gems, 235,676 files |
| rust | 1,854,408 | 17.5 | 15 | crates.io — 2,500 crates, 64,650 .rs files |
| python | 561,160 | 13.7 | 12 | local CPython 3.13 stdlib + 286 dist-packages, 13,710 files |
| go | 272,584 | 12.0 | 9 | local Go 1.24 standard library, 7,115 files |
| javascript | 67,283 | 7.0 | 6 | local /usr/share/javascript, 2,786 files |
| perl | 42,306 | 8.6 | 8 | local Perl 5 module tree, 752 files |
| **sum (with overlap)** | **4,221,776** | | | |
| **union (deduplicated)** | **3,732,017** | | | |
| overlap removed | 489,759 | | | |

## Identifier grammar

Every token matches `^[A-Za-z_][A-Za-z0-9_]*$` (ASCII only): starts with a
letter or underscore, followed by letters, underscores or digits.
Validation: **0** violating tokens and **0** empty lines in both the union
and every per-language file.

## Per-language character and style notes

| Language | starts `_` | contains `_` | ends digit | ALL_CAPS | inner capitals |
|---|---:|---:|---:|---:|---:|
| ruby | 23,542 (1.7%) | 668,053 (46.9%) | 112,317 (7.9%) | 133,552 (9.4%) | 610,777 (42.9%) |
| rust | 34,231 (1.8%) | 983,713 (53.0%) | 356,352 (19.2%) | 308,548 (16.6%) | 822,893 (44.4%) |
| python | 57,384 (10.2%) | 319,451 (56.9%) | 52,961 (9.4%) | 41,561 (7.4%) | 146,981 (26.2%) |
| go | 2,906 (1.1%) | 58,420 (21.4%) | 68,560 (25.2%) | 58,347 (21.4%) | 161,327 (59.2%) |
| javascript | 452 (0.7%) | 835 (1.2%) | 32,646 (48.5%) | 11,697 (17.4%) | 25,272 (37.6%) |
| perl | 1,164 (2.8%) | 10,236 (24.2%) | 3,120 (7.4%) | 4,337 (10.3%) | 9,204 (21.8%) |


---


| Metric | Value |
|---|---|
| Distinct identifiers | 3,732,017 |
| Total characters | 63,628,978 |
| Mean length | 17.05 |
| Median length | 14 |
| Min length | 1 |
| Max length | 262,145 |
| Distinct characters | 63 |
| Starts with `_` | 112,487 (3.01%) |
| Contains `_` | 1,917,952 (51.39%) |
| Ends with a digit | 534,704 (14.33%) |
| Contains a digit | 901,672 (24.16%) |
| ALL_CAPS style | 488,509 (13.09%) |
| Contains inner capitals (camel/Pascal) | 1,623,866 (43.51%) |

## Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 5 |
| p25 | 9 |
| p50 | 14 |
| p75 | 21 |
| p90 | 30 |
| p95 | 37 |
| p99 | 64 |
| p99.9 | 122 |
| p99.99 | 550 |
| max | 262,145 |

## Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 1,408,344 | 37.74% |
| 17-24 | 853,752 | 22.88% |
| 25-32 | 336,086 | 9.01% |
| 33-48 | 221,589 | 5.94% |
| 49-64 | 45,602 | 1.22% |
| 65-96 | 22,292 | 0.60% |
| 97-128 | 8,410 | 0.23% |
| 129-256 | 2,009 | 0.05% |
| >256 | 816 | 0.02% |

## Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 5,392,095 | 8.47% |
| `_` | 4,231,725 | 6.65% |
| `t` | 3,789,385 | 5.96% |
| `a` | 3,252,588 | 5.11% |
| `r` | 2,903,212 | 4.56% |
| `i` | 2,851,068 | 4.48% |
| `s` | 2,748,144 | 4.32% |
| `n` | 2,639,414 | 4.15% |
| `o` | 2,638,794 | 4.15% |
| `c` | 1,912,510 | 3.01% |
| `l` | 1,880,976 | 2.96% |
| `d` | 1,766,466 | 2.78% |
| `p` | 1,362,201 | 2.14% |
| `u` | 1,307,170 | 2.05% |
| `m` | 1,206,336 | 1.90% |
| `0` | 1,133,895 | 1.78% |
| `E` | 1,059,049 | 1.66% |
| `A` | 981,092 | 1.54% |
| `f` | 965,144 | 1.52% |
| `g` | 955,921 | 1.50% |

## Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `x` | 344,297 | 9.23% |
| `t` | 198,430 | 5.32% |
| `s` | 184,206 | 4.94% |
| `c` | 163,155 | 4.37% |
| `p` | 128,184 | 3.43% |
| `a` | 117,043 | 3.14% |
| `r` | 113,454 | 3.04% |
| `S` | 112,904 | 3.03% |
| `_` | 112,487 | 3.01% |
| `g` | 105,623 | 2.83% |
| `i` | 102,963 | 2.76% |
| `d` | 101,686 | 2.72% |
| `f` | 96,350 | 2.58% |
| `m` | 93,291 | 2.50% |
| `C` | 91,809 | 2.46% |

## Notes

- 2,825 identifiers exceed 128 characters; the longest is 262,145 chars and is almost certainly an embedded blob (base64 font/source-map data) rather than a real identifier.
- Longest token begins: `x0000000000000000000000000000000000000000000000000000000000000000000000000000000...`
