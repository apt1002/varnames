# Square-root (Hellinger) factorisation of the adjacency matrix, and a prior on unobserved pairs

Status: the square-root (Hellinger) factorisation is the **default** in
`scripts/pair_matrix.py` (saved `pair_factors_L*.npy` carry a `sqrt` flag;
`--no-sqrt` restores the old count-space behaviour).  The metric is now the
**joint** KL, `KL(M/T ‖ M̂/ΣM̂)` in bits (lower is better), computed by
`pair_matrix_lib.kl_joint`; no conditional `p(b|a)` is formed anywhere any more.

## Why the joint KL is the right metric (and why the conditional is unnecessary)

For the joint distribution over `(a, b)` the chain rule gives, exactly,

    H(P(a,b))          = H(P(a))    + H(P(b|a))
    KL(P(a,b)‖Q(a,b))  = KL(P(a)‖Q(a)) + Σ_a P(a)·KL(P(b|a)‖Q(b|a)).

The joint KL therefore splits into a row-marginal term plus the
*occurrence-weighted* conditional KL.  The row-marginal term is the same for
every model here (they all leave the prefix marginal `P(a)` fixed), so it is a
**model-independent constant** and cancels in any comparison.  Hence ranking
models by the joint KL, by the joint cross-entropy, or by the weighted
conditional KL all agree — and the conditional never needed to be built.

Verified numerically at `T = 100000`:

    1.35269  =  0.0135  +  1.3392      (joint = row-marginal + weighted cond.)
    11.912   =  6.766   +  5.146       (H(P(a,b)) = H(P(a)) + H(P(b|a)))

So the earlier "occurrence-weighted conditional" KL and the joint KL agree to
the small row-marginal mismatch, model by model (e.g. `sqrtcnt` 0.480 vs 0.494
at `T = 100000`); the ordering is unchanged.  Reporting the joint is the simpler
statement and drops a whole intermediate object.

## Big idea

SVD minimises squared L2 error; the model is scored by KL.  For probability
vectors the square-root map is an isometry,

    ‖√p − √q‖² = 2 H²(p, q) ≈ 2 KL(p ‖ q)   for p ≈ q,

so factorise the Hellinger embedding `√M` of the **count** matrix and **square
the reconstruction back**:

    sqrtcnt:   √M ≈ (U Σ Vᵀ)_L ,    M̂ = (U Σ Vᵀ)_L² .

Two consequences:

* The reconstruction is minimised in the metric that matches KL, not the count
  scale.  This is worth far more than anything done to the raw SVD.
* The square is non-negative *however signed the latent scores are*, so the
  **model never has negative probabilities** — the negatives survive only in the
  latent reconstruction, where they perturb the Hellinger-space fit, not a
  probability.  So negative *probabilities* were never the real problem.

Working in count space is the point.  `√M[a,b] = √(N_a) · √(p(b|a))`, so rooting
the counts already builds in the occurrence weighting.  This is *identical* to
rooting a row-normalised `p(b|a)` and weighting by `√N_a` (the `hellw` of
earlier versions), verified to 4 d.p. with the exact SVD — dividing by `√N_a`
and renormalising cancels.  **Rooting the counts is the same as
occurrence-weighting the Hellinger fit**, and it is the reason the conditional
could be dropped: `hell` (unweighted), `hellw` (weighted) and the explicit
`diag(√N_a)` dance were all just this one model in disguise.

## Results

`L = 16`, `alpha = 0`, exact SVD.  Joint KL (bits):

| threshold (N) | clip | abs | backoff .1 | nmf | **sqrtcnt** | independence |
|---|---:|---:|---:|---:|---:|---:|
| 100000 (159) | 1.059 | 0.757 | 0.688 | 0.730 | **0.494** | 1.623 |
| 50000 (316) | 1.547 | 1.298 | 1.213 | 1.290 | **0.990** | 2.329 |
| 20000 (911) | 2.377 | 2.333 | 2.225 | 2.367 | **2.036** | 3.475 |
| 10000 (2102) | 3.111 | 3.159 | 3.055 | 3.353 | 3.090 | 4.340 |

