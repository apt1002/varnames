# Corpus statistics — `multi-language union`

| Metric | Value |
|---|---|
| Distinct identifiers | 2,365,468 |
| Total characters | 42,896,750 |
| Mean length | 18.13 |
| Median length | 16 |
| Min length | 1 |
| Max length | 264 |
| Distinct characters | 63 |
| Starts with `_` | 86,482 (3.66%) |
| Contains `_` | 1,582,262 (66.89%) |
| Ends with a digit | 168,310 (7.12%) |
| Contains a digit | 298,954 (12.64%) |
| ALL_CAPS style | 365,316 (15.44%) |
| Contains inner capitals (camel/Pascal) | 1,040,061 (43.97%) |

## Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 8 |
| p25 | 11 |
| p50 | 16 |
| p75 | 23 |
| p90 | 31 |
| p95 | 37 |
| p99 | 55 |
| p99.9 | 87 |
| p99.99 | 133 |
| max | 264 |

## Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 961,255 | 40.64% |
| 17-24 | 630,969 | 26.67% |
| 25-32 | 278,140 | 11.76% |
| 33-48 | 159,148 | 6.73% |
| 49-64 | 30,078 | 1.27% |
| 65-96 | 9,005 | 0.38% |
| 97-128 | 1,251 | 0.05% |
| 129-256 | 287 | 0.01% |
| >256 | 2 | 0.00% |

## Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 3,937,382 | 9.18% |
| `_` | 3,521,774 | 8.21% |
| `t` | 2,950,150 | 6.88% |
| `r` | 2,188,632 | 5.10% |
| `a` | 2,187,341 | 5.10% |
| `i` | 2,060,074 | 4.80% |
| `s` | 2,053,976 | 4.79% |
| `o` | 1,958,982 | 4.57% |
| `n` | 1,931,051 | 4.50% |
| `l` | 1,378,410 | 3.21% |
| `c` | 1,257,573 | 2.93% |
| `d` | 1,171,307 | 2.73% |
| `p` | 1,023,667 | 2.39% |
| `u` | 926,838 | 2.16% |
| `m` | 865,363 | 2.02% |
| `E` | 844,834 | 1.97% |
| `S` | 687,075 | 1.60% |
| `T` | 680,759 | 1.59% |
| `I` | 637,926 | 1.49% |
| `A` | 624,959 | 1.46% |

## Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `t` | 170,384 | 7.20% |
| `s` | 135,101 | 5.71% |
| `c` | 111,772 | 4.73% |
| `p` | 96,356 | 4.07% |
| `S` | 91,039 | 3.85% |
| `_` | 86,482 | 3.66% |
| `r` | 83,265 | 3.52% |
| `I` | 80,892 | 3.42% |
| `D` | 73,352 | 3.10% |
| `a` | 71,960 | 3.04% |
| `C` | 70,505 | 2.98% |
| `d` | 68,673 | 2.90% |
| `i` | 67,985 | 2.87% |
| `g` | 66,589 | 2.82% |
| `P` | 59,571 | 2.52% |

## Notes

- 289 identifiers exceed 128 characters; the longest is 264 chars and is almost certainly an embedded blob (base64 font/source-map data) rather than a real identifier.
- Longest token begins: `abcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabc...`
