# Cluster quarters

Status: **`q = 1` ships; `q = 2` and `q = 4` are rejected on the measured
numbers.**  The "quarter" idea buys back part of the word-step rounding loss by
splitting each left cluster's word tree into `q` right clusters.  The name is
historical: a quarter is *any* finer right cluster, so `q = 2` gives halves.  The
idea changes the top stage from `k` leaves to `q·k` and leaves the encoding
untouched (`ENCODING.md` §§2–4); the accounting, the measurements and the price
are below.  The arithmetic accounting (stop charged) adopted `q = 2` on 0.9 fit
points for 1,184 B.  Under the shipped convention — a zero-weight terminator in
the top stage — the same build buys 0.13 points and 0.10 bits for those bytes,
because the terminator was most of what the quarters were buying.  The model file
still carries the grouping as one label per word when `q > 1`
(`MODEL_FORMAT.md`) — the right clusters are subtrees of the Huffman build, not
of the canonical tree a depth-only file implies, so the grouping cannot be read
off the tree — which costs 1.7 kB at the operating point ("The structural cost"
below).  Measured by `scripts/model_size.py` at the operating point (`8192/32`),
the shipped `q = 1` file is **32,126 B** and fits **84.8 %** of held-out
identifiers in 64 bits; `q = 2` is 33,790 B and 84.7 %, so at the operating point
the quarters lose on both axes (`MODEL_BUDGET.md` §7).

The factorised model needs `P(right cluster | left cluster)` before
`P(word | right cluster)`.
The flat model needs a tree per left cluster over all `V` words, i.e. `k` trees
of `V` leaves — `k·V` code lengths, about 450 kB at `V = 4,096, k = 64`, which
is out of the question.

The idea: **stop each tree early.**  Build the tree for
`P(word | right cluster)` and halt when `q` survivors remain (the *quarters* of
the title; each survivor is one right cluster, with no special status in the
shipped code).  Then encode `P(right cluster | left cluster)` with a tree of
`q·k` leaves.  Each of the `k` left clusters gets its own top tree, so right
clusters from *different* left clusters can be paired when their probabilities
are similar — which is exactly the pairing that the two-level factorisation
cannot do.

The mechanism is the classical Huffman redundancy bound: a tree's expected
redundancy is at most about its largest leaf probability, plus a small constant.
Splitting a right cluster into `q` pieces divides its largest leaf probability
by up to `q`, so the word-step penalty (measured at 0.173 bits/token) should shrink,
while the cluster-step penalty (0.036) hardly moves.

## The size accounting, checked

The formulas as stated:

```
CF  = k (2 (k - 1)   +  k log k)    + (2 (V - k)   + V log V)
CQF = k (2 (q k - 1) + q k log q k) + (2 (V - q k) + V log V)
W   = k (2 (V - 1)   +  V log V)
```

Notes on the accounting:

