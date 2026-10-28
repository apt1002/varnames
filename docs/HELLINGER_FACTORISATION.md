# Square-root (Hellinger) factorisation of the adjacency matrix, and smoothing

Status: the square-root (Hellinger) factorisation is the **default** in
`scripts/pair_matrix.py` (saved `pair_factors_L*.npy` carry a `sqrt` flag;
`--no-sqrt` restores the old count-space behaviour).  The metric is now the
**joint** KL, `KL(M/T ‖ M̂/ΣM̂)` in bits (lower is better), computed by
`pair_matrix.kl_joint`; no conditional `p(b|a)` is formed anywhere any more.

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
| 20000 (911)* | 2.528 | 2.423 | 2.256 | 2.367 | **2.016** | 3.475 |

\* randomised SVD (exact is ~30 s per factorisation on N=911 with reference
BLAS).  The randomised values are within ~0.02 bits and keep the ordering.

`sqrtcnt` wins at every threshold — the Hellinger factorisation is worth more
than any of the "cope with negatives" remedies, and it needs none.

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

## Smoothing towards independence

Add `alpha · M_mar`, `M_mar = r cᵀ / T`, before factorising.  It does what was
hoped, and something was not:

* it **reduces the latent negatives**, a lot — `sqrtcnt` goes 14.4% → 8.7% →
  4.7% at `alpha = 0, 0.05, 0.2` (T=100000);
* but it **raises the KL** for every good method.  At T=100000 (joint KL):
  `sqrtcnt` 0.494 → 0.498 → 0.549, `nmf` 0.730 → 0.726 → 0.742;
* it does help the *naive* family: `clip` improves 1.059 → 0.994 → 0.908, but
  never gets near `sqrtcnt` at `alpha = 0`.

So smoothing trades KL for fewer negatives — and since the squared
reconstruction already gives a non-negative *model*, the negatives it removes
are only in the latent scores, so it buys nothing worth the KL it costs.

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
3. Don't smooth `M` towards independence unless you specifically need the latent
   scores to be non-negative; it costs KL.
