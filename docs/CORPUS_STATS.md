# Corpus statistics — `RubyGems (full)`

| Metric | Value |
|---|---|
| Distinct identifiers | 1,424,035 |
| Total characters | 23,634,180 |
| Mean length | 16.60 |
| Median length | 13 |
| Min length | 1 |
| Max length | 138,787 |
| Distinct characters | 63 |
| Starts with `_` | 23,542 (1.65%) |
| Contains `_` | 668,053 (46.91%) |
| Ends with a digit | 112,317 (7.89%) |
| Contains a digit | 206,647 (14.51%) |
| ALL_CAPS style | 133,552 (9.38%) |
| Contains inner capitals (camel/Pascal) | 610,777 (42.89%) |

## Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 5 |
| p25 | 8 |
| p50 | 13 |
| p75 | 19 |
| p90 | 28 |
| p95 | 38 |
| p99 | 84 |
| p99.9 | 127 |
| p99.99 | 694 |
| max | 138,787 |

## Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 560,293 | 39.35% |
| 17-24 | 282,749 | 19.86% |
| 25-32 | 99,747 | 7.00% |
| 33-48 | 59,525 | 4.18% |
| 49-64 | 17,873 | 1.26% |
| 65-96 | 16,309 | 1.15% |
| 97-128 | 7,089 | 0.50% |
| 129-256 | 954 | 0.07% |
| >256 | 357 | 0.03% |

## Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 2,286,837 | 9.68% |
| `t` | 1,571,663 | 6.65% |
| `a` | 1,400,346 | 5.93% |
| `i` | 1,280,037 | 5.42% |
| `_` | 1,256,690 | 5.32% |
| `r` | 1,245,454 | 5.27% |
| `s` | 1,232,932 | 5.22% |
| `n` | 1,184,295 | 5.01% |
| `o` | 1,182,215 | 5.00% |
| `l` | 812,058 | 3.44% |
| `c` | 749,426 | 3.17% |
| `d` | 676,144 | 2.86% |
| `u` | 581,944 | 2.46% |
| `p` | 565,506 | 2.39% |
| `m` | 523,762 | 2.22% |
| `g` | 452,922 | 1.92% |
| `A` | 321,040 | 1.36% |
| `h` | 317,832 | 1.34% |
| `f` | 299,849 | 1.27% |
| `b` | 283,520 | 1.20% |

## Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `c` | 84,543 | 5.94% |
| `s` | 82,636 | 5.80% |
| `t` | 60,469 | 4.25% |
| `a` | 60,090 | 4.22% |
| `r` | 58,403 | 4.10% |
| `p` | 55,720 | 3.91% |
| `g` | 55,180 | 3.87% |
| `d` | 49,455 | 3.47% |
| `i` | 48,040 | 3.37% |
| `m` | 44,341 | 3.11% |
| `f` | 40,711 | 2.86% |
| `e` | 40,112 | 2.82% |
| `l` | 38,528 | 2.71% |
| `b` | 37,681 | 2.65% |
| `C` | 36,591 | 2.57% |

## Notes

- 1,311 identifiers exceed 128 characters; the longest is 138,787 chars and is almost certainly an embedded blob (base64 font/source-map data) rather than a real identifier.
- Longest token begins: `eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIi4uLy4uLy4uLy4uL2xpYi9oYW5kbGViYXJzL2NvbXBpbGVy...`
