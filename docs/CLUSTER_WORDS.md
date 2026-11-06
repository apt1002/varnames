# Compressing the word adjacency matrix by left/right K-means clustering

Status: **succeeded (as a compressor).**  A two-sided K-means co-clustering of
the word × word matrix, stored as a `k × k` block matrix plus the per-word
linear tables, codes held-out identifiers *better than the Hellinger rank-`L`
factorisation of equal storage* at all three grid vocabularies.  Both are far
behind the full table, but co-clustering is the better way to shrink the largest
table.

## Model

The word bigram matrix `M` (`V × V`) is the largest object in the model, so this
note asks how to store it in `k² + O(V)` numbers instead of `V²`.

Following the word-level analogue of [`CLUSTER_SIZE_STUDY.md`](CLUSTER_SIZE_STUDY.md),
each word is given:

* a **left cluster** (predecessor side): words are clustered by their successor
  distribution `p(·|a)`;
* a **right cluster** (successor side): words are clustered by their predecessor
  distribution `p(·|b)`.

Write `lcl(a)` and `rcl(a)` for the left and right cluster labels of the word
`a` (deliberately *not* `lc`/`rc`, which this project uses for a word's left and
right child).  Clustering is K-means in the **Hellinger** embedding `√p`, occurrence-weighted
(the helpers of `cluster_substrings_lib`, `kmeans_sphere`).  Two models
are built:

* **assoc** — the marginal-factored block model
  `M̂[a,b] = r[a] c[b]/T · D[lcl(a), rcl(b)]`, where `D` is the block mean of `M`
  divided by the block mean of `r cᵀ/T` — equivalently the ratio of their block
  sums, since the block sizes cancel (this is *not* the mean of the ratio
  `M / (r cᵀ/T)`); every block's mass is preserved exactly, and `r`, `c` are the
  row/column marginals.
* **1-sided** — the pooled-row model: `p(b|a) = P1[lcl(a), b]`, where `P1` is the
  occurrence-weighted **mean successor distribution** of each left cluster (the
  maximum-likelihood pooled distribution, and the direct word-level analogue of
  the character successor model).