(All exact SVD.)  `sqrtcnt` wins comfortably down to `T = 20000`; at
`T = 10000` the edge is gone at `L = 16` (the `backoff` mixture edges it,
3.055 vs 3.090) and even `abs` falls behind `clip` — the count-space Hellinger
subspace is no longer the best rank-16 KL model once the matrix is large and
sparse (density 16.7%).  A higher `L` narrows this (the Hellinger advantage
grows with rank at `T = 100000`), but we have not retested `T = 10000` at
`L > 16`.

**Accuracy of the randomised SVD.**  `pair_matrix_lib.randomized_svd` now
re-orthonormalises the range basis (QR) after *every* power iteration and
defaults to `n_iter = 8`.  At `N = 2102` this matches the exact SVD to ~0.001
bits in the sqrt domain and ~0.003 bits in count space; the old
single-iteration routine was ~0.07 bits off and overflowed in float32 (fixed in
commit `24d74db`).  Float64 buys nothing — the residual error is set by
`n_iter`, not the dtype, since the per-step QR keeps the basis
well-conditioned.  The tables above use the **exact** SVD and therefore carry
no approximation error.

## Rank dependence (T = 100000, exact)

| L | clip | abs | backoff .1 | nmf | **sqrtcnt** |
|---:|---:|---:|---:|---:|---:|
| 2 | 1.500 | 1.425 | 1.408 | 1.464 | 1.439 |
| 4 | 1.352 | 1.174 | 1.145 | 1.197 | **1.120** |
| 8 | 1.254 | 0.992 | 0.945 | 0.990 | **0.806** |
| 16 | 1.059 | 0.757 | 0.688 | 0.730 | **0.494** |
| 32 | 0.721 | 0.465 | 0.402 | 0.468 | **0.215** |
| 64 | 0.324 | 0.198 | 0.168 | 0.232 | **0.046** |

`sqrtcnt` wins from L=4 up, and the advantage *grows* with L (a factor ~4× over
the best previous remedy at L=64): the Hellinger space makes the extra ranks
count.  At L=2 the rank-1 backoff/marginal direction is marginally better.

## A prior on unobserved pairs (the counting fix)

