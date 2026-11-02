# Compressing the word adjacency matrix by left/right K-means clustering

Status: **succeeded (as a compressor).**  A two-sided K-means co-clustering of
the word × word matrix, stored as a `k × k` block matrix plus the per-word
linear tables, codes held-out identifiers *better than the Hellinger rank-`L`
factorisation of equal storage* at every size tested.  Both are far behind the
full table, but co-clustering is the better way to shrink the largest table.

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
(`n = 5 739`).

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
columns is the cost of imposing the factorisation — a few bits, i.e. the
factorisation is good but not free.

## Results

`k/N = 20` is `k = V/20` (`CLUSTER_SIZE_STUDY.md`'s ratio).  `store` counts
model numbers; the "matched" `sqrtcnt` column is the Hellinger factorisation
with `L = round(store / 2V)`; `loss` is `assoc − 1-sided`, the held-out cost of
the factorisation (see above).

**tw96 (V = 160), full table 65.029 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | loss | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---|
| 8 | 384 | 79.94 | 77.59 | 2.35 | 22/95 | L=1 / 320 / 84.73 |
| 20 | 720 | 77.32 | 73.92 | 3.39 | 14/95 | L=2 / 640 / 82.06 |
| 40 | 1920 | 74.18 | 70.83 | 3.35 | 9/95 | L=6 / 1920 / 76.47 |

**tw512 (V = 576), full table 54.205 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | loss | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---|
| 14 | 1348 | 69.69 | 66.65 | 3.05 | 16/492 | L=1 / 1152 / 75.47 |
| 29 | 1993 | 68.03 | 64.27 | 3.76 | 8/492 | L=2 / 2304 / 72.86 |
| 58 | 4516 | 65.68 | 61.73 | 3.95 | 2/492 | L=4 / 4608 / 69.60 |

**tw2040 (V = 2104), full table 45.861 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | loss | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---:|---|
| 26 | 4884 | 57.43 | 55.02 | 2.41 | 18/2012 | L=1 / 4208 / 62.77 |
| 52 | 6912 | 56.72 | 53.80 | 2.92 | 6/2012 | L=2 / 8416 / 60.68 |
| 105 | 15233 | 55.48 | 52.27 | 3.21 | 2/2012 | L=4 / 16832 / 58.53 |

## What it shows

* **At equal storage the co-clustering beats the Hellinger factorisation
  everywhere.**  At `V/20` on `tw2040`, a `105 × 105` block model (15.2k
  numbers, 0.35% of the `V²` cells) codes 55.48 bits against the factorisation's
  58.53 at the same size — 3 bits better.  The margin is similar at `tw512`
  (65.68 vs 69.60) and `tw96` (74.18 vs 76.47).
* **The 1-sided table survives the factorisation to within a few bits.**  The
  `loss` column (the held-out cost of replacing `P(right word | left cluster)`
  by `P(right cluster | left cluster)·P(right word | right cluster)`) is
  2.4–4.0 bits across the three dictionaries — so the factorisation the `assoc`
  model embodies is a good one, just not free.
* **The one-sided model is competitive only because its table is much larger**
  (`k·V`, not `k² + 2V`): at `tw2040` `k = 105` it stores 221k numbers for 52.27
  bits, versus 15.2k numbers for 55.48 — it wins by 3.2 bits for ~14× the
  storage, a different point on the frontier.
* **Aggressive compression is still lossy.**  At `k/N = 20` (`k = V/20`) the
  co-cluster model costs 9.6 bits (`tw2040`), 13.8 bits (`tw512`) and 14.9 bits
  (`tw96`) against the full table.  The block structure of the word matrix is
  real but weak: coarser than a few hundred clusters, the block approximation
  loses a lot.

## How the loss scales with `k`

The question behind this sweep: the loss from the full `V×V` table to the
`k×k` block model is large (~10 bits at `k = V/20`), but is it *fundamental* to
the block-constant restriction, or does it close if we simply allow more
clusters?  Sweeping `k` up to `V/2` (same harness, `kappa = 300`) answers it.

**`tw2040`** (V = 2104, full table 45.765 bits; `store = k² + 2V`):

| `k` | store | % of `V²` | assoc | Δ vs full | 1-sided | Δ vs full |
|---:|---:|---:|---:|---:|---:|---:|
| 26 | 4,884 | 0.11 % | 57.33 | +11.57 | 54.90 | +9.14 |
| 52 | 6,912 | 0.16 % | 56.58 | +10.82 | 53.69 | +7.92 |
| 105 | 15,233 | 0.35 % | 55.35 | +9.59 | 52.16 | +6.39 |
| 210 | 48,308 | 1.09 % | 53.43 | +7.67 | 50.61 | +4.84 |
| 420 | 180,608 | 4.1 % | 50.98 | +5.21 | 48.68 | +2.92 |
| 840 | 709,808 | 16.0 % | 48.58 | +2.82 | 47.24 | +1.48 |
| 1052 | 1,110,912 | 25.1 % | 47.78 | +2.01 | 46.80 | +1.04 |

**`tw512`** (V = 576, full table 54.164 bits):

| `k` | store | % of `V²` | assoc | Δ vs full | 1-sided | Δ vs full |
|---:|---:|---:|---:|---:|---:|---:|
| 14 | 1,348 | 0.41 % | 69.68 | +15.52 | 66.61 | +12.44 |
| 29 | 1,993 | 0.60 % | 68.00 | +13.83 | 64.23 | +10.07 |
| 58 | 4,516 | 1.4 % | 65.64 | +11.47 | 61.67 | +7.50 |
| 115 | 14,377 | 4.3 % | 61.77 | +7.61 | 58.61 | +4.44 |
| 230 | 54,052 | 16.3 % | 57.62 | +3.46 | 55.98 | +1.82 |
| 288 | 84,096 | 25.3 % | 56.33 | +2.16 | 55.30 | +1.13 |
| 432 | 187,776 | 56.6 % | 54.67 | +0.51 | 54.43 | +0.26 |

What the curves say:

* **The loss closes smoothly, with no knee.**  Each doubling of `k` buys roughly
  2–3 bits low down and 1–1.5 bits high up; there is no cluster count at which
  the block model suddenly becomes near-lossless.
* **"Low loss" means storing a large fraction of the matrix.**  To get within
  ~1 bit of the full table needs `k ≈ V/2`, i.e. `store ≈ V²/4` (25 % of the
  cells).  At the practical operating point `k = V/20` (0.3–0.6 % of `V²`) the
  loss is 9.6 bits (`tw2040`) / 13.8 bits (`tw512`).
* **So the loss is essentially unavoidable for the block-constant model.**  It is
  not the choice of `k` that hurts; it is the restriction itself.  Clustering
  cannot be both small and accurate, which is the case for compressing the
  matrix *directly* (sparse residual from a low-rank/`M_mar` fit) rather than
  approximating it by blocks.
* **The factorisation penalty shrinks with `k`.**  `assoc − 1-sided` falls from
  ~2.4 bits at `k = 26` to ~0.4 bits at `k = 1052` (as clusters become small,
  `P(right word | right cluster)` carries almost all the information).
* **At large store, even the low-rank model overtakes clustering.**  At matched
  storage the `sqrtcnt` factorisation is worse than `assoc` up to `k ≈ 420`
  (51.84 vs 50.98) but better beyond it (`k = 840`: 47.96 vs 48.58;
  `k = 1052`: 47.05 vs 47.78).  Neither reaches the full table: at ~25 % storage
  both sit 1–2 bits above it.

## The removable-word refinement

The plan suggested also dropping pair words `(uv)` whose left cluster equals
`v`'s and whose right cluster equals `u`'s (their cluster labels are implied by
their operands').  The `drop` column shows how many such words there are: only
**2 of 2012** pair words at `V/20` on `tw2040` (18 at `k = 26`).  The refinement
saves a negligible number of labels and was not pursued.

## Conclusion

K-means co-clustering is the better way to compress the word × word matrix:
stored as a `k × k` block matrix plus linear tables it dominates the Hellinger
factorisation of equal storage, and at `k/N = 20` it shrinks the matrix to ~0.3%
of its cells for ~10 bits/identifier.  But that loss is not avoidable by adding
clusters: it falls smoothly and only reaches ~1 bit at `k ≈ V/2`, i.e. ~25 % of
the matrix.  For a compact standard, the block model alone will not do.
The direct alternative — storing the matrix itself with codewords over a
low-rank/`M_mar` fit — fares no better: the residual is not sparse, and top-`N`
cells over the independence prior stays within ~1 bit only at `N ≈ 300K`
(~15× smaller than
`V²`).  Neither route alone gives a compact, near-lossless table.  See
[`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md).
`scripts/cluster_words.py`.
