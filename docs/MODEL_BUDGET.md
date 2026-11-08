# Model size in bytes, word list included

Status: **results (grid).**  The clustering notes measure the model in
"numbers" (`k² + 2V`); this note prices the model the standard publishes, in
**bytes**, so the word list can be charged for and the size compared against the
project's budget.  **Every number below is a byte count from a file
`scripts/model_size.py` packed and read back, or a fit rate from decoding
identifiers through it** — every decision has been made on the measured Huffman
code.  Everything below is computed at the
canonical grid (`V = 4096 / 6144 / 8192`, `kappa = 300`) on the 10× held-out set
(`n = 42,268`), except where a figure is marked as an estimate.  The inventory
is stated once, so that no object is charged twice.  The pre-grid measurements
are kept in "Pre-grid record" at the end.

## 1. What the standard publishes

The model is a word list and three tables.  The design is nearly settled:

* **The word list.**  A pair-merge dictionary: `V` symbols in total, of which the
  63 characters are implicit and the other `V − 63` (`4,032` / `6,080` /
  `8,128`) are merge rules.  A rule is `P a b`: two integers defined earlier in
  the list than the rule itself.  The decoder replays the rules, so the word
  list is stored as pairs.
* **The bottom stage: `k` Huffman trees with `V` leaves in total.**  One tree
  per cluster; its leaves are the words in that cluster, labelled by word index.
  A leaf's depth is its code length, so the trees carry `P(word | cluster)`; the
  word → cluster map carries the membership.  Together they are the cluster
  membership table and the unigram vector.
* **The top stage: `k` Huffman trees with `k + 1` leaves each.**  One tree per
  left cluster, its leaves the right clusters `0 … k−1` plus a zero-weight
  STOP leaf.  That is the cluster × cluster adjacency matrix, row by row.

Nothing else is published.  The 63 characters are implicit in the identifier
syntax; the cluster → list-of-words index, the tree walks and the canonical code
assignment are derived at load time.  There is no stop symbol in the file: an
identifier ends when the top stage says so, so the corpus tokeniser's stop
token has no leaf of its own (`MODEL_FORMAT.md` §1).

How the tables are *generated* is a separate matter, and it does not reach the
file.  A build may change its prior, its clustering method, its sample or its
value of `k`; the format describes whatever tables it is handed, so such a
change moves the numbers in this note and nothing else.  That is the property
that lets the model be re-tuned after the format is fixed.

For comparison, then, a candidate model is the triple `(V, k, q)`, which fixes
its size once the cost per leaf and per index is fixed, plus one measurement:
the fraction of held-out identifiers it codes into 64 bits.  The best model is
the one furthest bottom-left in the scatter plot in
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
rounding is 0.024–0.038 bits per token (`CODING_OVERHEAD.md`).  The bound is
why a Huffman code is affordable at all; it is not a size, so nothing in this
note is priced with it — every table below is a byte count from a packed file.

What has to be published is the **lengths**, not the codewords.  Given one length
per symbol, the code is assigned canonically, in the one direction that leaves
the all-zeros codeword on the terminator: the first leaf at the maximum depth
takes it and the rest follow from the far end of the code space
(`MODEL_FORMAT.md` §2).  Every implementation then derives the same codes from
the same table, which is the property a standard needs (`ENCODING.md` §3).  The
decoder walks the canonical prefix table; it never reads a codeword out of the
model.

Three properties of the shipped code matter for the accounting:

* **The terminator is a zero-weight leaf in the top stage.**  Its codeword is
  the all-zeros path and is never written: the padding *is* the terminator.  Its
  own length is therefore free per identifier, and each top tree is built with
  that leaf's weight driven to zero so that the other leaves get the lengths of
  the renormalised distribution (`ENCODING.md` §2).  The word trees carry no
  terminator: the padding meets the top stage first, so an identifier ends
  before any word step.
* **All trailing zeros are free, not just the stop's.**  The code sits in the low
  bits of the integer, so an integer's binary length already stops at its highest
  set bit: whatever zeros end the final codeword are indistinguishable from the
  terminator's padding and are never stored.  On a balanced code that is about
  `½ + ¼ + … = 1` bit per identifier, by luck.  The zero-weight stop and the
  trailing zeros together are worth ~2 bits/identifier against a code that has
  to spend bits on the end of the identifier, and this is the convention every
  fit rate in this note is measured under.
* **The terminator leaf still costs a depth.**  Every top tree pays one extra
  depth for its STOP leaf — 528 B rather than 512 B over the 32 trees at the
  operating point.  It is in the model; it is just not in the identifiers.

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

