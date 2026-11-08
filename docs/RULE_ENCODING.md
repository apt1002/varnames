# Encoding the rule list

**Adopted: two child indices, each coded by a base-2 geometric ladder, `b = 3`.**
The rule list is the largest object in the model file, so its encoding is worth
a grid.  This note is the experiment: three ways of combining a pair into one
number, crossed with eight ways of coding a number known to lie in `[0, N)`.
It measured 42 encodings on the shipped 8,192-word list, and the best is what
`MODEL_FORMAT.md` §4 specifies.  Nothing here is part of the format: the
adopted design is stated there, and this note exists so it does not have to be
re-argued.

## The problem

Rule `r` is a pair `(u, v)` of child ids, both below `N = len(alphabet) + r`,
and the file stores `V − len(alphabet)` of them.  Two choices:

1. how to turn the pair into numbers;
2. how to code a number that the decoder knows lies in `[0, N)`.

The index stream is strongly skewed: a low index is an old, frequent word,
because the greedy rule always merges the most frequent adjacent pair, so
creation order is roughly a frequency rank.  The whole gain, if there is one,
is in coding that skew.

## The grid

The first axis combines the pair into one number:

| pairing | `x` stored | range |
|---|---|---:|
| Pair | `u` and `v`, two numbers | `N²` |
| Triangle | `(u + v)(u + v − 1)/2 + u` | `2N²` |
| Square | `v² + u` if `u < v`, else `u(u + 1) + v` | `N²` |

The second axis codes a number in `[0, N)`:

| number code | bits |
|---|---|
| Fixed | `⌈log₂ N⌉` |
| Variable | `L = ⌊log₂ N⌋`, `s = N − 2^L`: `L` bits, then one more when `x ≥ 2^L − s` |
| Zipf | `b` bits of interval index, then Variable inside the interval |

The Zipf code is a geometric ladder: interval `i` is
`[N(base^i − 1)/(base^B − 1), N(base^(i+1) − 1)/(base^B − 1))` for
`B = 2^b` intervals, the index is
`floor(log_base(1 + (base^B − 1)x/N))`, and the residual inside the interval is
coded Variable.  The grid runs `b = 2, 3` and base 2, `e`, `√e`.

There are 24 design points, but the design's index formula writes `base^b`,
which yields only `b` intervals and so wastes most of the `b`-bit field; the
script prices that reading (`narrow`) against the one that uses the field,
`B = 2^b` (`wide`).  Both are in the table below, which is the wide reading
unless marked.

## The measured grid

Bytes for the whole 8,128-rule list (16,256 child indices), stride 10, on
`work/tw8192ns`.  Only the rows that matter for a decision are shown; the full
42-row output is `python3 scripts/rule_encoding.py --dir work/tw8192ns`.

| encoding | bytes | bits/child |
|---|---:|---:|
| **Zipf `b = 3`, base 2, Pair** | **20,925** | **10.298** |
| Zipf `b = 3`, base √e, Pair | 20,961 | 10.316 |
| Zipf `b = 2`, base e, Pair | 20,983 | 10.326 |
| Zipf `b = 3`, base e, Triangle | 21,162 | 10.415 |
| Zipf `b = 3`, base e, Square | 21,259 | 10.462 |
| Zipf `b = 2`, base 2, Pair | 21,416 | 10.539 |
| Zipf `b = 3`, base 2, Square | 21,458 | 10.560 |
| Zipf `b = 3`, base 2, Triangle | 21,555 | 10.608 |
| Zipf `b = 3`, base e, Pair | 21,564 | 10.612 |
| Zipf `b = 3`, base e, Square (narrow) | 23,711 | 11.669 |
| Pair / Variable | 22,948 | 11.293 |
| Square / Variable | 23,247 | 11.440 |
| Triangle / Variable | 24,154 | 11.887 |
| Square / Fixed | 24,072 | 11.846 |
| Pair / Fixed | 24,492 | 12.053 |
| Triangle / Fixed | 25,086 | 12.346 |

Three findings answer the axes, and a fourth prices the field width.

### Pair wins

Combining the pair costs more than it saves in every row that can be compared.
Pair codes each child with its own ladder, so a rule `(common, rare)` pays a
short code for the common child and a long one for the rare — which is what the
skew is.  Any pairing forces the two children through one number, so a frequent
child paired with an infrequent one cannot get the short code its own frequency
earns.