Storage: **assoc** is `k² + 2V` numbers; **1-sided** is `k·V`.  The Hellinger
factorisation of [`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md) is
`2VL`.  All models are fit to the same `kappa = 300` reference `M_ref`, and the
held-out mean bits use a stride-`40` sample of `work/camel/merged_validation.txt`
(`n = 10,567` identifiers).  The vocabularies are the grid builds
`work/tw4096ns`, `work/tw6144ns`, `work/tw8192ns`
(`--sample 20 --stride 0`); `scripts/cluster_words.py`.

### What the 1-sided model tests

The 1-sided table is the **un-factored reference** `P(b | L)` — the distribution
over *right words* given the *left cluster* alone.  Its value is that `assoc` is
*exactly* the factorisation of that table through the right cluster, so the
1-sided column measures how much that factorisation costs.  Two facts make the
identity literal:

* **`assoc` does not depend on `r[a]`.**  Normalising
  `M̂[a,b] = r[a]·c[b]/T · D[lcl(a), rcl(b)]` cancels the common factor `r[a]`:
  `p(b|a) = c[b]·D[lcl(a), rcl(b)] / Σ_{b'} c[b']·D[lcl(a), rcl(b')]`, a function
  of `(left cluster, right word)` only — the same functional class as the
  1-sided table.  (Verified: every word in a left cluster gets the same row, to
  machine precision.)
* **That expression is the factorisation.**  With `C_rc = Σ_{b∈rc} c[b]` it equals
  `P(rcl(b)|L) · P(b|rcl(b))`, where `P(rcl(b)|L) ∝ D[L, rcl(b)]·C_rcl(b)` and the
  within-right-cluster word distribution `P(b|rc) = c[b]/C_rc` is **shared across
  all left clusters**.

So the 1-sided column asks the question directly: *does `P(right word | left
cluster)` factor as "pick a right cluster given the left cluster, then draw the
word from that right cluster's own marginal"?*  The held-out gap between the two
columns is the cost of imposing the factorisation — 1–2 bits, i.e. the
factorisation is good but not free.

## Results

`store` counts model numbers; the "matched" `sqrtcnt` column is the Hellinger
factorisation with `L = round(store / 2V)`; `loss` is `assoc − 1-sided`, the
held-out cost of the factorisation (see above); `drop` counts the pair words
whose cluster labels are implied by their operands' (see "The removable-word
refinement").

**`V = 4,096`** (`tw4096ns`), full table **42.202 bits**

| `k` | store | % of `V²` | assoc | 1-sided | loss | 1-sided store | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 8,448 | 0.050 % | 51.580 | 50.208 | 1.372 | 65,536 | 470/4,032 | L=1 / 8,192 / 55.623 |
| 32 | 9,216 | 0.055 % | 51.355 | 49.533 | 1.822 | 131,072 | 274/4,032 | L=1 / 8,192 / 55.623 |
| 64 | 12,288 | 0.073 % | 50.623 | 48.649 | 1.974 | 262,144 | 194/4,032 | L=2 / 16,384 / 53.710 |

**`V = 6,144`** (`tw6144ns`), full table **40.800 bits**

| `k` | store | % of `V²` | assoc | 1-sided | loss | 1-sided store | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 12,544 | 0.033 % | 49.388 | 48.385 | 1.003 | 98,304 | 817/6,080 | L=1 / 12,288 / 52.864 |
| 32 | 13,312 | 0.035 % | 49.020 | 47.767 | 1.253 | 196,608 | 536/6,080 | L=1 / 12,288 / 52.864 |
| 64 | 16,384 | 0.043 % | 48.688 | 47.170 | 1.518 | 393,216 | 348/6,080 | L=1 / 12,288 / 52.864 |

**`V = 8,192`** (`tw8192ns`), full table **39.930 bits**

| `k` | store | % of `V²` | assoc | 1-sided | loss | 1-sided store | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 16,640 | 0.025 % | 47.713 | 46.783 | 0.930 | 131,072 | 741/8,128 | L=1 / 16,384 / 51.222 |
| 32 | 17,408 | 0.026 % | 47.479 | 46.329 | 1.150 | 262,144 | 514/8,128 | L=1 / 16,384 / 51.222 |
| 64 | 20,480 | 0.031 % | 47.279 | 45.959 | 1.320 | 524,288 | 407/8,128 | L=1 / 16,384 / 51.222 |

## What it shows

* **At equal storage the co-clustering beats the Hellinger factorisation
  everywhere.**  At `V = 4,096`, `k = 16` a `16 × 16` block model (8,448
  numbers, 0.05 % of the `V²` cells) codes 51.580 bits against the
  factorisation's 55.623 at *slightly larger* storage (8,192, i.e. already the
  smallest `L = 1` it has) — 4.0 bits better.  The margin is 4.0 bits at
  `V = 4,096`, 3.5 at `V = 6,144` and 3.5 at `V = 8,192`.
* **The 1-sided table survives the factorisation to within a couple of bits.**
  The `loss` column (the held-out cost of replacing `P(right word | left
  cluster)` by `P(right cluster | left cluster)·P(right word | right cluster)`)
  is 0.93–1.97 bits across the nine grid points — smaller than the 2.4–4.0 bits
  measured on the small pre-expansion vocabularies, because with 4–8 k words the
  within-right-cluster marginal `P(b|rc)` is a much better approximation.  The
  factorisation the `assoc` model embodies is a good one, and it costs less the
  larger the word list.
* **The one-sided model is competitive only because its table is much larger**
  (`k·V`, not `k² + 2V`): at `V = 4,096`, `k = 16` it stores 65,536 numbers for
  50.208 bits, versus 8,448 numbers for 51.580 — it wins by 1.37 bits for 7.8×
  the storage, a worse exchange rate than either `k` or `V` offers elsewhere on
  the frontier.
* **Aggressive compression is still lossy.**  At these `k` the block model costs
  8.4–9.4 bits (`V = 4,096`), 7.9–8.6 (`V = 6,144`) and 7.3–7.8 (`V = 8,192`)
  against the full table.  The block structure of the word matrix is real but
  weak: a few thousand blocks, 0.03–0.07 % of the cells, loses most of the
  detail.

## How the loss scales with `k`

The question behind this sweep: the loss from the full `V×V` table to the
`k×k` block model is large (~9 bits at `V = 4,096`), but is it *fundamental* to
the block-constant restriction, or does it close if we simply allow more
clusters?  Sweeping `k` upward at `V = 4,096` (same harness, `kappa = 300`,
`store = k² + 2V`):

| `k` | store | % of `V²` | assoc | Δ vs full |
|---:|---:|---:|---:|---:|
| 16 | 8,448 | 0.05 % | 51.580 | +9.38 |
| 32 | 9,216 | 0.06 % | 51.355 | +9.15 |
| 64 | 12,288 | 0.07 % | 50.623 | +8.42 |
| 128 | 24,576 | 0.15 % | 49.996 | +7.80 |
| 256 | 73,728 | 0.44 % | 48.958 | +6.76 |

What the curve says:

* **The loss closes smoothly, with no knee.**  Each doubling of `k` buys 0.2
  bits low down (16 → 32 costs almost nothing in bits, because 256 blocks are
  already all used: 237 of 256 cells at `k = 16`) and 0.7–1.0 bits higher up,
  but there is no cluster count at which the block model suddenly becomes
  near-lossless.
* **"Low loss" means storing a large fraction of the matrix.**  To get within
  ~1 bit of the full table needs `k ≈ V/2`, i.e. `store ≈ V²/4` (25 % of the
  cells) — the pre-expansion sweep below reaches that corner and finds +2.0
  bits at 25 % of the cells, not +1.  At the practical operating point
  (0.03–0.4 % of `V²`) the loss is 6.8–9.4 bits.
* **So the loss is essentially unavoidable for the block-constant model.**  It is
  not the choice of `k` that hurts; it is the restriction itself.  Clustering
  cannot be both small and accurate, which is the case for compressing the
  matrix *directly* (sparse residual from a low-rank/`M_mar` fit) rather than
  approximating it by blocks.
* **The factorisation penalty is already small at the operating point** and does
  not fall further with `k` in the range swept (1.4 → 2.0 bits from `k = 16` to
  64 at `V = 4,096`), so a finer table buys its bits in the block values, not by
  making the factorisation exact.

Pre-expansion record (legacy `tw2040`, `V = 2,104`, full table 45.765): `k = 26
→ 1,052` covers 0.11 % → 25.1 % of `V²`, with assoc 57.33 → 47.78 (+11.57 →
+2.01) and 1-sided 54.90 → 46.80.  That is where the "≈V/2 for ~2 bits"
statement comes from; the grid sweep reaches only 0.44 % of `V²`, so the
large-storage end of the curve is still the small-vocabulary measurement.  The
same table shows `sqrtcnt` overtaking `assoc` only beyond `k ≈ 420` (51.84 vs
50.98 at 420; 47.96 vs 48.58 at 840; 47.05 vs 47.78 at 1,052) — both still
1–2 bits above the full table at ~25 % storage.

## Word-list size vs cluster-matrix budget

Everything above holds the word list fixed and varies the table.  The other
budget knob is the word list itself: a larger `V` gives longer words, hence
fewer tokens per identifier, at the cost of a bigger matrix.  `store = k² + 2V`
is the same either way, so the question is where to put the budget.

`scripts/wordlist_budget.py` sweeps the three grid word lists with
`k ∈ {16, 32, 64}` plus `k = 128, 256` at `V = 4,096`, `kappa = 300`, stride-40
validation.  Held-out bits are **per identifier**, so they compare across `V`:

| `V` | full table | `k=16` | `k=32` | `k=64` | store |
|---:|---:|---:|---:|---:|---|
| 4,096 | 42.20 | 51.58 | 51.36 | 50.62 | 8,448 / 9,216 / 12,288 |
| 6,144 | 40.80 | 49.39 | 49.02 | 48.69 | 12,544 / 13,312 / 16,384 |
| 8,192 | 39.93 | 47.71 | 47.48 | 47.28 | 16,640 / 17,408 / 20,480 |

(The `V = 4,096` list continues to 50.00 at `k = 128`, store 24,576, and 48.96
at `k = 256`, store 73,728 — see the scaling table above.)

* **The word list is the dominant lever.**  Merely moving from `V = 4,096` to
  `V = 8,192` drops the *full* table from 42.20 to 39.93 bits/identifier
  (−2.27), and the clustered model at fixed `k = 16` from 51.58 to 47.71
  (−3.87).  This dwarfs anything `k` buys at a fixed word list.
* **At matched store, pick the largest word list that fits.**  With
  `store = k² + 2V` the per-list floor is `2V`, so the frontier is "biggest `V`
  whose floor fits, then spend the rest on `k`": at store ≈ 17 k the best point
  is `V = 8,192, k = 16` (47.71, store 16,640), beating `V = 6,144, k = 64`
  (48.69, store 16,384) by 1.0 bit and `V = 4,096, k = 64` (50.62, store 12,288)
  by 2.9 bits — for 1.02× and 1.35× the storage respectively.
* **The clustering penalty shrinks with `V`** — at `k = 16` the `assoc − full`
  gap falls from 9.38 (`V = 4,096`) to 8.59 (`V = 6,144`) to 7.78
  (`V = 8,192`) — but it is still ≥ 7 bits everywhere, so the block model
  remains the weak part even with a big word list.
* **Charging for the dictionary does not change the ordering.**  `store = k²+2V`
  ignores the tree dictionary (~`2(V−64)` integers, charged as bytes in
  [`MODEL_BUDGET.md`](MODEL_BUDGET.md)); adding it (`k² + 4V`) moves every point
  right but the frontier still picks the largest `V` at every budget.

So the budget sweep confirms the direction the other two results pointed to:
**buy words first, clusters last.**  The residual table loss is the part still
worth attacking (the loss-attribution and block-structure experiments) or
accepting.

## The removable-word refinement

The plan suggested also dropping pair words `(uv)` whose left cluster equals
`v`'s and whose right cluster equals `u`'s (their cluster labels are implied by
their operands').  The `drop` column shows how many such words there are: at
`k = 16` that is **470 of 4,032** pair words at `V = 4,096` (11.7 %), 817 of
6,080 at `V = 6,144` (13.4 %) and 741 of 8,128 at `V = 8,192` (9.1 %); at
`k = 64` it falls to 194 / 348 / 407 (4.8 % / 5.7 % / 5.0 %).  Much more than the
2 of 2,012 seen at `k = 52` on `tw2040` — a small `k` makes pair words share
their operands' cells far more often.  Even so the saving is 5–13 % of the
existing *pair* words (0.5 % of `V` at `k = 16`), and re-coding them would make
their labels implicit rather than free; the refinement was not pursued.

## Conclusion

K-means co-clustering is the better way to compress the word × word matrix:
stored as a `k × k` block matrix plus linear tables it dominates the Hellinger
factorisation of equal storage (by 3.5–4.0 bits at the grid), and at `k = 16–64`
it shrinks the matrix to 0.03–0.07 % of its cells for 7–9 bits/identifier.  But
that loss is not avoidable by adding clusters: it falls smoothly and needs
~25 % of the matrix to approach the full table.  For a compact standard, the
block model alone will not do.
The direct alternative — storing the matrix itself with codewords over a
low-rank/`M_mar` fit — fares no better: the residual is not sparse, and top-`N`
cells over the independence prior stays within ~1 bit of the full table only at
`N ≈ 300K` cells (1/56 of `V²` at `V = 4,096`).  Read the other way, at *matched
store* the block model now beats a top-`N` table outright: at store 9,216 the
`k = 32` block model codes 51.36 against 52.74 for top-`N` at `N = 10,000`
(store 10,000) and 56.46 at `N = 1,000` — a 1.4-bit win at *smaller* store, a
reversal of the pre-expansion tie.  See
[`MATRIX_COMPRESSION.md`](MATRIX_COMPRESSION.md).

The dominant budget knob is not the table at all but the **word list**: at
matched model size, the largest `V` that fits beats a finer `k`, by 1–3 bits in
the size range tested (`V = 4,096 → 8,192`).  Buy words first, clusters last;
the table's residual 7–9 bit loss is what remains to attack.
