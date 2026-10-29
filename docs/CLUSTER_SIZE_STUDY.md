# Study: choosing the number of clusters `k` and the vocabulary size `N`

Status: **plan**.  This note sets out a study to find the `(k, N)` pairs that give
a good successor model for their size, and to test the hypothesis that the
optimum sits on a *constant ratio* `k / N`.

## The two knobs and what they cost

The successor model predicts the next character from the longest common
substring that is a suffix of the prefix (the "context").  Its two size knobs
are:

* **`N`** — the number of common substrings (the vocabulary), set by the
  occurrence threshold `T` (a substring is kept if it occurs at least `T`
  times).  Raising `N` admits longer, sharper contexts.
* **`k`** — the number of clusters the contexts are pooled into; each cluster
  carries one successor distribution.

Under the dense representation we intend (see
[the brief](COMPRESSION_ESTIMATES.md)), a substring costs **16 bytes** (its
hash / index) and a cluster costs **128 bytes** (its dense distribution over the
`d ≈ 64` successor symbols).  So the model size is

    S(N, k) = 16 N + 128 k    bytes.

Only the *ratio* 128 : 16 = **8** matters for the trade-off; all conclusions
should be reported as a function of it, and checked for sensitivity.

## What "good for its size" means

Both knobs reduce the code length per character, `H(next | cluster)` in bits,
but at a byte cost.  Two equivalent framings:

1. **Pareto frontier (fixed budget).**  In the `(S, H)` plane, keep only points
   not dominated (smaller `S`, smaller `H`).  The frontier answers "given `S`
   bytes, what is the best `H`?", and each frontier point is a `(N, k)` pair.
2. **MDL / total cost.**  For a corpus of `C` characters,

        total_bits = 8 · S(N, k)  +  C · H(next | cluster)   (+ fixed bits)

   minimise over `(N, k)`.  This has an interior optimum: each extra cluster
   costs 8·128 = 1024 bits of model, worth it only while it saves `C · ΔH`
   data bits — and `ΔH` shrinks as `k` grows.

## Do we need held-out entropy?  (checked — barely)

The obvious worry is that training `H(next | cluster)` is monotone decreasing in
both `N` and `k`, so the training frontier degenerates to `k = n_ctx`, and the
study is meaningless.  We therefore measured **held-out** entropy directly, by
binomial thinning of the counts: each occurrence is independently assigned to
train / test (p = 1/2), the clusters are fit on the *train* counts, and the
held-out cross-entropy `-Σ_test log2 P_cluster(successor)` is accumulated on the
*test* counts.  (This is a clean held-out split and needs only the aggregated
count matrix.)

Result: `H_held ≈ H_train` to **≤ 0.005 bits**, all the way to `k = n_ctx`:

| T | n_ctx | k | H_train | H_held | Δ |
|---:|---:|---:|---:|---:|---:|
| 100000 | 150 | 150 | 3.932 | 3.932 | +0.001 |
| 20000 | 849 | 800 | 3.344 | 3.349 | +0.005 |
| 10000 | 1950 | 1000 | 3.127 | 3.132 | +0.005 |

The reason is structural: the threshold `T` keeps every retained context
*frequent* (≥ `T` occurrences), so its successor distribution is estimated well
even from half the data — over-clustering does not memorise noise.  **So
training `H` is a sound proxy here**, with the caveat that a low threshold
(rare contexts) would eventually overfit and then the held-out harness must be
used.  Keep the harness as a check anyway.

Consequently the interior optimum does **not** come from overfitting; it comes
from the **model-size term** in the total cost (below): adding clusters lowers
`H` only slightly once `k` is large, while costing 1024 bits each.

## Data

Per threshold `T` we need the training/held-out curve `H(next | cluster)` vs
`k`, together with `N`, `n_ctx`, `H(next)` and `H(next | substring)` (the `k = 1`
and `k = n_ctx` limits).  All thresholds `100000 … 500` already have
`successor_distributions.tsv`.  A first pass over the cached thresholds
(`100000, 50000, 20000, 10000, 5000, 2000`) spans `N = 159 … 11758`, enough for
a first frontier; the tail (`1000, 500`) needs a corpus rescan (~6 min each).

## Method