**Triangle** was meant to sort pairs by `u + v`, but the sum runs to `2N − 2`,
so the enumerated range is about `2N²` and it spends a full bit per rule before
any coding starts; the construction also forgot the cases `u ≥ N` / `v ≥ N`,
which is why it is not the bijection it looks like.  It measures 21,162 B at
best, 237 B behind Pair.

**Square** is the corrected formula `v² + u` if `u < v`, else `u(u + 1) + v`.
It *is* a bijection onto `[0, N²)` — verified exhaustively for `N = 2…5`, and
injective on all 8,128 rules of the shipped list — so it occupies exactly the
range Pair does and there is no range penalty.  What it does not do is preserve
the skew: it interleaves the two orders, so `(common, rare)` and `(rare,
common)` land far apart, and the ladder cannot give either of them the short
code the frequency of the common child deserves.  Measured at its best (base 2,
`b = 3`) it is 21,458 B, **533 B behind Pair** — usable, exactly as expected,
and not competitive.  (The first version of the formula, `(v − 1)² + u` /
`u(u − 1) + v`, collided at `(0, 1)` and `(1, 0)`; that was a bug in the
formula, not a verdict on the idea.)

### The ladder beats a fixed or variable field

Fixed width at `⌈log₂ N⌉` per child is the cheapest a fixed field can be, since
the decoder knows `r`; it costs 24,492 B.  One flat 13-bit field for every child
would cost 16,256 × 13/8 = 26,416 B.  Variable width saves what the field's
ragged top costs, but not the skew: 22,948 B.  The geometric ladder is 20,925 B,
so 2.0 kB better than Variable and 3.6 kB better than Fixed.  Nothing comes
from `N < V`; all of it comes from coding the skew.

### The field width is worth using whole

Writing `base^b` in the index formula yields only `b` intervals, so a `b`-bit
index mostly codes emptiness: the best narrow row is 23,711 B, against 20,925 B
for the same base and `b` read wide.  `b = 3` is the optimum in the wide
reading: `b = 2` costs 21,416 B (the intervals are too coarse), `b = 4` 22,430 B
and `b = 5` 24,460 B (they get too narrow to carry their own residual).

### The base hardly matters

Base 2, `e` and `√e` are within 0.3 % of each other at `b = 3`.  Base 2 is the
one to ship because its interval edges are exact integers,
`N(2^i − 1) // (2^B − 1)`, so the decoder needs no floating point.  The design
states a third exponent as `s = −ln√2` with `base = exp(0.5)`; under
`base = 2^(−1/s)` that gives `exp(2)`, which measures 23,610 B at `b = 3`,
13 % worse — the base is the meaningful parameter, not `s`.

## How close is that to the limit?

The pooled entropy of the absolute child index over `[0, V)` is 9.80 bits per
child, i.e. 19,916 B for the list, only 5 % below the ladder.  Reaching it would
need the empirical distribution to be stored, and that costs more than the 1 kB
it saves.  Two cheaper-looking alternatives do not work either:

* the *unigram* distribution is a poor code for child indices — worse than
  plain uniform, because a rule's children are frequent *at the time it was
  made* and the unigram is measured at the end;
* the children come in index order only 54–55 % of the time (`a < b` 55.4 /
  54.9 / 53.8 % at 4,096 / 6,144 / 8,192), so there is no triangular saving —
  and measured, Triangle is 1.2 kB dearer than Pair.

## The adopted code, precisely

The file stores, for rule `r`, the two child ids, each by the same static
ladder:

    B       = 2^b,  b = 3
    edge(i) = N (2^i − 1) // (2^B − 1)        for i = 0 … B
    index   = floor(log_2(1 + (2^B − 1) x / N))
    residual = x − edge(index),  coded as a variable-width integer in
               [0, edge(index + 1) − edge(index))

The decoder derives `edge` from `N` and `b` with integer arithmetic — nothing is
stored for the code and nothing is computed at start-up beyond those divisions.
At base 2 the index is also exact in integers:

    index = floor(log2(1 + x (2^B − 1) / N))

which a decoder can get by shifting.  The rule stream is not self-delimiting, so
its length is stored as a varint; that is three bytes at the operating point.