* **The bottom stage does not grow.** `2(V − qk)` instead of `2(V − k)` *saves*
  `2(q−1)k` bits — a few hundred bytes.  All of CQF's cost is in the top stage,
  which is `k·qk·log(qk)` — quadratic in `k`, and in `q` linear only up to the
  logarithm.  The increments over CF are 1.1 kB (`q = 2`) and 3.6 kB (`q = 4`)
  at `k = 32`, and 5.0 / 15.9 kB at `k = 64`: **`q = 4` costs about three times
  what `q = 2` costs**, and doubling `k` roughly quadruples both.  (An earlier
  draft said "a quarter"; that was wrong — `q = 2`'s top stage is 44 % of
  `q = 4`'s.)
* **What the `2` is: a bracket string.**  A full binary tree with `L` leaves has
  `L − 1` internal nodes.  Write each internal node as `(… )` around its two
  children and each leaf as its word index, and the tree becomes a depth-first
  string.  Keep only the brackets and you have the *shape* in exactly `2(L−1)`
  bits — enough to recover every code length.  Keep only the indices and you
  have the *leaf list* in depth-first order — enough to recover the assignment.
  Either alone is useless; together they reconstruct the tree exactly.  So
  `2(V−k)` is **two bits per internal node** across all `k` bottom trees, not
  "two bytes per rule", and `V log V` is the leaf list.

  It is **not the form to ship**, and it is not the smallest.  The bracket form
  pays `log₂V + 2` bits per leaf: the +2 amortises one internal node per leaf,
  and the `log₂V` names every leaf by its word index.  A **depth table** pays
  `log₂⌈max depth⌉ + log₂k` bits per leaf — 9 bits at `V = 8192, k = 16`
  (5 for a depth ≤ 31, 4 for the map) against 15 — and needs no tree walk.

  The reason the leaf list cannot simply be dropped, for `2 + log₂k`, is that the
  shape fixes the depths **in depth-first order** and an arbitrary leaf order
  need not admit that depth sequence: a depth-1 leaf can only sit at an end of
  its subtree, so a word in the middle of the list cannot take the shortest code.
  Permuting equal-depth leaves and reflecting subtrees only reaches orders the
  shape already admits; it cannot manufacture one.  So the depth has to be
  carried **per word**, not derived from the shape — `log₂ depth + log₂k` is
  available, `2 + log₂k` is not.

  The figures below are therefore an *upper* bound on the codebook; the shipped
  store is the packed depth table, and `MODEL_BUDGET.md` prices it.
* **One term is missing: the word→left-cluster map.**  The top stage is indexed
  by the left cluster of the *current* word, and neither formula charges the
  `V log₂k` bits that map needs; the leaf list only implies the *right*-cluster
  side.  If the shared cluster assignment is adopted, one map serves both and
  the term is already paid — one more reason that idea is attractive.
* **`V log V` is right, and it is what makes the scheme work.**  An earlier draft
  of this note tried to charge `Σ_j V_j log V_j ≈ V log(V/qk)` instead and to add
  a separate word→cluster map.  That double-charges: with every leaf annotated by
  its word index, the *map is implied* — which tree a word's leaf sits in is its
  right cluster, and its position in that tree is its rank.  The decomposition is
  exact when the groups are equal-sized: `Σ_j V_j log V_j + V log q ≈ V log V`.
  The same reading applies to CF (`V log V` implies the word→right-cluster map),
  which is why the two schemes differ *only* through the top stage.

With the stated formulas:

| `V` | `k` | CF | CQF (`q = 2`) | CQF (`q = 4`) | W |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 32 | 8,048 | 9,192 | 11,736 | 229,368 |
| 4,096 | 64 | 11,232 | 16,336 | 27,568 | 458,736 |
| 8,192 | 32 | 16,240 | 17,384 | 19,928 | 491,512 |
| 8,192 | 64 | 19,424 | 24,528 | 35,760 | 983,024 |

(bytes, exact; the earlier draft of this table quoted rounded kB and was off
by up to 0.8 kB in the CQF columns)

So the honest description is "`O(k² log k)` larger than CF", and at `k = 64`
that is a doubling of the model — not "barely bigger".  The comparison that
matters is therefore **bytes versus fit**, not bytes versus bytes: CQF has to
out-perform re-spending the same 8–16 kB on a longer word list or a finer `k`,
which is the frontier measured in `WORDLIST_BUDGET.md` / `MODEL_BUDGET.md`.

## The accounting check, run

`scripts/quarter_accounting.py` computes the three layouts exactly from the
counts — no sampling, no held-out set — as Huffman costs (so the rounding is
real, not modelled).  The first run was at the testing vocabulary; those numbers
are in [`SMALL_DICT.md`](SMALL_DICT.md) and none of them is used here.

`V = 4096`, `k = 32`, `kappa = 300`, 4.02M identifiers, 22.9M transitions:

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **50.122** | — | 229,368 |
| CF | 52.426 | +2.304 | 8,048 |
| CQF `q = 2` | 51.615 | +1.493 | 9,192 |
| CQF `q = 4` | 51.480 | +1.358 | 11,736 |

and the mechanism, checked to three decimals against the identity above:

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 22.948 | 18.055 | +4.893 | 5.704 | **+0.811** | +1,144 |
| 4 | 27.563 | 18.055 | +9.508 | 10.454 | **+0.946** | +3,688 |

The `kappa` prior makes every right cluster non-zero, so the Huffman rounding is small
here and these are close to rounding-free numbers.

**The mechanism is real, and the fraction grows with the model.**  CQF recovers
**35% (`q = 2`) and 41% (`q = 4`)** of the flat → CF penalty, and the amounts are
exactly the expensive within-cluster merges.  An earlier draft guessed a ~1.2-bit
penalty at the canonical grid, so that a small recovered fraction would give
~0.22 (`q = 2`) and ~0.36 (`q = 4`) bits.  **That guess was wrong in both
terms**: the penalty is *larger* (2.3 bits at `k = 32`, 3.0 at `k = 64`) and the
recovered fraction is *larger* too, because the within-cluster merge mass is nearly
independent of `k` while CF's cluster step is not.  The extrapolation in that
earlier draft is therefore too pessimistic: the word step is 66% of CF's cost
(34.371 of 52.426) and the expensive within-cluster merges are a larger share of it
the canonical grid.

The `k = 64` point (`V = 4096`, 4.02M identifiers) completes the picture:

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **49.328** | — | 458,736 |
| CF | 52.306 | +2.979 | 11,232 |
| CQF `q = 2` | 51.035 | +1.707 | 16,336 |
| CQF `q = 4` | 50.806 | +1.478 | 27,568 |

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 25.851 | 21.421 | +4.430 | 5.702 | **+1.272** | +5,104 |
| 4 | 30.171 | 21.421 | +8.751 | 10.251 | **+1.500** | +16,336 |

Two things to note, both against the earlier expectation:

* **The within-cluster merges are `k`-independent** — 5.704 / 10.454 at
  `k = 32`, 5.702 / 10.251 at `k = 64`.  They are a property of the tail of each
  right cluster's word distribution, not of how many right clusters there are.
  So the recovery
  *fraction* rises with `k` (35% → 43% for `q = 2`), because the penalty it is a
  fraction of grows (CF's cluster step 18.055 → 21.421 while the word step only
  falls 34.371 → 30.886).
* **The top stage increase is `k`-*sub*linear**: 4.893 → 4.430 for `q = 2` even
  though the top tree grows from 32 to 64 leaves.  It is charged as
  `H(right cluster | L) − H(cluster | L)`, and the extra distinction bites
  less once the right clusters are already fine.

Against bytes, though, the story is unchanged: the top stage is `k x kq`, so the
byte cost of the same 1.27 bits is 4.5x what it was at `k = 32`.

**Priced against the frontier**, using the slope measured two independent ways on
the canonical grid — `k`: 32 → 64 at `V = 4096` costs 4,088 B and buys 0.733
bits; `V`: 4,096 → 8,192 at `k = 64` costs 18,432 B and buys 3.34 bits — both
give **≈5.5 kB per bit**:

| config | CQF bytes over CF | bits it buys | bits the same bytes buy elsewhere | net |
|---|---:|---:|---:|---:|
| 4096, k=32, q=2 | +1.1 kB | **0.81** | 0.21 | **+0.60** |
| 4096, k=32, q=4 | +3.6 kB | **0.95** | 0.67 | +0.28 |
| 4096, k=64, q=2 | +5.0 kB | **1.27** | 0.91 | **+0.36** |
| 4096, k=64, q=4 | +16.0 kB | **1.50** | 2.89 | −1.39 |

So **CQF pays at `k = 32`**: `q = 2` comfortably (+0.60 bits equivalent), `q = 4`
marginally (+0.28).  At `k = 64` both `q = 2` (+0.36) and `q = 4` (−1.39) get
worse, but not for the reason guessed earlier: the bits it buys *grow* (1.27,
1.50) and the bytes grow faster.  Per kilobyte the buy is 0.71 bits/kB at
`k = 32, q = 2`, 0.25 at `k = 64, q = 2`, 0.09 at `k = 64, q = 4`, against a
frontier of ~0.18.  So `q = 2` is above the frontier at both `k`, by 4x and by
1.4x; `q = 4` is above it only at `k = 32`, by 1.5x.

These are Huffman costs on the *training* counts, so they are optimistic and
they carry no fit rate.  The decision rule is stated in fit rates, so the codes
were built and scored on held-out identifiers — that is the next section.

## The measured codes, held-out

`scripts/quarter_codes.py` constructs the four codes from the training counts and
scores them on `merged_validation.txt` at **stride 10 (42,268 identifiers)** —
the current re-measurement; the earlier pass used 4,227 identifiers.  Held-out
identifiers average 4.71 tokens at `V = 4096` and 4.06 at `V = 8192` against
5.70 in the corpus, so bits/identifier are not comparable *across* corpora, but
every comparison at one point is paired on the same identifiers.  The absolute
fit rates are 0.5–0.7 points lower than the 4,227-identifier pass read, which is
the sampling, not the model (see "The noise, measured").

`V = 4096, k = 32` (codes built on 4,019,467 identifiers, 22.9M transitions):

| scheme | bits/id | vs flat | fit<=64 | fit<=128 | model bytes |
|---|---:|---:|---:|---:|---:|
| flat (yardstick) | **49.654** | — | 80.6% | 98.5% | 229,368 |
| CF | 52.113 | +2.459 | 77.7% | 98.1% | 8,048 |
| CF, decoded arithmetically | 51.245 | +1.591 | 78.1% | 98.1% | 8,048 |
| CQF `q = 2` | 51.293 | +1.638 | 78.5% | 98.2% | 9,192 |
| CQF `q = 4` | 51.140 | +1.486 | 78.7% | 98.2% | 11,736 |
| `ref` (exact `P(v\|u)`) | 42.149 | −7.505 | 90.3% | 99.5% | 2,102,784 |

`V = 4096, k = 64`:

| scheme | bits/identifier | vs flat | fit<=64 | fit<=128 | model bytes |
|---|---:|---:|---:|---:|---:|
| flat | 48.783 | — | 81.7% | 98.7% | 458,736 |
| CF | 51.920 | +3.137 | 78.2% | 98.2% | 11,232 |
| CF, decoded arithmetically | 50.528 | +1.745 | 78.9% | 98.3% | 11,232 |
| CQF `q = 2` | 50.639 | +1.856 | 79.3% | 98.3% | 16,336 |
| CQF `q = 4` | 50.402 | +1.619 | 79.6% | 98.4% | 27,568 |
| `ref` | 42.149 | −6.634 | 90.3% | 99.5% | 2,102,784 |

`V = 8192, k = 64` (4,289,911 identifiers, 21.7M transitions):

| scheme | bits/identifier | vs flat | fit<=64 | fit<=128 | bytes |
|---|---:|---:|---:|---:|---:|
| flat | 46.181 | — | 84.9% | 99.1% | 983,024 |
| CF | 48.602 | +2.421 | 82.3% | 98.8% | 19,424 |
| CF, decoded arithmetically | 47.284 | +1.103 | 83.1% | 98.8% | 19,424 |
| CQF `q = 2` | 47.465 | +1.284 | 83.3% | 98.8% | 24,528 |
| CQF `q = 4` | 47.358 | +1.177 | 83.4% | 98.8% | 35,760 |
| `ref` | 39.949 | −6.232 | 93.1% | 99.7% | 8,400,896 |

Four readings:

* **The codes generalise and the accounting was honest.** Held-out CF is 0.31
  bits (4096/32) and 0.39 bits (4096/64) *below* the training-count Huffman cost
  (52.426 and 52.306), and the recovered fraction is the predicted one: 33% and
  40% at `k = 32` against the accounting's 35% / 41%; 41% / 48% at `k = 64`
  against 43% / 50%; 47% / 51% at `V = 8192, k = 64`.  Nothing here is a training
  artefact.
* **The code is worth a point on the threshold, not on the mean.** At
  `4096, k = 32` CQF `q = 2` and *arithmetic* decoding of the same tables have
  the same mean to 0.05 bits (51.293 vs 51.245 — CQF slightly *worse*) but their
  fit rates are not the same: **78.5% against 78.1%**, i.e. `+0.8 ± 0.1` against
  `+0.4 ± 0.1` points over CF.  The same pattern appears at `k = 64` (79.3 vs
  78.9) and at 8192/64 (83.3 vs 83.1).  So CQF is *not* "the two-stage Huffman
  code catching up to its own entropy" — an arithmetic decoder already does
  that, and it costs nothing in bytes.  CQF reshapes the cost distribution:
  Huffman lengths are not `−log₂ P`, they are short for the heavy symbols of a
  right cluster and long for the rare ones, which pulls identifiers toward the
  threshold even at the same mean.  But the size of that gain is **+0.2 to
  +0.4 pt**, not the +0.9 the 4,227-identifier pass reported: its paired
  standard error was ±0.2 pt, so that reading was noise.
* **Mean bits and fit rates agree in sign here, and disagree in size.** `q = 4`
  is better than `q = 2` on both statistics at all three points (51.140/78.7 vs
  51.293/78.5; 50.402/79.6 vs 50.639/79.3; 47.358/83.4 vs 47.465/83.3) — for
  3.2× the bytes.  A 0.1-bit mean gain buys 0.1–0.3 points; the choice between
  `q = 2` and `q = 4` is therefore a question of price, not of sign.
* **The arithmetic bound is far away.** `ref` is 7.51 bits below flat at
  `V = 4096, k = 32` (6.63 at `k = 64`, 6.23 at 8192) for a `V x V` table of
  2.1 MB / 8.4 MB.  The flat → CF penalty CQF attacks (2.4–3.1 bits) is
  therefore only a fraction of what the factorisation loses overall; the rest is
  within-cluster resolution on both sides, which is a `k` question and not a
  quarters question.  CQF recovers most of *the CF penalty*, not most of the gap
  to optimal.

**Priced in fit rates** (CQF's byte delta over CF is the code-only accounting of
the tables above; the local frontier slope is the best measured neighbour in
the same accounting, from [`MODEL_BUDGET.md`](MODEL_BUDGET.md)'s stride-10
`k`-sweep):

| config | fit<=64 | vs CF | bytes over CF | kB per point | local frontier |
|---|---:|---:|---:|---:|---:|
| 4096, k=32, q=2 | 78.5% | **+0.8** | +1,144 | **1.4** | 4.6 (k 32→48), 5.4 (48→64) |
| 4096, k=32, q=4 | 78.7% | +0.9 | +3,688 | 4.1 | |
| 4096, k=64, q=2 | 79.3% | +1.1 | +5,104 | 4.6 | 5.4, 14.8 (k 64→96) |
| 4096, k=64, q=4 | 79.6% | +1.4 | +16,336 | 11.7 | |
| 8192, k=64, q=2 | 83.3% | +0.9 | +5,104 | 5.7 | 14.8 (k 64→96 at 4096) |
| 8192, k=64, q=4 | 83.4% | +1.1 | +16,336 | 14.9 | |

The decision rule of step 6 is "adopt only if, at matched total bytes, it beats
the best CF configuration on the fit rates by more than the frontier's noise".
Stated as domination, which avoids the interpolation entirely:

| pair | CQF option | CF option | winner |
|---|---|---|---|
| `V = 4096` | `k = 32, q = 2`: **78.5%** at 18,544 B | `k = 64`: 78.2% at 21,488 B | CQF, by 0.3 pt and 2.9 kB |
| `V = 4096` | `k = 64, q = 2`: **79.3%** at 26,592 B | `k = 128`: 79.6% at 34,784 B | CF, by 0.3 pt for 8.2 kB (27 kB/pt — worse than the frontier) |
| `V = 8192` | `k = 64, q = 2`: **83.3%** at 45,024 B | `k = 128`: 83.6% at 54,240 B | CF, by 0.3 pt for 9.2 kB (31 kB/pt) |

The comparator is the Huffman product.  Against *arithmetic* decoding the
picture is sharper, and it is the one that decides the verdict:

| | CQF `q = 2` fit | arithmetic fit | CQF's margin | bytes | kB per point |
|---|---:|---:|---:|---:|---:|
| 4096, k=32 | 78.5% | 78.1% | **+0.4 pt** | +1,144 | **2.9** |
| 4096, k=64 | 79.3% | 78.9% | +0.4 | +5,104 | 12.8 |
| 8192, k=64 | 83.3% | 83.1% | +0.2 | +5,104 | 25.5 |

So CQF `q = 2` **wins as a `k = 32` Huffman-only** optimisation: worth
+0.4 fit points there for 1,144 B — 3–4× cheaper per point than the `k`
direction (4.6–5.4 kB/pt in the middle of the 4096 sweep) and 1.4× cheaper than
the frontier even on its own CF-relative reading (+0.8 pt for 1.4 kB).  At
`k = 64` and above it is a wash: the same +0.4 points cost 12.8–25.5 kB/pt, and
against the CF-at-`k`-frontier reading the alternative is just as good.
`q = 4` is **rejected**: at `k = 32` it buys only 0.2 pt more fit than `q = 2`
for 3.2× the bytes (4.1 against 1.4 kB/pt relative to CF), and at `k = 64` it
costs 11.7–14.9 kB/pt for 0.1–0.3 points.  Since `ENCODING.md` §1–3 chooses code
lengths over probabilities for the decoder's sake, the `k = 32` gain is real and
conditional: it exists *because* the product is a Huffman product.

(The byte figures here are this note's codebook accounting; the dictionary term,
and the full arithmetic model it belongs to, are in
[`MODEL_BUDGET.md`](MODEL_BUDGET.md).  Every comparison in this section is
within one `V`, so the rule table cancels and the omission does not move the
ordering.)

**The point the accounting liked: `V = 8192, k = 16`.**  The frontier measurement
moved the cheap model down to a coarse `k` at the largest vocabulary, which
changes CQF's economics because the top stage is `k x kq` — at `k = 16, q = 2` it
is 16 × 32 leaves (the shipped build, `k = 32, q = 1`, is 32 trees of 32 leaves
plus the STOP leaf):

| scheme | bits/id | fit ≤64 | bytes |
|---|---:|---:|---:|
| flat (yardstick) | 46.951 | 83.9% | 245,756 |
| CF | 48.987 | 81.9% | 15,544 |
| CF, arithmetic | 47.727 | 82.5% | 15,544 |
| CQF `q = 2` | 47.891 | **82.8%** | 15,796 |
| CQF `q = 4` | 47.820 | 82.8% | 16,364 |

Paired against CF: arithmetic `−1.260 ± 0.005` bits / `+0.6 ± 0.0` pt; CQF `q = 2`
`−1.095 ± 0.006` / `+0.9 ± 0.1` pt; CQF `q = 4` `−1.167 ± 0.006` / `+1.0 ± 0.1`.

So at 8192/16 CQF `q = 2` costs **252 bytes** in this accounting and
buys 0.9 points over CF, or **0.3 points over arithmetic decoding at
0.84 kB/pt**.  On the accounting's price it is the cheapest fit point in the
whole study — cheaper than anything the `k` or `V` directions offer — and `q = 4`
is again dominated (same fit, 3.3× the bytes).  This is the point that made CQF
the adopted code on the arithmetic accounting; the `k = 32` point above is the
second-best case, and above `k = 32` it is not worth the tables.  The shipped
convention decides against it:

| `V, k` | `q = 1` file | bits/id | fit ≤64 | `q = 2` file | bits/id | fit ≤64 |
|---|---:|---:|---:|---:|---:|---:|
| 4096, 16 | 14,683 B | 49.083 | 80.0 % | 15,355 B | 49.060 | 80.1 % |
| 8192, 16 | 30,612 B | 45.790 | 84.1 % | 31,796 B | 45.687 | 84.3 % |
| 8192, 32 | 32,126 B | 45.221 | 84.8 % | 33,790 B | 45.272 | 84.7 % |
| 8192, 64 | 35,090 B | 45.347 | 84.5 % | 38,674 B | 45.296 | 84.7 % |

At 8192/16 the paired difference is `−0.103 ± 0.010` bits per identifier and
+53 identifiers fitting in 64 bits (282 gained, 229 lost, out of 42,268) for
1,184 B.  Against the frontier that is 9.5 kB/pt where the shipped curve charges
3.9 kB/pt between 4096/16 and 8192/16, and 0.10 bits is worth about 0.57 kB at
5.5 kB/bit — so the 1,184 B is not repaid on either axis.  At the operating point
`k = 32` there is nothing to repay: `q = 2` is 1,664 B *and* 0.05 bits worse,
with 0.08 points fewer.  The reason is the terminator: of the 1.10 bits and
0.9 points the arithmetic accounting credited to the quarters, about 1.00 bits and
0.78 points were the cost of *ending* an identifier, which the zero-weight STOP
leaf in the top stage now removes from both codes.  What is left is the word-stage
granularity alone, and it is worth a tenth of a bit.  `q = 4` is worse still, and
at `k = 64` the `q = 2` file costs 3,584 B for 0.05 bits.

The 252 bytes are real in this accounting's terms and not in the model file's.
That accounting stores each tree as a bracket string plus its leaves in
depth-first order, so the grouping is *in* the file: the whole change costs
256 B of extra top-stage labels and brackets, less 4 B of bottom brackets.  A
published file stores depths instead — a third of the size (`MODEL_BUDGET.md`
§3) — and depths do not say which symbols share a tree, so it carries one label
per word: one bit more than a left-cluster label (5 against 4 at the operating
point), 1,024 B, plus 160 B of extra top depths, so **1,184 B is what `q = 2`
would cost at `8192/16`** and 1,664 B at the operating point `k = 32`
(`MODEL_FORMAT.md` §3).  The arithmetic accounting priced that at 1.3 kB/pt;
measured it is 9.5 kB/pt there, outside the frontier's 1–6 kB/pt band, and at
`k = 32` it is negative.  Either way the factored file sits below the arithmetic
reference on bytes *and* above it on fit: 34.2 kB / 84.8 % measured against
42.6 kB / 82.8 %, where the Huffman row has already had the terminator's bits
taken off and the arithmetic row cannot (`MODEL_BUDGET.md` §7).

**The noise, measured.** These are proportions over 42,268 identifiers, so the
right yardstick is the *paired* per-identifier difference (same held-out
identifiers, same trees below the top stage).  At `V = 4096, k = 32`:

| comparison | bits | fit<=64 |
|---|---:|---:|
| flat − CF | −2.459 ± 0.015 | +2.9 ± 0.1 pt |
| arithmetic − CF | −0.868 ± 0.007 | +0.4 ± 0.1 pt |
| CQF `q = 2` − CF | −0.820 ± 0.007 | **+0.8 ± 0.1 pt** |
| CQF `q = 4` − CF | −0.973 ± 0.008 | +0.9 ± 0.1 pt |
| `ref` − CF | −9.964 ± 0.056 | +12.6 ± 0.2 pt |

at `k = 64`: arithmetic `−1.392 ± 0.006` / `+0.8 ± 0.1`; CQF `q = 2`
`−1.281 ± 0.007` / `+1.1 ± 0.1`; CQF `q = 4` `−1.518 ± 0.008` / `+1.4 ± 0.1`;
at 8192/64: arithmetic `−1.318 ± 0.006` / `+0.8 ± 0.0`; `q = 2`
`−1.137 ± 0.007` / `+0.9 ± 0.1`; `q = 4` `−1.244 ± 0.008` / `+1.1 ± 0.1`.

So the `k = 32` claim is solid on the statistics that matter: 117σ in bits and
8σ in fit rate for CQF over CF, and 0.4 ± 0.1 pt for CQF over arithmetic.  The
unpaired binomial standard error at this sample is 0.2 pt, which is why the
paired form matters — it is twice as tight, because almost all identifiers sit
far from the threshold and the ones that flip are a small correlated set.  The
stride-10 re-measurement also tightened every standard error by `sqrt(10)`
against the earlier pass, which is how the +0.9 pt reading at `k = 32` was
identified as noise.

All of these numbers are the arithmetic accounting's convention: both codes pay
for the stop.  Under the shipped convention the same `q = 2`-against-`q = 1`
comparison at the operating point is 0.10 bits and 0.13 points, not 1.10 and
0.9 — the STOP leaf removes the transition cost from both codes, and that was
most of the quarters' margin.

Two honesty notes on the domination table, whose margins are 0.3 pt: those are
*cross-model* differences (a different code for a different `k`), so their
sampling error is the unpaired one, 0.2 pt, and individually they are not
significant.  What is significant is the bits gap they are built from
(`−0.820 ± 0.007` here), and the fact that the fit ordering agrees with the bits
ordering at all three points.  The two metrics can disagree when the mean sits
well below the 64-bit threshold — a bits gain that does not appear as fit
points — which is why both are always reported.

## The experiment

1. Tokenise a held-out set with the canonical dictionaries (`V ∈ {4096, 6144,
   8192}`), as `words_per_identifier.py` already does.
2. Cluster as now (`cluster_words.py`, Hellinger `k`-means, `k ∈ {16, 32, 64}`),
   then form the quarters **only by truncating the
   build**: halt each right cluster's tree when `q` subtrees remain, and take
   those survivors as the quarters.  There is no freedom here, and that is the
   point (see "How the gain arises" below): an imposed partition — equal-mass
   quantiles, or `k`-means inside the cluster — forces the unequal merge *inside*
   a quarter, which is precisely the loss the truncation avoids.  Measure one
   imposed partition anyway, as a control that should lose; `k`-means inside the
   cluster is the natural one, since it also shows that a context-similarity
   criterion is not a code criterion.
3. **How the gain arises — and why the grouping is not a design choice.**
   Huffman's cost is the sum over merges of the merged mass, so the `q − 1`
   merges *above* the stop point are exactly what CQF replaces:

       loss avoided inside the cluster = Σ over the last q − 1 merged masses

   CQF replaces them with a top symbol shared across right clusters.  Careful
   with the comparison: the top stage is not *new* — CF already pays a cluster
   step of `H(cluster | left cluster)`.  What CQF pays is the **increase** from
   `k` to `kq` symbols, i.e. the same conditional entropy at a finer target, plus
   its rounding.  So the net is

       recovered − (top stage increase)

   and quoting the whole top stage rather than its increment overstates it,
   because it charges what CF already paid.  The trade works because a right
   cluster whose final merges are expensive is one with a heavy survivor and
   small siblings: the shared top tree lets that survivor pair with *other right
   clusters'* heavy survivors instead of with its own tail.

   Three consequences, all of which rule out imposing a partition:

   * If the survivors were equal in mass, finishing the build would cost exactly
     `log₂ q` bits per symbol — the cheapest a `q`-way split can be.  There would
     be nothing left for the shared tree to recover, and the extra stage would
     only add its own rounding.  Equal quarters are the one case where CQF
     *cannot* win, so "balance the quarters" is the wrong prescription.
   * Any imposed partition must merge unequal masses *inside* a quarter (a heavy
     word sharing a bottom tree with small ones), which reintroduces the loss in
     every quarter — the bottom trees are individually optimal for their groups,
     but the grouping is what costs.
   * The only design freedom is therefore `q` (and whether to ship quarters at
     all).  Where to stop is chosen by the build.

4. Measure four lengths per identifier: arithmetic reference; flat Huffman
   (one tree per left cluster over `V` words — affordable at `4,096` only as an
   upper-bound curiosity); CF (two trees); CQF for
   `q ∈ {2, 4}`.
5. Price each scheme with the size accounting above, then plot **total model
   bytes (word list + memberships + block + code lengths) against mean bits and
   against the 64/128-bit fit rates**, alongside the "spend the same bytes on
   more words / more clusters" frontier.
6. Decision rule: adopt CQF only if, at matched total bytes, it beats the best
   CF configuration on the *fit* rates — the quantity the product cares about —
   by more than the run-to-run noise of the frontier.  The measured upper bound
   on the gain is the CF penalty itself (1.4–1.6 bits/identifier), and CQF can
   only recover the word-step share of it.


## The structural cost: it refines one side only

Every model in this repository before this one had **one label set**, used on
both sides of the transition: `k` word trees with `V` leaves between them, and
`k` cluster trees with `k` leaves each, so the number of trees equalled the
number of leaves in a row.

CQF gives the two sides different label sets.  Every word belongs to a **right
cluster** — the thing the word step codes — and the `kq` right clusters are
grouped `q` to a **left cluster**, which is what the cluster step codes.  So the
top stage is `k` trees of `kq` leaves, not `kq` trees of `kq`, and a right
cluster can pair with a *different* left cluster's survivor in the top tree,
which a finer shared clustering cannot do without also making the left context
finer.  That asymmetry is where the gain comes from.

It does not need a second **map**.  Each word carries one label, its right
cluster, and its left cluster is that label divided by `q`.  So the file stores
one label per word in `⌈log₂ kq⌉` bits rather than `⌈log₂ k⌉` — 5 instead of 4
at 8192/16, 6 instead of 5 at the operating point, 1,024 B either way — plus the
extra top depths, 160 B at `k = 16` and 640 B at `k = 32`, and the two counts
`k` and `q`.  What is paid for is the width, not a second table.

**The width is not avoidable.**  It is tempting to name a right cluster by a
position in the tree — the boundary between two runs of its leaves, `q − 1`
positions per left cluster, about 26 B — and the size accounting can price the
change that way only because it stores the tree's *topology*: a bracket string
plus its leaves, in which any grouping is already explicit.  Two things rule the
shortcut out for the published file.

* **Depths cannot carry the grouping.**  The file stores depths, a third of the
  size, and a reader rebuilds the *canonical* tree from them.  The right clusters
  are subtrees of the *Huffman* build, and the canonical tree has the same shape
  with different leaves: about a quarter of the right clusters come out as
  unbroken blocks of its leaf order, and fewer still as subtrees of it.  So a
  position in the stored tree does not mark them.
* **A position would change the code, not describe it.**  Even if the blocks
  lined up, a block boundary is a *partition*: it merges unequal masses inside a
  right cluster, which is exactly the loss the truncation avoids (step 3 of the
  experiment above).  The right clusters have to be the survivors the build
  stopped at, and those are decided by the weights, not by where a boundary
  falls.

So the label is the price of an arbitrary grouping, and arbitrary is what the
quarter code needs.  `MODEL_FORMAT.md` §7 records it as settled.

Two alternatives were priced, and neither is the shipped file:

* **252 B, in the accounting above.**  Topology plus leaves; the grouping is
  explicit, at the cost of making the file three times bigger (`MODEL_BUDGET.md`
  §3).
* **2,816 B, with the label set made symmetric.**  `k` becomes `kq` on both
  sides, the plain factored model at twice the clusters: 42,571 B against
  39,755 B at `V = 8192`, for +0.3 points on the arithmetic reference.  It needs
  no format change at all, and it costs 2.7× the accounting's CF file for a third
  of the gain (0.3 arithmetic points against the quarters' 1.1 arithmetic
  points; measured under the shipped convention the quarters' gain is 0.13).

**Outcome.** On the arithmetic accounting `q = 2` won and `q = 4` lost.  On the
measured numbers neither wins: at `8192/16` the quarter code costs 1,184 B for
0.10 bits and 0.13 fit points — 9.5 kB/pt against the shipped frontier's 3.9 — and
at the other measured points the terms are worse (672 B at 4096/16 for 0.1
points, 3,584 B at 8192/64 for 0.2, and 1,664 B at the operating point for
nothing).  So **`q = 1` ships**: the plain factored code, 32,126 B, 45.221 bits
per identifier, 84.8 % in 64 bits at `8192/32`.  The mechanism is
real — the truncated build does shorten the word step, and with the stop charged
it is worth about a bit — but the shipped code no longer pays that charge, so the
quarters solve a problem the format has already solved with the top-stage STOP
leaf.  The encoding is unchanged throughout — `q` only multiplies `k` in the top
stage (`ENCODING.md` §5) — and the format keeps `q` as an option
(`MODEL_FORMAT.md` §2), so the decision can be revisited if a different `k` or a
different terminator convention changes the price.