1. **Grid.**  For each `T`, sweep `k` over a log-spaced grid from 2 up to
   `n_ctx` (clip at `n_ctx`).  Record `(N, n_ctx, k, H_train, H_held)`.
2. **Points.**  Map each run to `(S = 16N + 128k, H_held)`.
3. **Frontier.**  Sort by `S`, take the lower envelope of `H_held`.
4. **Fit** the frontier, e.g. `H_held ≈ a − b·S^{-c}`, and tabulate the
   `(N, k)` pairs and their ratio `k / N` along it.
5. **Test the hypothesis** `k / N ≈ const`: regress `log k` on `log N` along the
   frontier; a slope near 1 with a tight intercept supports it.  Report the
   ratio and its spread, and whether it drifts with `S`.
6. **MDL overlay.**  For corpus sizes `C` spanning a grid, mark the optimal
   `(N, k)` from the total-cost formula and compare the implied `k / N`.

## Sensitivity and controls

* **Ratio.**  Rerun step 5 with cluster costs 32/64/128/512 bytes (ratio 2…32)
  and report how the frontier ratio scales — expect `k / N ∝ 1 / (cluster
  cost)`.
* **Restarts.**  Report the best-of-`R` spread; flag grid points where restarts
  disagree by more than ~0.01 bits.
* **Corpus size.**  Held-out folds of different sizes show whether the optimum
  drifts as data grows (the model term is fixed, the data term grows).
* **`k ≤ n_ctx`.**  Near the cap the model approaches the exact context model;
  this is a corner, not an interior optimum — mark it.

## Deliverables

1. A figure: `S` (bytes, log axis) against held-out bits/character, one curve
   per `N`, with the Pareto frontier drawn through them.
2. A table of frontier `(T, N, k, S, H)` and the `k / N` ratio.
3. A one-line recommendation: the ratio and the `(N, k)` at a few budgets.

## First pass (done) and what it says

`scripts/cluster_size_frontier.py` turns a sweep log into the frontier and the
MDL optimum.  Sweeping `k` over a log grid for `T = 100000 … 5000` gives, at the
endpoints,

| T | N | n_ctx | H(next) | H(next\|substring) |
|---:|---:|---:|---:|---:|
| 100000 | 159 | 150 | 4.966 | 3.932 |
| 50000 | 316 | 298 | 4.966 | 3.711 |
| 20000 | 911 | 849 | 4.966 | 3.344 |
| 10000 | 2102 | 1950 | 4.966 | 3.070 |
| 5000 | 4478 | 4162 | 4.966 | 2.856 |

The `(S, H)` frontier is well populated between `S ≈ 3 kB` and `S ≈ 150 kB`, and
the ratio `k / N` along it **rises with `S`** (roughly 0.01 → 0.35 across that
range) rather than being constant — so the constant-ratio hypothesis is *not*
supported by this first cut, and the interesting regime (large `k`) is where the
data runs out.  Two concrete gaps to close:

* **The grid is truncated.**  For every corpus size `C ≳ 10^7` the MDL optimum
  sits at the largest `k` and the lowest `T` we tried (`k = 640`, `T = 5000`),
  i.e. at the corner of the data.  We need `k` up to `n_ctx` and the tail
  thresholds `T = 1000, 500` (and a couple more, e.g. 4000) to see the optimum
  move inside the range.
* **`common2000`'s table was stale** (built from the pre-longest-suffix
  successor count; it gave `H(next|substring) = 3.159 > 2.856`, breaking
  monotonicity), so it was excluded and is being regenerated.

The held-out check (above) says overfitting is not the limiter, so the shape of
the frontier is driven by the model-cost trade-off, which is what the extended
grid should settle.

## Notes for the "distant future" encoding

* We have deliberately rejected storing occurrence frequencies and Huffman /
  arithmetic tables; this study is about the *clustered successor* model, whose
  whole size is `16N + 128k`, not a code table.
* The final scheme also needs the top-level 64-bit codeword plan and the
  hash + global-dictionary fallback; `(N, k)` is only the model-size part of
  the budget.  When that lands, the byte cost should be reconciled with the
  actual bit budget (64 bits) rather than the placeholder 16/128.
* `scripts/cluster_size_frontier.py` is the analysis entry point; the sweep
  itself is just `cluster_substrings.py --k K` over a grid of `K` and `T`.