`M` counts only the `(a, b)` pairs actually seen, so it is full of structural
zeros — 21% of cells at `N = 159`, 83% at `N = 2102`.  A zero is not an
impossibility, so (as defined and justified in
[`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md)) we add an independence-shaped
prior of fixed mass to form a **corrected reference**

    M_ref = M + alpha · P_mar ,   P_mar = (r/T)(c/T)ᵀ (sum 1),   alpha = kappa · N .

`M_ref` is the reference for the whole analysis: every model is fitted to
`M_ref` and scored against it, so results are **not comparable across `kappa`**
by design — `kappa` is a counting fix, not a reconstruction knob (the
reconstruction-side counterpart is the `backoff` remedy above, which keeps using
the sum-`T` `M_mar` for its convex mixture).

`L = 16`, joint KL `KL(M_ref ‖ M̂/ΣM̂)` in bits (lower is better).

`kappa = 1000` (the default) is the column to read; the others show the trend.

**T = 100000 (N = 159), 21% of cells unobserved** — the fix is small:

| method | κ=0 | κ=100 | κ=300 | κ=1000 | κ=3000 |
|---|---:|---:|---:|---:|---:|
| clip | 1.059 | 1.059 | 1.058 | 1.057 | 1.062 |
| abs | 0.757 | 0.756 | 0.754 | 0.747 | 0.731 |
| backoff .1 | 0.688 | 0.688 | 0.686 | 0.680 | 0.666 |
| nmf | 0.730 | 0.729 | 0.728 | 0.723 | 0.711 |
| **sqrtcnt** | 0.494 | 0.493 | 0.492 | **0.488** | 0.481 |

**T = 20000 (N = 911), 65% of cells unobserved** — intermediate:

| method | κ=0 | κ=100 | κ=300 | κ=1000 | κ=3000 |
|---|---:|---:|---:|---:|---:|
| clip | 2.377 | 2.370 | 2.360 | 2.331 | 2.261 |
| abs | 2.333 | 2.318 | 2.293 | 2.218 | 2.046 |
| backoff .1 | 2.225 | 2.211 | 2.188 | 2.118 | 1.961 |
| nmf | 2.367 | 2.358 | 2.343 | 2.242 | 2.075 |
| **sqrtcnt** | 2.036 | 2.003 | 1.969 | **1.894** | 1.747 |

**T = 10000 (N = 2102), 83% of cells unobserved** — the fix is material:

| method | κ=0 | κ=100 | κ=300 | κ=1000 | κ=3000 |
|---|---:|---:|---:|---:|---:|
| clip | 3.114 | 3.087 | 3.045 | 2.929 | 2.656 |
| abs | 3.160 | 3.119 | 3.052 | 2.860 | 2.463 |
| backoff .1 | 3.055 | 3.016 | 2.952 | 2.772 | 2.401 |
| nmf | 3.353 | 3.289 | 3.217 | 2.855 | 2.551 |
| **sqrtcnt** | 3.091 | 2.956 | 2.849 | **2.622** | 2.230 |

It also cuts the *latent* negatives (the model is non-negative anyway, so this is
a side benefit).  `sqrtcnt`: at `N = 159`, 14.4% → 13.3% → 11.9% over
`κ = 0, 1000, 3000`; at `N = 911`, 20.5% → 7.9% → 3.3%; at `N = 2102`,
25.8% → 3.7% → 1.1%.  For `clip`/`abs`/`backoff` the negative fraction
shifts with the reference: 23.8% → 23.4% (`N = 159`), 19.8% → 17.1%
(`N = 911`), 18.1% → 11.9% (`N = 2102`).

Two things to read off carefully:

* **The effect is a property of the vocabulary, not the corpus.**  It is driven
  by the *fraction of unobserved cells* (21% at `N = 159`, 83% at `N = 2102`):
  a fixed `kappa` adds the same mass *per context* `N`, so `alpha = kappa·N`
  grows in proportion to the vocabulary — which is exactly what keeps its
  per-cell effect roughly constant while the matrix gets sparser.  At `N = 159`
  the whole sweep moves `sqrtcnt` by 0.013 bits (0.005 at `κ = 1000`); at
  `N = 2102` it moves it by 0.47 bits at `κ = 1000` and 0.86 over the sweep.
* **Do not choose `kappa` by this KL.**  It decreases monotonically in `kappa`
  for *every* method, because as `kappa → ∞` the reference `M_ref` tends to the
  rank-1 `P_mar`, which any rank-`L` model fits nearly exactly, so the KL tends
  to 0.  `kappa` is a *prior strength* and must be fixed independently — by
  held-out predictive log-likelihood (see below).  The earlier draft's
  conclusion that "smoothing raises the KL" was an artefact of the unnormalised,
  `T`-sized correction.

### Choosing `kappa` by held-out likelihood

How `kappa` is chosen — and why it must **not** be chosen by the KL — is set out
in [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md) §7, together with the held-out
cross-entropy table and the recommendation of a fixed `alpha = 1000·N`
(`kappa = 1000`).  In short: the KL decreases monotonically in `kappa` (as
`kappa → ∞`, `M_ref → P_mar`, which any rank-`L` model fits), so `kappa` is
fixed instead by predictive cross-entropy on a train/test split; the optimum is
a prior mass *per context* ≈10³, constant across a 28× range of `N`.

## Conclusions

0. The square-root factorisation is the default in `pair_matrix.py` (`--no-sqrt`
   for the old count-space behaviour); saved factors carry a `sqrt` flag, and
   squaring the reconstruction gives the model.
1. Factorise `√M` (equivalently, the occurrence-weighted Hellinger embedding)
   and square back.  Best KL at every threshold and every rank ≥ 4; the model is
   non-negative by construction; no extra hyper-parameters.
2. Score with the **joint** KL `KL(M/T ‖ M̂/ΣM̂)`.  It differs from the old
   occurrence-weighted conditional KL only by a model-independent constant, so
   the conditional `p(b|a)` is not needed and has been removed from the code.
3. Put a small independence-shaped prior on unobserved pairs,
   `M_ref = M + kappa·N·P_mar`, with `kappa` a fixed prior mass *per context*
   (not a fraction of the corpus: `alpha` must not scale with `T`).  The
   held-out study gives `kappa ≈ 10³` across a 28× range of `N`, and the code's
   default is `kappa = 1000`.  It changes the reference, so fix it independently
   (held-out likelihood), not by the KL — which decreases monotonically in
   `kappa` as `M_ref → P_mar`.  Construction and `kappa` selection:
   [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md).
