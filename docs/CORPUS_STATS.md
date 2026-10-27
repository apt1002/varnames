# Corpus statistics — `RubyGems corpus`

| Metric | Value |
|---|---|
| Distinct identifiers | 710,477 |
| Total characters | 12,657,587 |
| Mean length | 17.82 |
| Median length | 15 |
| Min length | 1 |
| Max length | 264 |
| Distinct characters | 63 |
| Starts with `_` | 7,318 (1.03%) |
| Contains `_` | 477,991 (67.28%) |
| Ends with a digit | 17,273 (2.43%) |
| Contains a digit | 36,172 (5.09%) |
| ALL_CAPS style | 57,213 (8.05%) |
| Contains inner capitals (camel/Pascal) | 231,408 (32.57%) |

## Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 8 |
| p25 | 11 |
| p50 | 15 |
| p75 | 21 |
| p90 | 30 |
| p95 | 37 |
| p99 | 62 |
| p99.9 | 107 |
| p99.99 | 148 |
| max | 264 |

## Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 315,313 | 44.38% |
| 17-24 | 187,737 | 26.42% |
| 25-32 | 68,351 | 9.62% |
| 33-48 | 38,570 | 5.43% |
| 49-64 | 9,397 | 1.32% |
| 65-96 | 5,182 | 0.73% |
| 97-128 | 955 | 0.13% |
| 129-256 | 240 | 0.03% |
| >256 | 1 | 0.00% |

## Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 1,372,429 | 10.84% |
| `t` | 979,458 | 7.74% |
| `_` | 907,479 | 7.17% |
| `a` | 772,241 | 6.10% |
| `r` | 745,255 | 5.89% |
| `s` | 735,449 | 5.81% |
| `i` | 712,987 | 5.63% |
| `o` | 707,327 | 5.59% |
| `n` | 673,498 | 5.32% |
| `l` | 467,698 | 3.70% |
| `c` | 444,379 | 3.51% |
| `d` | 398,159 | 3.15% |
| `p` | 332,096 | 2.62% |
| `u` | 328,714 | 2.60% |
| `m` | 285,997 | 2.26% |
| `g` | 210,341 | 1.66% |
| `h` | 180,491 | 1.43% |
| `f` | 172,998 | 1.37% |
| `b` | 144,328 | 1.14% |
| `E` | 130,121 | 1.03% |

## Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `c` | 49,116 | 6.91% |
| `s` | 46,658 | 6.57% |
| `t` | 38,766 | 5.46% |
| `r` | 34,576 | 4.87% |
| `p` | 31,723 | 4.47% |
| `a` | 31,185 | 4.39% |
| `d` | 26,099 | 3.67% |
| `C` | 23,432 | 3.30% |
| `g` | 22,853 | 3.22% |
| `S` | 21,507 | 3.03% |
| `e` | 21,276 | 2.99% |
| `f` | 20,514 | 2.89% |
| `i` | 19,505 | 2.75% |
| `m` | 19,237 | 2.71% |
| `l` | 17,664 | 2.49% |

## Notes

- 241 identifiers exceed 128 characters; the longest is 264 chars and is almost certainly an embedded blob (base64 font/source-map data) rather than a real identifier.
- Longest token begins: `abcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabc...`
