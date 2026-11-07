# Model size in bytes, word list included

Status: **results (grid).**  The clustering notes measure the model in
"numbers" (`k² + 2V`); this note prices the model the standard publishes, in
**bytes**, so the word list can be charged for and the size compared against the
project's budget.  Two shapes of the same statistics are kept apart throughout:
the **Huffman** code the standard publishes and the **arithmetic** reference the
fit tables were measured on.  Everything below is computed at the canonical grid
(`V = 4096 / 6144 / 8192`, `kappa = 300`) on the 10× held-out set
(`n = 42,268`), except where a figure is marked as an estimate.  The inventory is
stated once, so that no object is charged twice.  The pre-grid measurements are
kept in "Pre-grid record" at the end.

## 1. What the standard publishes

The model is a word list and three tables.  The design is nearly settled:

* **The word list.**  A pair-merge dictionary: `V` symbols in total, of which 64
  are implicit — the 63 characters and the stop `\n` — and the remaining
  `V − 64` (`4,032` / `6,080` / `8,128`) are merge rules.  A rule is `P a b`:
  two integers less than `V`, both defined earlier in the list than the rule
  itself.  The decoder replays the rules, so the word list is stored as pairs.
* **The bottom stage: `k` Huffman trees with `V` leaves in total.**  One tree
  per cluster; its leaves are the words in that cluster, labelled by word index.
  A leaf's depth is its code length, so the trees carry `P(word | cluster)`; the
  word → cluster map carries the membership.  Together they are the cluster
  membership table and the unigram vector.
* **The top stage: `k` Huffman trees with `k` leaves each.**  One tree per left
  cluster, its leaves the right clusters `0 … k−1`.  That is the cluster ×
  cluster adjacency matrix, row by row.

Nothing else is published.  The 63 characters are implicit in the identifier
syntax; the cluster → list-of-words index, the tree walks and the canonical code
assignment are derived at load time.

How the tables are *generated* is a separate matter, and the tool chain is not
settled.  What the research still has to settle — `kappa`, the clustering
method, the choice of `k`, the quarter code — moves the parameters but not the
structure.  For comparison, then, a candidate model is the pair `(V, k)`, which
fixes its size once the cost per leaf and per index is fixed, plus one
measurement: the fraction of held-out identifiers it codes into 64 bits.  The
best model is the one furthest bottom-left in the scatter plot in
[`README.md`](../README.md); the rest of this note is the accounting that makes
the horizontal axis honest.

## 2. Theory: Huffman trees

A Huffman code is a full binary tree.  Every internal node has two children,
every leaf is a symbol, and a symbol's codeword is the path from the root, one
bit per branch.  A tree with `L` leaves has exactly `L − 1` internal nodes, one
fewer than it has leaves.

The lengths are near-optimal: `len(s) ≈ −log₂ p(s)`, and the excess — the
redundancy — is bounded by about the largest leaf probability plus a small
constant.  That bound is why a Huffman code is affordable on the
cluster-conditional distributions here, which are very skewed; the measured
rounding is 0.024–0.038 bits per token (`CODING_OVERHEAD.md`).  `ENCODING.md` §5
uses the same bound to price the quarter code.

What has to be published is the **lengths**, not the codewords.  Given one length
per symbol, the code is assigned canonically: sort the symbols by
`(length, label)` and hand out consecutive integers of each length in that order.
Every implementation then derives the same codes from the same table, which is
the property a standard needs (`ENCODING.md` §3).  The decoder walks the canonical
prefix table; it never reads a codeword out of the model.

Three properties of the shipped code matter for the accounting:

* **The stop is a zero-weight leaf.**  Its codeword is the all-zeros path and is
  never written: the padding *is* the terminator.  The stop's own length is
  therefore free per identifier, and each tree is built with the stop's weight
  driven to zero so that the other symbols get the lengths of the renormalised
  distribution (`ENCODING.md` §2).
* **All trailing zeros are free, not just the stop's.**  The code sits in the low
  bits of the integer, so an integer's binary length already stops at its highest
  set bit: whatever zeros end the final codeword are indistinguishable from the
  terminator's padding and are never stored.  On a balanced code that is about
  `½ + ¼ + … = 1` bit per identifier, by luck.  The zero-weight stop and the
  trailing zeros together are worth ~2 bits/identifier that an arithmetic coder
  cannot match.
* **The stop's leaf still costs a leaf.**  It is one of the `V` words and takes a
  leaf in its cluster's tree.  It is in the model; it is just not in the
  identifiers.

## 3. The best representation of a Huffman tree

The current best representation is **a list of the depth of each leaf**, in
label order.  Within each depth the leaves are in label order, so the order
need not otherwise be stored: the canonical assignment above reconstructs every
codeword from the depths alone.  Nor does the shape need storing — the depths
determine it — so the bracket form's "2 bits per internal node" is not paid.

