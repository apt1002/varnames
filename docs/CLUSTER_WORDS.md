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
(the helpers of `cluster_substrings_lib`, `kmeans_sphere`).  Two block models
are built:

* **assoc** — the marginal-factored block model
  `M̂[a,b] = r[a] c[b]/T · D[lcl(a), rcl(b)]`, where `D` is the block mean of the
  ratio `M / (r cᵀ/T)`; every block's mass is preserved exactly, and `r`, `c`
  are the row/column marginals.
* **1-sided** — the pooled-row model: predict `p(·|a)` by the mean successor
  distribution of `lcl(a)` (the direct word-level analogue of the character
  successor model).

Storage: **assoc** is `k² + 2V` numbers; **1-sided** is `k·V`.  The Hellinger
factorisation of [`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md) is
`2VL`.  All models are fit to the same `kappa = 300` reference `M_ref`, and the
held-out mean bits use a stride-`40` sample of `work/camel/merged_validation.txt`
(`n = 5 739`).

## Results

`k/N = 20` is `k = V/20` (`CLUSTER_SIZE_STUDY.md`'s ratio).  `store` counts
model numbers; the "matched" `sqrtcnt` column is the Hellinger factorisation
with `L = round(store / 2V)`.

**tw96 (V = 160), full table 65.0 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---|
| 8 | 384 | 79.62 | 78.40 | 22/95 | L=1 / 320 / 84.42 |
| 20 | 720 | 77.07 | 74.51 | 14/95 | L=2 / 640 / 81.73 |
| 40 | 1920 | 73.83 | 71.00 | 9/95 | L=6 / 1920 / 76.11 |

**tw512 (V = 576), full table 54.2 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---|
| 14 | 1348 | 69.69 | 68.30 | 16/492 | L=1 / 1152 / 75.47 |
| 29 | 1993 | 68.03 | 65.72 | 8/492 | L=2 / 2304 / 72.86 |
| 58 | 4516 | 65.68 | 62.84 | 2/492 | L=4 / 4608 / 69.60 |

**tw2040 (V = 2104), full table 45.9 bits**

| `k` | store (assoc) | assoc bits | 1-sided bits | drop | `sqrtcnt` L / store / bits |
|---:|---:|---:|---:|---:|---|
| 26 | 4884 | 57.43 | 56.38 | 18/2012 | L=1 / 4208 / 62.77 |
| 52 | 6912 | 56.72 | 55.05 | 6/2012 | L=2 / 8416 / 60.68 |
| 105 | 15233 | 55.48 | 53.32 | 2/2012 | L=4 / 16832 / 58.53 |

## What it shows

* **At equal storage the co-clustering beats the Hellinger factorisation
  everywhere.**  At `V/20` on `tw2040`, a `105 × 105` block model (15.2k
  numbers, 0.35% of the `V²` cells) codes 55.48 bits against the factorisation's
  58.53 at the same size — 3 bits better.  The margin is similar at `tw512` and
  `tw96`.
* **The one-sided model is competitive only because its table is much larger**
  (`k·V`, not `k² + 2V`): at `tw2040` `k = 105` it stores 220k numbers for 53.32
  bits, versus 15.2k numbers for 55.48 — a different point on the frontier.
* **Aggressive compression is still lossy.**  At `k/N = 20` the co-cluster model
  costs 9.6 bits (`tw2040`), 11.5 bits (`tw512`), 14.6 bits (`tw96`) against the
  full table.  The block structure of the word matrix is real but weak: coarser
  than a few hundred clusters, the block approximation loses a lot.

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
of its cells for ~10 bits/identifier.  `scripts/cluster_words.py`.
