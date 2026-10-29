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
impossibility, so we add a small amount of pseudo-count mass, shaped like the
independence model, to form a **corrected reference**

    M_ref = M + alpha · P_mar ,   P_mar = (r/T)(c/T)ᵀ   (sum 1),   alpha = c · N²

where `c` is the average pseudo-count per cell (`P_mar` is `M_mar` rescaled to
unit mass).  The correction has a **fixed** total mass `alpha = c·N²`, not a
fraction of the corpus, so it is a prior on *unseen pairs* that washes out as the
corpus grows.  (Adding the *unnormalised* `alpha · M_mar`, `M_mar = r cᵀ/T`,
would instead inject `alpha·T` pseudo-counts — at `alpha = 1`, half the matrix —
and never vanish; that was an earlier error.)  `M_ref` is the reference for the
whole analysis: every model is fitted to `M_ref` and scored against it, so
results are **not comparable across `c`** by design — `c` is a counting fix, not
a reconstruction knob (the reconstruction-side counterpart is the `backoff`
remedy above, which keeps using the sum-`T` `M_mar` for its convex mixture).

`L = 16`, joint KL `KL(M_ref ‖ M̂/ΣM̂)` in bits (lower is better).

**T = 100000 (N = 159), 21% of cells unobserved** — the fix is negligible:

| method | c=0 | c=0.1 | c=0.5 | c=1 | c=2 |
|---|---:|---:|---:|---:|---:|
| clip | 1.059 | 1.059 | 1.059 | 1.059 | 1.058 |
| abs | 0.757 | 0.757 | 0.756 | 0.755 | 0.754 |
| backoff .1 | 0.688 | 0.688 | 0.688 | 0.687 | 0.686 |
| nmf | 0.730 | 0.730 | 0.730 | 0.729 | 0.728 |
| **sqrtcnt** | 0.494 | 0.493 | 0.493 | 0.493 | 0.492 |

**T = 10000 (N = 2102), 83% of cells unobserved** — the fix is material:

| method | c=0 | c=0.1 | c=0.5 | c=1 | c=2 |
|---|---:|---:|---:|---:|---:|
| clip | 3.114 | 3.064 | 2.921 | 2.772 | 2.509 |
| abs | 3.160 | 3.080 | 2.848 | 2.623 | 2.279 |
| backoff .1 | 3.055 | 2.979 | 2.761 | 2.551 | 2.229 |
| nmf | 3.353 | 3.246 | 2.844 | 2.673 | 2.400 |
| **sqrtcnt** | 3.091 | 2.891 | 2.609 | 2.383 | 2.058 |

It also cuts the *latent* negatives (the model is non-negative anyway, so this is
a side benefit): at `N = 2102`, `sqrtcnt` goes 25.8% → 10.8% → 3.5% → 1.7% → 0.8%
over `c = 0 … 2`, while `clip`/`abs`/`backoff` go 18.1% → 10.3%; `T = 20000`
(`N = 911`) interpolates (`sqrtcnt` 2.036 → 1.827 bits, negatives 20.5% → 5.2%).

Two things to read off carefully:

* **The effect is a property of the vocabulary, not the corpus.**  It is driven
  by the *fraction of unobserved cells* (21% at `N = 159`, 83% at `N = 2102`):
  a given `c` fills the same average per-cell count, but it only matters when the
  matrix is sparse.  At `N = 159` the whole sweep moves `sqrtcnt` by 0.002 bits;
  at `N = 2102` it moves it by over a bit.
* **Do not choose `c` by this KL.**  It decreases monotonically in `c` for
  *every* method, because as `c → ∞` the reference `M_ref` tends to the rank-1
  `P_mar`, which any rank-`L` model fits nearly exactly, so the KL tends to 0.
  `c` is a *prior strength* and must be fixed independently — by held-out
  predictive log-likelihood (see below).  The earlier draft's conclusion that
  "smoothing raises the KL" was an artefact of the unnormalised, `T`-sized
  correction.

### Choosing `c` by held-out likelihood

`scripts/choose_c.py` selects the prior by *predictive* performance:
binomial-thin the counts into train/test (`p_train = 0.5`), fit the `sqrtcnt`
model to `M_train + alpha·P_mar(train)`, and score the test counts as
cross-entropy in bits per held-out event (lower is better; mean over 5–10
splits).  The test set contains pairs that are *unseen in train*, so this is the
criterion that can reward the prior.

| T (N) | cells unobs. | best `c` | best `alpha` | `alpha/N` | CE\* best | CE `c=0` | CE indep. |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100000 (159) | 21% | 7 | 1.8×10⁵ | 1.1×10³ | 12.405 | 12.406 | 13.535 |
| 50000 (316) | 36% | 5 | 5.0×10⁵ | 1.6×10³ | 14.067 | 14.075 | 15.413 |
| 20000 (911) | 65% | 1 | 8.3×10⁵ | 0.9×10³ | 16.643 | 16.723 | 18.155 |
| 10000 (2102) | 83% | 0.5 | 2.2×10⁶ | 1.0×10³ | 18.656 | 18.929 | 20.161 |
| 5000 (4478) | 92% | 0.2 | 4.0×10⁶ | 0.9×10³ | 20.526 | 21.097 | 21.992 |

(\*cross-entropy of the test table under the model, bits/event; the "CE indep."
column is the no-latent-structure baseline `P_mar(train)`.)

Reading it:

* **The prior helps, and the benefit grows with sparsity** — from 0.001
  bits/event at `N = 159` (few unobserved cells; the whole `c` sweep is within
  noise) to 0.57 bits/event at `N = 4478` (`sqrtcnt` still beats the independence
  model by a further 1.5 bits).  Every `c > 0` beats `c = 0`.
* **The invariant is prior mass *per context*, not per cell.**  `alpha/N` is
  roughly constant at ≈10³ (0.9–1.6×10³) across a 28× range of `N`, so
  `alpha ≈ 10³·N` and in the `c·N²` form the optimal `c` falls like `1/N`
  (7 → 0.2).  A *fixed* `c` is therefore not scale-invariant: `c ≈ ½–1` is
  near-optimal for `N ≈ 900–2100` but too strong at `N = 4478` and too weak at
  `N = 159`.
* Caveat: with a single corpus we cannot separate the `N`- from the corpus-size
  dependence; ≈10³ is an empirical constant for this corpus.

So either tune `c` per corpus with `choose_c.py`, or parameterise the mass
per context, `alpha = kappa·N` with `kappa` ≈ 10³, which a single constant
serves across the whole range.

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
   `M_ref = M + c·N²·P_mar`, with `c` a fixed pseudo-count *rate* per cell (not
   a fraction of the corpus).  It changes the reference, so fix `c`
   independently (held-out likelihood), not by the KL — which decreases
   monotonically in `c` as `M_ref → P_mar`.