Two things follow, and they cut opposite ways.

* **Against the bracket skeleton alone, the depth table is more expensive.**  A
  depth costs `log₂⌈max depth⌉` bits per leaf (~5 when no tree exceeds depth 31),
  where the bracket skeleton costs 2 bits per internal node, i.e. ~2 per leaf.
  The depth table wins only because it replaces "shape **and** leaf list": the
  leaf list names every leaf by word index, `log₂V` bits each (~13 at
  `V = 8192`), while the depth table needs only the cluster map on top,
  `log₂k` bits per leaf.  At `V = 8192, k = 16` that is **9 bits per leaf against
  15** — 9.2 kB against 15.4 kB — which is where the saving comes from.  It is
  the *labelling* that is saved, not the shape.
* **It cannot do better than that.**  The shape fixes the depths in depth-first
  order and an arbitrary leaf order need not admit that depth sequence: a
  depth-1 leaf can only sit at an end of its subtree.  So the depth has to be
  carried per word; `log₂ depth + log₂ k` is available and `2 + log₂k` is not.
  (An earlier draft claimed `2 + log₂k`; it is not reachable.)

The depths are stored in label order, which is creation order.  That order cannot
be permuted without changing the tokenisation (see "The unigram in creation
order" below), so the depth table carries whatever depth distribution the words
happen to have.

## 4. Theory: the Zipf model of word tree indices

The word list is itself a tree: rule `r` is `(a, b)` and both children are
earlier than the rule.  A child index is therefore `< s`, the number of symbols
defined when its rule was created, so `s ≤ V` and the naive `⌈log₂V⌉` is not the
right cost.  The index stream is also strongly skewed: a low index is an old,
frequent word, because the greedy rule always merges the most frequent adjacent
pair, so creation order is roughly a frequency rank.  That makes the index
distribution approximately Zipf, and a two-parameter prior over the index range
fits it without storing anything:

    p(j) ∝ (j + 1)^−0.7,   j = 0 … s − 1.

Coding the index stream four ways (`scripts/model_budget.py --index-code`, and
the empirical entropy of the index histogram for the last column):

| `V` | fixed `⌈log₂V⌉` | variable `⌈log₂s⌉` | Zipf `p(j) ∝ (j+1)^−0.7` | empirical optimum |
|---:|---:|---:|---:|---:|
| 4,096 | 12.1 kB (24.0 b/rule) | 11.2 (22.2) | **9.8 (19.5)** | 9.2 (18.2) |
| 6,144 | 19.8 (26.0) | 17.8 (23.5) | **15.4 (20.2)** | 14.4 (19.0) |
| 8,192 | 26.4 (26.0) | 24.5 (24.1) | **21.1 (20.8)** | 19.9 (19.6) |

So the answer to "can we get away with fewer than `log V` bits" is **yes, about
20 % fewer** (19 / 22 / 20 % from 4,096 to 8,192), but almost all of it comes
from coding the *skew within* `[0, s)`, not from `s < V`: variable-width buys
7–10 %, and the Zipf prior buys another 12–14 % at no side-information cost.  The
empirical optimum is a further 5–6 % away and would need the distribution stored,
so it is not worth it.

Three tempting alternatives do **not** work, and the first two are worth stating
because they look as if they should:

* the *unigram* distribution is a poor code for child indices (43.4 kB at
  `V = 11 758` on the pre-grid build, worse than plain uniform — the two
  distributions are unrelated);
* the children come in index order only 54–55 % of the time (`a < b` 55.4 /
  54.9 / 53.8 %), so there is no triangular saving;
* storing the empirical distribution costs more than the 5–6 % it would save.

`k_frontier.py` and every byte figure below charge the Zipf code.

## 5. The adopted design, priced

### 5.1 The three tables, byte by byte

Estimates, not serialised bytes: the rule table is priced in §4, the depth and
map counts in §3.  The size oracle in §7 replaces them with measured bytes.

| object | who stores it | how | 4096/16 | 8192/16 | 8192/64 | derivable at load? |
|---|---|---|---:|---:|---:|---|
| word list — rules | the decoder | Zipf-coded child indices | 9.8 kB | 21.1 kB | 21.1 kB | no |
| bottom — depths | the decoder | `V` depths, label order | 2.6 | 5.1 | 5.1 | no |
| bottom — cluster map | the decoder | `V` labels | 2.0 | 4.1 | 6.1 | no |
| top — depths | the decoder | `k²` depths | 0.2 | 0.2 | 2.6 | no |
| terminator | — | the all-zeros path | 0 | 0 | 0 | yes |
| padding | — | high zero bits of the integer | 0 | 0 | 0 | yes |
| cluster → words index | — | from the map | 0 | 0 | 0 | yes |
| canonical codes | — | from the depths | 0 | 0 | 0 | yes |
| program code | the library | — | 2.0 | 2.0 | 2.0 | — |
| **total** | | | **16.6** | **32.5** | **36.9** | |

The depth column assumes no tree exceeds depth 31, i.e. a 5-bit field.  That is
the one figure still to be measured: the zero-weight stop landed at depth 28 at
`V = 2104` (`CODING_OVERHEAD.md`), so a 6-bit field is a real possibility and
would add 1.0 kB at `V = 8192` (1,024 B of depths) and 0.5 kB more to the top
stage at `k = 64`.

### 5.2 The arithmetic alternative

The arithmetic model stores probabilities and evaluates `P(b | a)` at load time.
It is the shape the fit tables were measured on, and it is a **different
object**, not an addition to the Huffman one:

| object | representation | cost at `V = 8192, k = 16` |
|---|---|---:|
| word list — rules | one merge rule per word: two child indices, Zipf-coded | 21.1 kB |
| word list — unigram | the `V` word probabilities, in creation order, one byte each | 8.2 kB |
| membership | the two maps word → left/right cluster | 8.2 kB |
| block | the `k × k` cluster-pair table, one byte per cell | 0.3 kB |
| program code | — | 2.0 kB |
| **total** | | **39.8 kB** |

The 63 characters are implicit in the identifier syntax and cost nothing, and
anything derivable at load time — notably the *cluster* → list-of-words index
(`V log₂V` bits at runtime) — is not charged.  Probabilities are quantised to one
byte per number on the logarithmic grid `P ∝ exp(byte/resolution) − 1`,
`resolution = 12`; this is **free** to within 0.01 bits (`model_fit_rates.py`).

With one shared cluster assignment the two maps collapse to one: **35.7 kB**.
The Huffman inventory in §5.1 assumes the same sharing; keeping both maps adds
4.1 kB there too.  Either way the Huffman shape saves 3.2 kB.  Side by side, the
two shapes at `V = 8192, k = 16` are:

| object | arithmetic | Huffman |
|---|---|---|
| word list rules | rule table | rule table |
| the distributions | unigram + memberships + block | depths + map + top depths |
| program code | 2 kB | 2 kB |
| **total** | **39.8 kB** | **32.5 kB** |

They must never be added — an earlier draft did exactly that and got 53.5 kB by
charging the Huffman bottom-stage codebook on top of the arithmetic tables and
double-counting the 2 kB of code.

#### The unigram in creation order

**The word list is in *creation* order, and that is not unigram order.**  The
greedy rule selects the most frequent *pair* of adjacent symbols, so the sequence
of **selection counts** is monotone non-increasing — but the stored unigram is
the word's count in the **final** segmentation, and a word created early keeps
being absorbed into longer words later, by an amount that is not monotone in the
creation index.  So the guarantee does not hold, even when the dictionary and
the counts come from the same corpus:

| build | adjacent rises | mean rank displacement |
|---|---:|---:|
| `tw4096ns` (`V = 4 096`) | 1 998 / 4 031 (49.6 %) | 17.9 % of `V` |
| `tw6144ns` (`V = 6 144`) | 2 978 / 6 079 (49.0 %) | 16.7 % of `V` |
| `tw8192ns` (`V = 8 192`) | 3 976 / 8 127 (48.9 %) | 15.8 % of `V` |

(`scripts/wordlist_order.py`.  All three are `--sample 20` builds, and the
sampling mismatch roughly doubles the rise rate: the full-corpus `s0` builds
measured 26–27 %.  The displacement is the robust figure.)

The counterexample is stark.  The first created words are `er` 66 665,
`on` 29 190, `es` 51 855, `at` 29 429, `in` 37 791, `en` 28 996 — so `on` was
merged *before* `es`, and at that moment `on` was the more frequent pair, yet in
the final segmentation `es` outnumbers it 1.8 to 1, because `on` is absorbed into
longer words (`only`, `once`, `control`, …) far more heavily.

The order is semantic — the tokeniser merges the lowest-ranked adjacent pair
first — so it cannot be renumbered without changing the tokenisation, and
storing the permutation would cost `V log₂V` bits, about 1.5 times the unigram
itself.  Costed honestly the arithmetic unigram is `V` bytes (4.1 / 6.1 /
8.2 kB); entropy-coding the byte grid (5.4–5.8 bits/value on the pre-grid
builds, i.e. ~0.7 `V`) would bring it to 2.9 / 4.3 / 5.7 kB.  The Huffman shape
has no unigram to store — the depths replace it — but its depth table is in the
same creation order and cannot be permuted either.

### 5.3 The fit-rate convention

The shipped criterion is the Huffman code with the zero-weight stop and the free
trailing zeros.  Three consequences for every fit rate quoted below:

* **Measure bits up to the last 1**, not the sum of codeword lengths.  The
  canonical form is the integer, and its binary length stops at its highest set
  bit; a summed length over-counts by ~1 bit/identifier (`ENCODING.md` §2).
* **The stop's transition is not paid.**  The zero-weight stop returns ~1.8 bits
  and costs ~0.75 in rounding, so the stop is worth ~1 bit; with the trailing
  zeros that is ~2 bits better than the arithmetic figure for the same tables
  (`CODING_OVERHEAD.md`).
* **The fit rate quoted in the tables below is the arithmetic one**, i.e. the
  ideal length of the cyclic code including the stop.  It is therefore
  conservative by ~2 bits, and the frontier in §6 lies down-left of where the
  shipped design does.  Re-measuring it under the shipped convention is step 5 of
  the oracle.

One correction to an earlier version of this note.  At `V = 8192, k = 16` the
measured Huffman figure, 45.027 bits and 85.3 % fit, is the **flat** code — one
tree per left cluster over all `V` words — whose codebook is `W`, about 245 kB
in the bracket form and ~105 kB as the depth table.  It is an upper bound on
what a Huffman code can do at this cell, not the shipped design.  The
**factored** code that ships measures 48.987 bits / 81.9 % (CF) and
47.891 / 82.8 % (CQF `q = 2`) with the stop charged (`ENCODING.md` §5); its
zero-stop figure has not been measured and should come out ~2 bits better.  So
"32.5 kB gets 85.3 %" is not a sentence this note can support yet — 32.5 kB is
the factored model's size, 85.3 % is the flat model's fit.  The oracle measures
both, on the same cell, in the same convention.

### 5.4 The arithmetic size at the grid

Zipf index code, raw-byte unigram, +2 kB code (`scripts/model_budget.py`):

| `V` | `k` | rules | unigram | members | block | code | total |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | 16 | 9.8 | 4.1 | 4.1 | 0.3 | 2.0 | **20.3 kB** |
| 4,096 | 32 | 9.8 | 4.1 | 5.1 | 1.0 | 2.0 | 22.0 |
| 4,096 | 64 | 9.8 | 4.1 | 6.1 | 4.1 | 2.0 | 26.1 |
| 6,144 | 16 | 15.4 | 6.1 | 6.1 | 0.3 | 2.0 | 29.9 |
| 6,144 | 32 | 15.4 | 6.1 | 7.7 | 1.0 | 2.0 | 32.2 |
| 8,192 | 16 | 21.1 | 8.2 | 8.2 | 0.3 | 2.0 | **39.8** |
| 8,192 | 32 | 21.1 | 8.2 | 10.2 | 1.0 | 2.0 | 42.6 |
| 8,192 | 64 | 21.1 | 8.2 | 12.3 | 4.1 | 2.0 | 47.7 |

## 6. The frontier so far

The same accounting against the held-out fit, every measured configuration, with
dominated points removed (a point is kept if it is smaller *and* better than
everything cheaper):

| bytes | `V` | `k` | mean bits | fit ≤64 | fit ≤128 | kB/pt to next |
|---:|---:|---:|---:|---:|---:|---:|
| 19,041 | 4096 | 8 | 51.904 | 77.2 % | 98.0 % | 2.0 |
| 20,257 | 4096 | 16 | 51.462 | 77.8 % | 98.1 % | 9.2 |
| 21,176 | 4096 | 24 | 51.333 | 77.9 % | 98.1 % | 4.4 |
| 22,049 | 4096 | 32 | 51.245 | 78.1 % | 98.1 % | 4.7 |
| 23,928 | 4096 | 48 | 50.889 | 78.5 % | 98.2 % | 5.5 |
| 26,145 | 4096 | 64 | 50.527 | 78.9 % | 98.3 % | **1.1** |
| 26,597 | 6144 | 4 | 50.384 | 79.3 % | 98.3 % | 2.3 |
| 28,181 | 6144 | 8 | 49.674 | 80.0 % | 98.4 % | 3.5 |
| 29,909 | 6144 | 16 | 49.317 | 80.5 % | 98.5 % | 5.8 |
| 32,213 | 6144 | 32 | 48.959 | 80.9 % | 98.5 % | 4.4 |
| 36,637 | 8192 | 6 | 48.282 | 81.9 % | 98.7 % | — (bits only) |
| 37,515 | 8192 | 8 | 48.240 | 81.9 % | 98.7 % | 4.3 |
| 38,793 | 8192 | 12 | 48.019 | 82.2 % | 98.7 % | 3.2 |
| 39,755 | 8192 | 16 | 47.727 | 82.5 % | 98.8 % | 7.6 |
| 41,273 | 8192 | 24 | 47.535 | 82.7 % | 98.8 % | 13.0 |
| 42,571 | 8192 | 32 | 47.481 | 82.8 % | 98.8 % | 24.8 |
| 45,049 | 8192 | 48 | 47.399 | 82.9 % | 98.8 % | 13.2 |
| 47,691 | 8192 | 64 | 47.285 | 83.1 % | 98.8 % | 31.6 |
| 54,009 | 8192 | 96 | 47.108 | 83.3 % | 98.9 % | 80.2 |
| 62,027 | 8192 | 128 | 46.964 | 83.4 % | 98.9 % | — |

The shipped code has been measured at the operating point only.  Its size is an
estimate (§5.1); its fit charges the stop (`ENCODING.md` §5):

| point | kB | fit ≤64 | note |
|---|---:|---:|---|
| CF | 32.5 | 81.9 % | 8192/16, factored, stop charged |
| CQF `q = 2` | 32.6 | 82.8 % | 8192/16, adopted, stop charged |

**Read the axes with care.**  The bytes are the **arithmetic** model's (§5.4) and
the fit is the **arithmetic** ideal length, stop included; the two are
consistent with each other, and neither is the shipped code's.  The shipped
factored code is smaller at the same `(V, k)` — 32.5 kB against 39.8 kB at
8192/16, or 36.6 against 39.8 with the maps counted alike — and fits ~2 bits
better once the zero-weight stop is measured.  So this table is the frontier of
the *reference*, and the shipped design's frontier lies down and to the left of
it.  Its shape — the knee, the cheap stretch, the dead
zone — carries over; the numbers do not.  [`README.md`](../README.md) plots these
points, with the one measured shipped cell marked.

Four things follow.

* **The cheap stretch is 20–39 kB at 1–6 kB per fit point**, and it is the `V`
  step out of 4096 plus the low-`k` 6144 and 8192 configurations.  Below 20 kB
  you are on 4096 with a coarse `k`; above 40 kB each further point costs 8, 13,
  25, 32 and finally 80 kB per point.
* **The best value on the whole curve is the corner at 26 kB**: 4096 / `k = 64`
  → 6144 / `k = 4` costs 452 B for +0.4 pt (1.1 kB/pt) because the bigger word
  list pays for itself twice — better tokens *and* a `k` that can be coarser.
* **`V = 6144` dominates the upper half of the 4096 sweep.**  Its *worst* point
  (`k = 4`, 26.6 kB, 79.3 %) matches the best 4096 point that costs less
  (31.9 kB at `k = 96`, 79.3 %) at 5.3 kB cheaper, and 6144 at `k = 16`
  (29.9 kB, 80.5 %) beats 4096's best overall (39.5 kB at `k = 128`, 79.6 %) by
  0.9 points for 9.6 kB less.
* **Fit ≤128 is saturated** (98.0–98.9 % everywhere), so every trade here is a
  64-bit trade.

### The frontier along `k` — the interior slices

`scripts/k_frontier.py` sweeps `k` at fixed `V` with the same accounting and the
same held-out set.  These are the same points as the frontier table above, kept
separate because the *local slope* is what prices a change made inside a model
(the shared clusters, the reserved stop cell, the quarters).

`V = 4096`, stride 10 (`n = 42,268`):

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 8 | 51.904 | 77.2 % | 98.0 % | 19,041 |
| 16 | 51.462 | 77.8 % | 98.1 % | 20,257 |
| 24 | 51.333 | 77.9 % | 98.1 % | 21,176 |
| 32 | 51.245 | 78.1 % | 98.1 % | 22,049 |
| 48 | 50.889 | 78.5 % | 98.2 % | 23,928 |
| 64 | 50.527 | 78.9 % | 98.3 % | 26,145 |
| 96 | 50.203 | 79.3 % | 98.3 % | 31,864 |
| 128 | 49.919 | 79.6 % | 98.4 % | 39,457 |

`V = 6144`:

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 4 | 50.384 | 79.3 % | 98.3 % | 26,597 |
| 8 | 49.674 | 80.0 % | 98.4 % | 28,181 |
| 16 | 49.317 | 80.5 % | 98.5 % | 29,909 |
| 32 | 48.959 | 80.9 % | 98.5 % | 32,213 |
| 64 | 48.626 | 81.3 % | 98.6 % | 36,821 |
| 96 | 48.322 | 81.6 % | 98.6 % | 42,840 |

`V = 8192`:

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 4 | 48.995 | 81.2 % | 98.6 % | 35,419 |
| 6 | 48.282 | 81.9 % | 98.7 % | 36,637 |
| 8 | 48.240 | 81.9 % | 98.7 % | 37,515 |
| 12 | 48.019 | 82.2 % | 98.7 % | 38,793 |
| 16 | 47.727 | 82.5 % | 98.8 % | 39,755 |
| 24 | 47.535 | 82.7 % | 98.8 % | 41,273 |
| 32 | 47.481 | 82.8 % | 98.8 % | 42,571 |
| 48 | 47.399 | 82.9 % | 98.8 % | 45,049 |
| 64 | 47.285 | 83.1 % | 98.8 % | 47,691 |
| 96 | 47.108 | 83.3 % | 98.9 % | 54,009 |
| 128 | 46.964 | 83.4 % | 98.9 % | 62,027 |

| step | Δbits | Δbytes | kB/bit | Δ fit ≤64 | kB per point |
|---|---:|---:|---:|---:|---:|
| 4096: 8→16 | −0.442 | +1,216 | 2.8 | +0.6 | 2.0 |
| 4096: 16→24 | −0.129 | +919 | 7.1 | +0.1 | 9.2 |
| 4096: 24→32 | −0.088 | +873 | 9.9 | +0.2 | 4.4 |
| 4096: 32→48 | −0.356 | +1,879 | 5.3 | +0.4 | 4.7 |
| 4096: 48→64 | −0.362 | +2,217 | 6.1 | +0.4 | 5.5 |
| 4096: 64→96 | −0.324 | +5,719 | 17.7 | +0.4 | 14.3 |
| 4096: 96→128 | −0.284 | +7,593 | 26.7 | +0.3 | 25.3 |
| 6144: 4→8 | −0.710 | +1,584 | 2.2 | +0.7 | 2.3 |
| 6144: 8→16 | −0.357 | +1,728 | 4.8 | +0.5 | 3.5 |
| 6144: 16→32 | −0.358 | +2,304 | 6.4 | +0.4 | 5.8 |
| 6144: 32→64 | −0.333 | +4,608 | 13.8 | +0.4 | 11.5 |
| 6144: 64→96 | −0.304 | +6,019 | 19.8 | +0.3 | 20.1 |
| 8192: 4→6 | −0.713 | +1,218 | 1.7 | +0.7 | 1.7 |
| 8192: 6→8 | −0.042 | +878 | 20.9 | +0.0 | — |
| 8192: 8→12 | −0.221 | +1,278 | 5.8 | +0.3 | 4.3 |
| 8192: 12→16 | −0.292 | +962 | 3.3 | +0.3 | 3.2 |
| 8192: 16→24 | −0.192 | +1,518 | 7.9 | +0.2 | 7.6 |
| 8192: 24→32 | −0.054 | +1,298 | 24.0 | +0.1 | 13.0 |
| 8192: 32→48 | −0.082 | +2,478 | 30.2 | +0.1 | 24.8 |
| 8192: 48→64 | −0.114 | +2,642 | 23.2 | +0.2 | 13.2 |
| 8192: 64→96 | −0.177 | +6,318 | 35.7 | +0.2 | 31.6 |
| 8192: 96→128 | −0.144 | +8,018 | 55.7 | +0.1 | 80.2 |

Five things follow.

* **`k = 16` is the floor, at both vocabularies.**  Fit *falls* below it —
  77.8 → 77.2 % at 4096 and 82.5 → 81.9 → 81.2 % from 16 down to 6 and 4 at
  8192 — so there is a genuine optimum rather than "the lowest affordable `k`".
  At 8192, `k = 6` is the same fit as `k = 8` for 878 B less, and `k = 4` is a
  full point worse.  The earlier open question ("`k = 8` may be better still")
  is answered: it is not.
* **Below `k = 16` the curve is as cheap as the `V` direction** (1.7–3.3 kB/pt
  at 8192) because a very coarse clustering is genuinely broken, and the repair
  is worth paying for.  Above 16 it is a plateau and then a dead zone: 16 → 64
  buys 0.6 points for 7.9 kB (13 kB/pt), 64 → 96 buys 0.2 for 7.3 kB
  (32 kB/pt), and 96 → 128 buys 0.1 for 8.0 kB (80 kB/pt).
* **The apparent cheap segment at 32→48 was noise.**  At `n = 4,227` it looked
  like 2.8 kB/pt, inviting a story about a cheap stretch; at `n = 42,268` it is
  4.7, in line with its neighbours.  The 10× held-out set was run for exactly
  this reason: with 4,227 identifiers, adjacent fit differences of 0.2–0.7 pt
  are ±0.9 pt, so segment *slopes* were never reliable to better than a factor
  of two.  Absolute fit rates also fell 0.2–0.9 pt at every `k`.
* **The knee is the `k²` block taking over from the memberships, and it moves
  with `V`.**  At 4096 the block is 1.0 kB at `k = 32`, 4.1 at 64 and 16.4 at
  128, so the curve is still paying about 5 kB/pt up to 64 and 14.3 beyond it.
  At 8192 the memberships are already 8.2 kB at `k = 16` and every step above it
  costs 7.6–13 kB/pt.  The block table, not the memberships, dominates the top
  of the curve.
* **The envelope is a ramp, not a staircase — and the earlier claim was an
  artefact.**  Reading only the two `k`-sweeps, the frontier looked
  discontinuous: 4096's best point (31.9 kB, 79.3 %) against 8192's worst
  (35.4 kB, 81.2 %) was a 1.9-point jump for 3.5 kB.  That comparison put the
  *top* of one `k`-curve (where `k` is worth nothing) against the *bottom* of
  the next.  With `V = 6144` measured in between, the jump disappears: the
  envelope passes 79.3 % at 26.6 kB and 81.2 % at 32.2 kB on the way to 81.9 %
  at 36.6 kB.

**This is a slice, not the frontier.**  The sweep answers what the *next*
kilobyte buys **at fixed `V`**, which is the right comparison for a candidate
that adds bytes to an existing model but the wrong one for "should this model be
bigger".  Used that way the two pictures agree: the k-curve is interior to the
`V`-envelope, and its local slope (4.7 kB/pt in the middle of the 4096 sweep) is
the opportunity cost of spending a kilobyte *inside* a model rather than
replacing it.

### `V` against `k` at matched size

Once the rule table is charged, the earlier "`V` is 2–6× cheaper than `k`" claim
softens but survives:

* the `V` step at matched `k` is **3.6 kB/pt** (4096→6144, `k = 16`),
  **4.9** (6144→8192, `k = 16`) and **5.5** (6144→8192, `k = 32`);
* the `k` step above 16 at 8192 is **7.6 / 13.0 / 24.8 / 13.2** kB/pt
  (16→24→32→48→64), then 31.6 to 96 and 80.2 to 128.

So a bigger word list is still the cheaper way to buy a point, but by 1.5–4×
against the 8–25 kB/pt the `k` direction costs above 16, not by the 2–6× claimed
when the rule table was omitted.  The mechanism is mechanical: a bigger word list
shortens identifiers (held-out mean length falls 4.70 → 4.05 tokens from
`V = 4096` to `8192`) and the 64-bit budget is dominated by the *long*
identifiers, so `V` attacks the part of the distribution the threshold measures;
a finer `k` only shaves the conditional entropy of tokens already inside an
identifier.

## 7. The size oracle

The structure in §1 and the oracle answer different questions.  The structure
says **what is stored**; the oracle says **how many bytes it takes**.  The oracle
is the more general of the two, because once built it measures whatever structure
it is given — the arithmetic shape, the Huffman shape, the flat variant, the
quarter code — from the same script and the same held-out set.  The three tables
in §1 are the special case that ships.  The byte figures above are arithmetic and
formula-driven, and formulas have drifted three times: the 53.5 kB total that
double-charged a Huffman bottom stage, the missing word→left-cluster map, and a
"bracket vs length table" claim that did not survive re-reading.  The next step
is therefore to stop pricing the model by formula and measure it.  Six steps:

1. `scripts/model_size.py` — the size **oracle**.  Build at `(V, k)`, serialise
   the model in the published format (§1), report actual bytes per section,
   decode a held-out identifier and assert losslessness, and report the code's
   real bits/identifier from the decoded artefact.  From then on every published
   byte comes from this, not from a formula.
2. One **inventory table** in this note: object / who stores it / how / bytes at
   4096/16, 8192/16, 8192/64 / derivable at load? / charged where.  The
   checklist is rules, unigram, left map, right map, block, bottom codebook, top
   codebook, program code, terminator, padding.  §5.1 is the first cut of it.
3. The **depth store**: measure the maximum code depth in every bottom and top
   tree on the grid.  That sets the bits per depth (4, 5 or 6 — a 5-bit field
   assumes no tree exceeds depth 31), whether any tree must be length-limited
   (which costs bits), and whether the top stage is `k²` packed depths or
   something cheaper.  It also confirms that the depth is carried per word: the
   leaf-list-free `2 + log₂k` form fails because a depth-1 leaf can only sit at
   an end of its subtree, so the Huffman depth sequence need not be realisable
   in an arbitrary order.
4. **Re-derive** every table from the oracle: the frontier here, `ENCODING` §5
   (`CF`/`CQF`/`W`), `WORDLIST_BUDGET`, `CLUSTER_WORDS`, `SHARED_CLUSTERS` and
   the shared-cluster, reserved-cell and quarter pricing, `PRUNE_WORDS`,
   `DICTIONARY_RULES`, and `SMALL_DICT`'s price row.  The dictionary term must
   be charged in `shared_clusters.py`, `quarter_accounting.py` and the
   corresponding comparisons, which still quote code-side bytes; their verdicts
   are unaffected (they are within-`V`), but any cross-`V` price must carry the
   term.
5. **Fit-rate convention.**  Re-measure the fit under the shipped criterion of
   §5.3 — the zero-weight stop, all trailing zeros free — for the *factored*
   code at every grid cell, and settle the `k = 16`, `q = 2` and shared-cluster
   choices on those numbers rather than on arithmetic bits.  This is also where
   the flat-versus-factored mix-up of §5.3 gets closed.
6. **Retire** the superseded numbers: `README.md`'s status line, and any table
   not produced by the oracle.

The outcome is a single number per model, traceable to a file the decoder can
read.

## 8. What it shows

* **The rule table is more than half the model** — 21.1 of 32.5 kB at the
  operating point, well ahead of the depths and the map (5.1 and 4.1 kB).  Zipf
  coding already takes 20 % off the fixed-width index stream; the empirical
  optimum is only a further 5 % and would have to be stored.  The real lever is a
  smaller vocabulary, which is the `V`-against-`k` trade above.
* **The frontier is 19 kB / 77 %, 30 kB / 81 %, 40 kB / 83 %** on the arithmetic
  reference — comfortably inside the "50 kB-ish is acceptable if it rescues the
  64-bit set" band, and 2× the 20 kB goal.  The shipped code sits below and left
  of that curve; how far is what the oracle measures.
* **Size is not what costs the 64-bit set — clustering is.**  The full-table
  ceilings are 85–94 %; the shipped models fit 77–83 %.  The gap is the
  membership and block structure, not the word list.
* **The next two objects are the map and the depths** (4.1 and 5.1 kB at the
  operating point).  `2V · ⌈log₂k / 8⌉` doubles by `k = 64`, so the map is the
  term that makes a fine `k` expensive; it is what the shared cluster assignment
  buys down.  The depth store is the one figure still estimated — a 6-bit field
  instead of 5 adds 1 kB, and the top stage grows from 0.2 kB at `k = 16` to
  2.6 kB at `k = 64`.

## Reproducing

```sh
# model size, with the rule table priced from the directory
for d in work/tw4096ns work/tw6144ns work/tw8192ns; do
  python3 scripts/model_budget.py --dirs $d --ks 16,32,64 --index-code zipf --code 2000
done

# the k-sweeps (bytes in the full inventory by default; --code-side for the
# Huffman codebook accounting used in SHARED_CLUSTERS.md)
python3 scripts/k_frontier.py --dir work/tw4096ns --ks 8,16,24,32,48,64,96,128 --stride 10
python3 scripts/k_frontier.py --dir work/tw6144ns --ks 4,8,16,32,64,96 --stride 10
python3 scripts/k_frontier.py --dir work/tw8192ns --ks 4,6,8,12,16,24,32,48,64,96,128 --stride 10

# creation order vs unigram order
python3 scripts/wordlist_order.py --dirs work/tw4096ns,work/tw6144ns,work/tw8192ns

# the scatter plot in README.md (reads the frontier table above)
python3 scripts/frontier_plot.py --doc docs/MODEL_BUDGET.md --out docs/frontier.svg
```

## Pre-grid record

Before the 10-ecosystem corpus the frontier was measured on the older
vocabularies (`V = 2 104 / 4 478 / 11 758`) at stride 40 (`n = 5 739`) and priced
with the codebook accounting discussed above.  Those numbers are **not**
comparable with the tables in this note — different corpus, vocabulary and
accounting — and are kept only as the record of what was believed at the time:

| size | `V` | `k` | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 14.3 kB | 2,104 | 52 | 56.72 | 70.4 % | 97.0 % |
| 22.9 kB | 2,104 | 105 | 55.48 | 71.8 % | 97.3 % |
| 26.1 kB | 4,478 | 52 | 51.75 | 76.3 % | 98.1 % |
| 35.3 kB | 4,478 | 105 | 51.10 | 77.0 % | 98.2 % |
| 64.2 kB | 11,758 | 52 | 47.21 | 82.5 % | 98.9 % |
| 75.2 kB | 11,758 | 105 | 46.90 | 82.9 % | 98.9 % |

Full tables (stride 40): `V = 2 104` 4.2 MB / 85.1 %, `V = 4 478` 19.1 MB /
89.4 %, `V = 11 758` 131.8 MB / 93.5 %.  The old 64.2 kB point and the current
47.7 kB point (`8192, k = 64`) differ by 0.6 pt of fit, but they are different
corpora: the size difference is mostly the smaller vocabulary and its cheaper
memberships, not a better model.

## Rejected / not done

* Reordering the word list by unigram — not possible without changing the
  tokenisation; the list is in creation order (measured above).
* A unigram-derived code for the child indices — worse than uniform.
* Storing the empirical child-index distribution — 5 % of the index stream,
  paid for by storing the distribution.
* Entropy-coding the *index stream* beyond the two-parameter Zipf prior.
* A cluster → members index: derivable at load time, not charged.
* Charging a Huffman codebook *and* the arithmetic tables for one model — they
  are alternatives (see "The arithmetic alternative").