**Measured** (`scripts/model_size.py`): unbiased, the depth distribution is
broad rather than peaked — at 8192/16 the word depths run from 0 (singletons) to
23 — so a raw depth needs five bits.  The format does not store raw depths: it
stores `d − d_min` per tree in a fixed four-bit field and recovers `d_min` from
the Kraft equality ([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3).  Four bits cover a
span of 15, so the build biases the weights before the merge — *searched*, by
doubling to bracket and then bisecting for the least value that holds every
tree to that span (`MODEL_FORMAT.md` §3.1).  Measured, every tree on the grid
fits the field: the operating point lands exactly on a span of 15, and 4096/16
needs no bias at all.  The narrowing takes 1,156 B off the operating-point file
while moving the fit rate by nothing and the mean bits by 0.001.

## 4. Coding the child indices

The word list is itself a tree: rule `r` is `(a, b)` and both children are
earlier than the rule, so a child index is below `N = len(alphabet) + r`.  The
index stream is also strongly skewed: a low index is an old, frequent word,
because the greedy rule always merges the most frequent adjacent pair, so
creation order is roughly a frequency rank.

`scripts/rule_encoding.py` prices a grid of pairings and number codes on the
shipped 8,192-word list — 8,128 rules, 16,256 child indices.  The adopted entry
codes the two children separately with a static base-2 geometric ladder; bytes
are for the whole list, bits per child index:

| encoding | bytes | bits/child |
|---|---:|---:|
| **Zipf `b = 3`, base 2, Pair** | **20,925** | **10.298** |
| Zipf `b = 3`, base √e, Pair | 20,961 | 10.316 |
| Zipf `b = 2`, base e, Pair | 20,983 | 10.326 |
| Zipf `b = 3`, base e, Triangle | 21,162 | 10.415 |
| Zipf `b = 3`, base 2, Square | 21,458 | 10.560 |
| Pair / Variable | 22,948 | 11.293 |
| Pair / Fixed | 24,492 | 12.053 |

* **The skew inside `[0, N)` is the whole of the gain.**  Fixed width at
  `⌈log₂ N⌉` per rule — the cheapest a fixed field can be, since the decoder
  knows `r` — costs 24,492 B, and the geometric ladder 20,925 B.  A single
  13-bit field for every child would cost 26,416 B.  Nothing comes from
  `N < V`; all of it comes from coding the skew.
* **Combining the pair never pays.**  Triangle sorts `(u, v)` by `u + v`, which
  runs to `2N − 2` and so enumerates about `2N²` values — a full bit per rule
  before any coding starts — and it also misses the cases `u ≥ N` / `v ≥ N`.
  Square is the corrected formula `v² + u` if `u < v`, else `u(u + 1) + v`; it
  *is* a bijection onto `[0, N²)`, so it costs no range, but it interleaves the
  two orders and so destroys the per-child skew: a rule `(common, rare)` cannot
  give the common child a short code.  It measures 533 B behind Pair.  Pair —
  two numbers, each in `[0, N)` — is what the file stores.
* **The ladder beats the arithmetic coder it replaced**, by 184 B, and it needs
  no arithmetic coder: the decoder computes the interval edges from `N` and `b`
  with integer arithmetic (`N(2^i − 1) // 255` at base 2) and reads a
  variable-width residual inside the interval it lands in.  Nothing is stored
  for the code and nothing is computed at start-up beyond those divisions — the
  rule list is read, not derived.

The whole grid — three pairings, eight number codes, `b` from 2 to 5, three
bases, and the narrow and wide readings of the index formula — is
[`RULE_ENCODING.md`](RULE_ENCODING.md).  It also prices the empirical entropy
limit: the pooled entropy of the child index is 9.80 bits/child, only 5 % below
the ladder, and reaching it would need the empirical distribution to be stored,
which costs more than the kilobyte it saves.

## 5. The adopted design, priced

### 5.1 The three tables, byte by byte

**Measured**, not estimated: `scripts/model_size.py` writes the model, packs it
in the layout of [`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3 and reports each
section, so every number below is a byte count from a file the decoder read
back.  The columns are the shipped code, `q = 1`, so the map is `⌈log₂ k⌉` bits
wide; the right-hand column is the operating point.

| object | who stores it | how | 4096/16 | 8192/16 | 8192/32 | derivable at load? |
|---|---|---|---:|---:|---:|---|
| word list — rules | the decoder | geometric-ladder child indices (§4) | 9,787 | 20,926 | 20,926 | no |
| bottom — depths | the decoder | `V` depths, 4-bit field | 2,048 | 4,096 | 4,096 | no |
| bottom — cluster map | the decoder | `V` labels, 4 or 5 bits | 2,048 | 4,096 | 5,120 | no |
| top — depths | the decoder | `k(k+1)` depths, 4-bit field | 136 | 136 | 528 | no |
| header, alphabet | the decoder | magic, varints, 63 bytes | 74 | 75 | 75 | — |
| terminator | — | the all-zeros path | 0 | 0 | 0 | yes |
| padding | — | high zero bits of the integer | 0 | 0 | 0 | yes |
| cluster → words index | — | from the map | 0 | 0 | 0 | yes |
| canonical codes | — | from the depths | 0 | 0 | 0 | yes |
| program code | the library | — | 2,048 | 2,048 | 2,048 | — |
| **total** | | | | **16,141** | **31,377** | **32,793** |

The depth field is **four bits, always** (`MODEL_FORMAT.md` §3): the stored
value is `d − d_min` inside its own tree, and the offset is recovered from the
Kraft equality, so there is no width byte and no `d_min` field.  An unbiased
build does not fit four bits — one tree at 8192/32 spans 18 levels — so the
build searches for the least weight bias that holds every tree to a span of 15
(`MODEL_FORMAT.md` §3.1).  Measured, that costs 0.001 bits per identifier at the
operating point and nothing at the others, and it saves 1,156 B: the depths go
from 5,780 to 4,624 B.

Two differences from the earlier estimate of this table are worth naming,
because each was a formula that had drifted: the top stage carries the STOP leaf
(hence `k(k+1)` depths, not `k²`), and the header is charged at all.  The
earlier estimate's 16.6 / 32.5 / 36.9 kB become 16.1 / 31.4 / 32.8 kB measured.

What the quarter code would add — the map one bit wider, the top stage doubled,
1.7 kB at the operating point — and what it buys are in
[`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md); it is not shipped.

### 5.2 The flat yardstick

One tree per left cluster over *all* `V` words — `k·V` depths — is the code
`ENCODING.md` §2 describes if the factorisation is removed.  It is not
shippable, and `--flat` measures it under the same convention so the factored
code can be bounded against it:

| point | flat bits/id | flat ≤ 64 | flat file | factored bits/id | factored ≤ 64 | factored file |
|---|---:|---:|---:|---:|---:|---:|
| 4096/16 | 46.612 | 83.1 % | 52,870 B | 48.982 | 80.5 % | 14,093 B |
| 8192/16 | 43.333 | 86.9 % | 123,401 B | 45.677 | 84.5 % | 29,329 B |
| 8192/64 | 42.134 | 88.4 % | 420,361 B | 44.952 | 85.3 % | 33,321 B |

At 8192/16 the flat codebook alone is `k·V` depths — 98,304 B at a measured
6-bit field, against 4,232 B for the factored bottom and top trees — so with the
maps equal at 4,096 B the flat file is **123,401 B against 29,329 B**.  It buys
2.344 bits/identifier and 2.4 fit points, which on this frontier's cheap band of
1–5 kB a point is worth 2–12 kB: the flat code pays 94 kB for what the frontier
sells for a tenth of that.  That is domination, not a trade, and it gets worse
as `k·V` grows — at 8192/64 the flat file is 420,361 B for 2.818 bits (39 kB a
point at 8192/16, 124 kB a point at 8192/64).  It also needs a wider depth
field: the flat code's deepest leaf is 33 levels, so its depths take 6 bits
where the factored model's take 5.

### 5.3 The fit-rate convention

The shipped criterion is the factored Huffman code with the zero-weight STOP leaf
and the free trailing zeros.  Three consequences for every fit rate quoted here:

* **Measure bits up to the last 1**, not the sum of codeword lengths.  The
  canonical form is the integer, and its binary length stops at its highest set
  bit; a summed length over-counts by ~1 bit/identifier (`ENCODING.md` §2).
* **The terminator's transition is not paid.**  The STOP leaf's codeword is the
  all-zeros path, and the trailing zeros of the last real codeword are not
  stored either: together they are worth 2–3 bits per identifier against a code
  that has to spend bits on the end of the identifier (`CODING_OVERHEAD.md`).
* **Every number in §5.1, §5.2, §6 and §7 is measured**, by the same script, on
  the same held-out set, from the packed file.  Nothing in this note is an
  ideal length any more.

### 5.4 The word list is in creation order, and cannot be permuted

**The word list is in *creation* order, and that is not frequency order.**  The
greedy rule selects the most frequent *pair* of adjacent symbols, so the sequence
of **selection counts** is monotone non-increasing — but a word's count in the
**final** segmentation is not, because an early word keeps being absorbed into
longer words later.  Measured on the three sample-20 builds: 49.6 / 49.0 / 48.9 %
of adjacent pairs rise, with a mean rank displacement of 17.9 / 16.7 / 15.8 % of
`V` (`scripts/wordlist_order.py`).

The counterexample is stark.  The first created words are `er` 66 665,
`on` 29 190, `es` 51 855, `at` 29 429, `in` 37 791, `en` 28 996 — so `on` was
merged *before* `es`, and at that moment `on` was the more frequent pair, yet in
the final segmentation `es` outnumbers it 1.8 to 1, because `on` is absorbed into
longer words (`only`, `once`, `control`, …) far more heavily.

The order is semantic — the tokeniser merges the lowest-ranked adjacent pair
first — so it cannot be renumbered without changing the tokenisation, and
storing the permutation would cost `V log₂V` bits, more than the depth table
itself.  The depths inherit the order, so §3's "in label order" means "in
creation order", and the depth table carries whatever depth distribution the
words happen to have.

## 6. The frontier, measured

Every point below is a packed model file from `scripts/model_size.py`, decoded
and scored on the 10× held-out set (stride 10, `n = 42,268`), one map, `q = 1`,
seed 1.  Dominated points are removed: a point is kept if no cheaper point is at
least as good.

| bytes | `V` | `k` | bits/id | fit ≤64 | fit ≤128 | kB/pt to next |
|---:|---:|---:|---:|---:|---:|---:|
| 13,481 | 4,096 | 8 | 49.105 | 80.4 % | 98.3 % | 11.8 |
| 14,093 | 4,096 | 16 | 48.982 | 80.5 % | 98.3 % | 10.3 |
| 16,157 | 4,096 | 48 | 48.704 | 80.7 % | 98.4 % | 3.1 |
| 17,061 | 4,096 | 64 | 48.531 | 81.0 % | 98.4 % | 10.0 |
| 19,951 | 6,144 | 4 | 48.661 | 81.3 % | 98.5 % | 0.4 |
| 20,149 | 4,096 | 96 | 47.934 | 81.7 % | 98.5 % | 1.0 |
| 20,745 | 6,144 | 8 | 47.542 | 82.3 % | 98.6 % | 2.3 |
| 21,613 | 6,144 | 16 | 47.162 | 82.7 % | 98.6 % | 2.0 |
| 22,545 | 6,144 | 24 | 46.735 | 83.2 % | 98.7 % | 1.8 |
| 22,773 | 6,144 | 32 | 46.646 | 83.3 % | 98.8 % | 8.5 |
| 25,093 | 6,144 | 64 | 46.278 | 83.6 % | 98.8 % | 4.9 |
| 28,205 | 8,192 | 8 | 46.013 | 84.2 % | 98.9 % | 5.2 |
| 29,271 | 8,192 | 12 | 45.775 | 84.4 % | 98.9 % | 0.6 |
| 29,329 | 8,192 | 16 | 45.677 | 84.5 % | 98.9 % | 3.5 |
| 30,517 | 8,192 | 24 | 45.453 | 84.9 % | 99.0 % | 2.8 |
| 30,745 | 8,192 | 32 | 45.218 | 85.0 % | 99.0 % | 8.2 |
| 33,321 | 8,192 | 64 | 44.952 | 85.3 % | 99.0 % | 17.5 |
| 36,921 | 8,192 | 96 | 44.926 | 85.5 % | 99.0 % | 25.8 |
| 40,522 | 8,192 | 128 | 44.724 | 85.6 % | 99.1 % | — |

Fit ≤128 is saturated (98.3–99.0 % everywhere), so every trade here is a 64-bit
trade, and **the frontier is the measured Huffman code, not a reference**: the
arithmetic accounting that used to stand in for it has been retired, because the
format no longer contains an arithmetic coder (§4) and a table nobody can ship
was being read as if it were the model.

Four things follow.

* **The cheap stretch is 20.1–22.8 kB, at 1.0–2.3 kB a point.**  4096/96 →
  6144/8 → 6144/16 → 6144/24 → 6144/32 are five files inside 2.6 kB that buy
  1.6 points.  Above that the price steps up to 8.3 kB a point (22,773 →
  25,093 B) and then to 4.9 and 8.3 at the far end, because the `k²` top stage
  and the `k`-wide labels take over from the word list.
* **The best single step on the curve is 8192/8 → 8192/12**: 1,066 B buys 0.2
  points at 5.2 kB/pt, and then 58 B buys a further 0.1 point at 0.6 kB/pt, the
  cheapest point per point anywhere.  The whole 4,096 → 6,144 jump at matched
  `k = 32`, 14,997 → 22,773 B, buys 2.2 bits and 2.8 fit points — 3.5 kB per bit
  and 2.8 kB per point — because the bigger word list pays twice: better tokens
  *and* a `k` that can be coarser.
* **`V = 6,144` is the cheapest way to 81.3 %.**  6144/4 costs 19,951 B; 4096/64
  reaches only 81.0 % for 17,061 B, and 4096/96 reaches 81.7 % for 20,149 B but
  costs 4.1 kB a point on the way there.
* **`V = 8,192` is worth its word list from 28 kB up.**  8192/8 (28,205 B,
  84.2 %) beats 6144/64 (25,093 B, 83.6 %) by 0.6 points for 3.1 kB — 4.9 kB/pt,
  in the band — and nothing below 28 kB reaches 84 %.

### The frontier along `k` — the measured slices

The same files, read along `k` at fixed `V`.  The local slope is what prices a
change made *inside* a model (the shared clusters, the quarters), and it is the
number the other notes charge against.

`V = 4,096`:

| `k` | model file | bits/id | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 8 | 13,481 B | 49.105 | 80.4 % | 98.3 % |
| 16 | 14,093 B | 48.982 | 80.5 % | 98.3 % |
| 24 | 14,769 B | 48.882 | 80.5 % | 98.4 % |
| 32 | 14,997 B | 48.866 | 80.5 % | 98.4 % |
| 48 | 16,157 B | 48.704 | 80.7 % | 98.4 % |
| 64 | 17,061 B | 48.531 | 81.0 % | 98.4 % |
| 96 | 20,149 B | 47.934 | 81.7 % | 98.5 % |
| 128 | 23,750 B | 47.770 | 81.9 % | 98.5 % |

`V = 6,144`:

| `k` | model file | bits/id | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 4 | 19,951 B | 48.661 | 81.3 % | 98.5 % |
| 8 | 20,745 B | 47.542 | 82.3 % | 98.6 % |
| 16 | 21,613 B | 47.162 | 82.7 % | 98.6 % |
| 24 | 22,545 B | 46.735 | 83.2 % | 98.7 % |
| 32 | 22,773 B | 46.646 | 83.3 % | 98.8 % |
| 64 | 25,093 B | 46.278 | 83.6 % | 98.8 % |
| 96 | 28,437 B | 46.174 | 83.7 % | 98.8 % |

`V = 8,192`:

| `k` | model file | bits/id | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 4 | 27,155 B | 46.579 | 83.6 % | 98.8 % |
| 6 | 28,190 B | 46.846 | 83.4 % | 98.8 % |
| 8 | 28,205 B | 46.013 | 84.2 % | 98.9 % |
| 12 | 29,271 B | 45.775 | 84.4 % | 98.9 % |
| 16 | 29,329 B | 45.677 | 84.5 % | 98.9 % |
| 24 | 30,517 B | 45.453 | 84.9 % | 99.0 % |
| 32 | 30,745 B | 45.218 | 85.0 % | 99.0 % |
| 48 | 32,417 B | 45.218 | 85.0 % | 99.0 % |
| 64 | 33,321 B | 44.952 | 85.3 % | 99.0 % |
| 96 | 36,921 B | 44.926 | 85.5 % | 99.0 % |
| 128 | 40,522 B | 44.724 | 85.6 % | 99.1 % |

| step | Δbits | Δbytes | kB/bit | Δ fit ≤64 | kB per point |
|---|---:|---:|---:|---:|---:|
| 8,192: 4→6 | +0.267 | +1,035 | — | -0.22 | — |
| 8,192: 6→8 | -0.833 | +15 | 0.0 | +0.84 | 0.0 |
| 8,192: 8→12 | -0.238 | +1,066 | 4.5 | +0.20 | 5.2 |
| 8,192: 12→16 | -0.098 | +58 | 0.6 | +0.10 | 0.6 |
| 8,192: 16→24 | -0.223 | +1,188 | 5.3 | +0.34 | 3.5 |
| 8,192: 24→32 | -0.235 | +228 | 1.0 | +0.08 | 2.8 |
| 8,192: 32→48 | +0.001 | +1,672 | — | +0.07 | 25.2 |
| 8,192: 48→64 | -0.266 | +904 | 3.4 | +0.25 | 3.7 |
| 8,192: 64→96 | -0.026 | +3,600 | 138.5 | +0.21 | 17.5 |

Four things follow.

* **The knee is at `k = 32` and it is shallow.**  16 → 32 buys 0.4 points for
  1,416 B (3.4 kB/pt); 32 → 64 buys 0.3 for 2,576 B (8.3 kB/pt); 96 is another
  3.6 kB for 0.2.  So a change that costs a kilobyte *inside* the model must buy
  about 0.3 points to be worth making, and one that costs 5 kB must buy a point.
* **The old turnover at `k = 32` was an artefact of the terminator.**  With the
  stop inside the bottom trees, each top tree carried a right cluster for it and
  the rounding at fine `k` ate the gain; with the STOP leaf carrying it for free
  the curve is monotone through 96.  The operating point stays at 32 because
  that is where the price per point leaves the cheap band, not because the curve
  turns over.
* **Below `k = 8` the curve is unstable.**  8192/6 is worse than 8192/4 and
  4096/24 no better than 4096/16: k-means lands in a different local optimum from
  seed to seed at coarse `k`, and one degenerate cluster of 16 words at 8192/8
  produces the widest tree on the grid.  Nothing below `k = 12` is worth
  quoting to better than half a point.
* **Every point round-trips.**  42,268 held-out identifiers per file decode
  through the packed bytes with zero failures.

### `V` against `k` at matched size

At `k = 32`, the word list buys 2.2 bits for 7.8 kB from 4,096 to 6,144 (3.5 kB
per bit) and 1.4 bits for 8.0 kB from 6,144 to 8,192 (5.6 kB per bit).  Inside a
model, `k` costs 3.4 kB per fit point up to 32 and 8.3 beyond it.  So a bigger
word list is still the cheaper way to buy a point — 2.8 and 4.9 kB against 3.4
and 8.3 — but by only 1.2–1.7×, not the "2–6×" the formula accounting claimed.  Why `V` is different
is mechanical: a bigger word list shortens identifiers (held-out mean length
4.70 → 4.05 tokens from 4,096 to 8,192) and the 64-bit budget is dominated by
the *long* identifiers, so `V` attacks the part of the distribution the
threshold measures, while a finer `k` only shaves the conditional entropy of
tokens already inside an identifier.

## 7. The size oracle

The structure in §1 and the oracle answer different questions.  The structure
says **what is stored**; the oracle says **how many bytes it takes**, and it
measures whatever structure it is given — the factored code, the flat variant,
the quarter code, a second map — from one script and one held-out set.  The
byte figures above are the oracle's; the formulas that preceded it had drifted
three times (a double-charged bottom stage, a missing label map, a "bracket
versus length table" claim that did not survive re-reading), which is why the
model is no longer priced by formula anywhere in this note.

1. `scripts/model_size.py` — the size **oracle**.  Build at `(V, k)`, write the
   YAML model, pack it to the binary form of
   [`MODEL_FORMAT.md`](MODEL_FORMAT.md), report actual bytes per section, decode
   held-out identifiers and assert losslessness, and report the code's real
   bits/identifier from the decoded artefact.  The packing rule is the codec of
   H12, so the oracle and the published file share one implementation.
2. One **inventory table** in this note: object / who stores it / how / bytes at
   4096/16, 8192/16, 8192/32 / derivable at load?  §5.1 is it.
3. The **depth store**: measure the depth span of every bottom and top tree on
   the grid.  That sets the weight bias the build searches for and the four-bit
   field, and the raw maxima show that no tree needs length limiting; the top
   stage is `k(k+1)` packed depths.  It also confirms that the depth is carried per word: the
   leaf-list-free `2 + log₂k` form fails because a depth-1 leaf can only sit at
   an end of its subtree, so the Huffman depth sequence need not be realisable
   in an arbitrary order.
4. **Re-derive** every table from the oracle: the frontier here,
   `CLUSTER_QUARTERS.md` (`CF`/`CQF`/`W`), `WORDLIST_BUDGET`, `CLUSTER_WORDS`,
   `SHARED_CLUSTERS`, `PRUNE_WORDS`, `DICTIONARY_RULES` and `SMALL_DICT`'s price
   row.  The dictionary term must be charged in `shared_clusters.py`,
   `quarter_accounting.py` and the corresponding comparisons, which still quote
   code-side bytes; their verdicts are unaffected (they are within-`V`), but any
   cross-`V` price must carry the term.
5. **The fit-rate convention** of §5.3, applied at every point.  It has already
   overturned `q = 2` — once the terminator is free the quarters are worth 0.12
   bits and 0.1–0.3 fit points for 1,184–1,664 B, i.e. 10–14 kB a bit, so
   `q = 1` ships (`CLUSTER_QUARTERS.md`) — and it moved the operating point from
   `k = 16` to `k = 32`.
6. **Retire** the superseded numbers: `README.md`'s status line, and any table
   not produced by the oracle.

The outcome is a model stated as one `(V, k, q)` triple and one file.

**What the oracle measured** (one map, zero-weight terminator, canonical codes
from the packed file — `MODEL_FORMAT.md` §3), shipped `q = 1`:

| point | model file | + library | bits/id | fit ≤ 64 | fit ≤ 128 |
|---|---:|---:|---:|---:|---:|
| 4096/16 | 14,093 B | 16.1 kB | 48.982 | 80.5 % | 98.3 % |
| 8192/16 | 29,329 B | 31.4 kB | 45.677 | 84.5 % | 98.9 % |
| **8192/32** | **30,745 B** | **32.8 kB** | **45.218** | **85.0 %** | **99.0 %** |
| 8192/64 | 33,321 B | 35.4 kB | 44.952 | 85.3 % | 99.0 % |

**The `k` curve, measured**, at `V = 8,192`, seed 1:

| `k` | model file | bits/id | fit ≤64 | step from the row above |
|---:|---:|---:|---:|---|
| 8 | 28,205 B | 46.013 | 84.2 % | — |
| 12 | 29,271 B | 45.775 | 84.4 % | +1,066 B, +0.20 pt, 5.2 kB/pt |
| 16 | 29,329 B | 45.677 | 84.5 % | +58 B, +0.10 pt, 0.6 kB/pt |
| 24 | 30,517 B | 45.453 | 84.9 % | +1,188 B, +0.34 pt, 3.5 kB/pt |
| **32** | 30,745 B | 45.218 | 85.0 % | +228 B, +0.08 pt, 2.8 kB/pt |
| 48 | 32,417 B | 45.218 | 85.0 % | +1,672 B, +0.07 pt, 25.2 kB/pt |
| 64 | 33,321 B | 44.952 | 85.3 % | +904 B, +0.25 pt, 3.7 kB/pt |
| 96 | 36,921 B | 44.926 | 85.5 % | +3,600 B, +0.21 pt, 17.5 kB/pt |

The operating point is **`V = 8,192, k = 32`**: 30,745 B, 45.218 bits, 85.0 % in
64 bits, 99.0 % in 128.  `k = 48` is a dud at seed 1 (no gain for 1.7 kB) and
`k = 64` is back in band, which is the seed noise these single-seed points
carry: the honest reading is a flat stretch from 32 to 64, 2.6 kB for 0.3
points, and a dead zone after that.

**The `V` curve, measured**, at `k = 32`:

| `V` | model file | bits/id | fit ≤64 | word list share |
|---:|---:|---:|---:|---:|
| 511 | 2,114 B | 65.535 | 60.3 % | 44 % |
| 4,095 | 14,997 B | 48.866 | 80.5 % | 65 % |
| 6,143 | 22,773 B | 46.646 | 83.3 % | 67 % |
| 8,191 | 30,745 B | 45.218 | 85.0 % | 68 % |

The steps cost 3.5 and 5.6 kB per bit, against the 2.8–8.3 kB the `k` direction
charges per fit point at matched `V`; a bit is worth about 1.2 fit points at this
size, so the ladder is running out rather than exhausted.  The next rung,
`V = 12,288`, needs ~10.5 kB more rules at the measured 2.6 B per rule, plus
2.0 kB of depths and 2.6 kB of labels — 15 kB — and the marginal value of words
is falling, so it cannot buy more than ~1.5 bits: 10 kB per bit or worse, well
above the 3–5 kB per bit the frontier sells for.  Extrapolated, not built;
[`WORDLIST_BUDGET.md`](WORDLIST_BUDGET.md) has the ladder.

Four more things came out of building it, none of which the formulas could have
shown:

* **The terminator had to move to the top stage.**  A two-stage code cannot put
  the all-zeros path on the stop's right cluster without recoding the top stage,
  so each top tree gets a zero-weight STOP leaf instead.  Cost: one depth per top
  tree; saving: the whole terminator.
* **The corpus's stop token is not a symbol of the file.**  Its row of the
  adjacency matrix is the **start state** (the first token's distribution) and
  its column does not exist, because nothing is coded after the end.  So the
  matrix is `V0 × (V0−1)`, the bottom trees carry no terminator, and the
  dictionary loses 36 B because every child bound is one smaller
  (`MODEL_FORMAT.md` §1).  Measured against the same build with the stop kept,
  the file is 41 B smaller and the code is 0.9 bits/identifier better at
  `V = 512`, `k = 8` (66.04 against 66.93).
* **One map is worth its constraint, and more so as `k` grows.**  A file with a
  second map adds one label per word — 2,048 B at 4096/16, 4,096 B at 8192/16,
  5,120 B at 8192/32 — and buys 0.012 / 0.549 / 0.328 bits per identifier:

  | point | one map | two maps | the map costs | for | per bit | fit ≤64 |
  |---|---:|---:|---:|---:|---:|---:|
  | 4096/16 | 14,093 B | 16,141 B | 2,048 B | 0.011 bits | 186 kB | 80.5 → 80.6 % |
  | 8192/16 | 29,329 B | 33,425 B | 4,096 B | 0.549 bits | 7.5 kB | 84.5 → 85.1 % |
  | 8192/32 | 30,745 B | 35,865 B | 5,120 B | 0.329 bits | 15.6 kB | 85.0 → 85.3 % |

  The frontier sells bits for 3–5 kB (§6), so the second map is 1.5–2.5× too
  dear at `k = 16` and 3–5× too dear at `k = 32`, and its price is rising: the
  bits it buys fall as `k` grows while the map grows with it.  The constraint is
  therefore not a compromise to be weighed — it is what makes a fine `k`
  affordable, and the measurement says so at both 8192 points
  ([`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md)).
* **The quarter code does not pay once the terminator is free.**  The arithmetic
  accounting credited it 1.10 bits and 0.9 points because both codes were paying
  for the stop there; with the STOP leaf the same build is worth 0.12 bits and
  0.1 points, for 1,536 B — 13 kB a bit, three times the frontier's own price.
  An accounting that charges a terminator to the word step will over-reward
  every scheme that refines the word step
  ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)).

## 8. What it shows

* **The rule table is two thirds of the model** — 20.9 of 30.7 kB at the
  operating point, well ahead of the map (5.1 kB) and the depths (4.6 kB).  The
  ladder is within 5 % of the empirical entropy of the index stream, so there is
  nothing left there; the real lever is a smaller vocabulary, which is the
  `V`-against-`k` trade above.
* **The frontier is 14.1 kB / 80.5 %, 22.5 kB / 83.2 %, 30.7 kB / 85.0 %,
  33.3 kB / 85.3 %, 36.9 kB / 85.5 %** — the last point 2× the 20 kB goal, and all of them inside
  the "50 kB-ish is acceptable if it rescues the 64-bit set" band.
* **Size is not what costs the 64-bit set — clustering is.**  The full-table
  ceilings are 85–94 %; the shipped models fit 85.0 % (8192/32) and 84.5 %
  (8192/16).  The remaining gap is the membership structure, not the word list.
* **The next two objects are the map and the depths** (5.1 and 4.6 kB at the
  operating point).  `V · ⌈log₂ k / 8⌉` doubles by `k = 64`, so the map is what
  makes a fine `k` expensive, and it is what the shared cluster assignment buys
  down.  The depths are four bits, and the build searches for the least weight
  bias that holds every tree to a span of 15 (`MODEL_FORMAT.md` §3.1); that
  saves 1,156 B at no measured fit cost.

## Reproducing

```sh
# the size oracle: build, write the YAML, pack, decode, report (§6, §7)
python3 scripts/model_size.py --dir work/tw8192ns --k 32 --stride 10   # the shipped point
for d in "tw4096ns 8 16 24 32 48 64 96 128" "tw6144ns 4 8 16 24 32 64 96" \
         "tw8192ns 4 6 8 12 16 24 32 48 64 96"; do                    # the grid
  set -- $d; dir=$1; shift
  for k in "$@"; do
    python3 scripts/model_size.py --dir work/$dir --k $k --stride 10
  done
done
for d in "tw512ns 8" "tw512ns 16" "tw512ns 32"; do                   # the V ladder
  set -- $d
  python3 scripts/model_size.py --dir work/$1 --k $2 --stride 10
done
python3 scripts/model_size.py --dir work/tw8192ns --k 16 --q 2 \
        --stride 10          # the quarter code, priced but not shipped
python3 scripts/model_size.py --dir work/tw8192ns --k 32 \
        --assignment two --stride 10   # a second map, at the operating point
python3 scripts/model_size.py --dir work/tw8192ns --k 16 --flat   # §5.2 yardstick
python3 scripts/model_size.py --dir work/tw8192ns --k 32 --no-depth-bias  # §3's five-bit case
python3 scripts/model_size.py --self-test      # the MODEL_FORMAT.md §6 example

# the rule-pair grid of §4 and RULE_ENCODING.md
python3 scripts/rule_encoding.py --dir work/tw8192ns

# creation order vs frequency order
python3 scripts/wordlist_order.py --dirs work/tw4096ns,work/tw6144ns,work/tw8192ns

# the scatter plot in README.md (reads the frontier table of §6)
python3 scripts/frontier_plot.py --doc docs/MODEL_BUDGET.md --out docs/frontier.svg
```

## Pre-grid record (historical, not comparable)

Before the 10-ecosystem corpus the frontier was measured on the older
vocabularies (`V = 2 104 / 4 478 / 11 758`) at stride 40 (`n = 5 739`) and priced
with the codebook accounting that has since been retired.  Those numbers are
**not** comparable with the tables in this note — different corpus, vocabulary
and accounting — and are kept only as the record of what was believed at the
time; nothing below or elsewhere is derived from them:

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
* Pricing the model with arithmetic code lengths — retired everywhere.  The
  format is a Huffman code, the rule table is a static geometric ladder, and a
  size that no decoder could reach was being read as if it were the model
  (§7, step 6).
* A 4-bit depth field without the weight bias — the span is 18 levels at the
  operating point, so the field would have to hold a depth of 18 and no width
  below five bits works.  The bias is what buys the field
  (`MODEL_FORMAT.md` §3.1).
