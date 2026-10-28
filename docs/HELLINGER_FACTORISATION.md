# Hellinger (square-root) factorisation of the adjacency matrix, and smoothing

Status: draft. All numbers are the occurrence-weighted mean `KL(P_emp ‖ p̂)` in
bits (lower is better) unless a column says otherwise; `P_emp` is the
row-normalised empirical conditional `p(b|a)`, `p̂` the model.

## Big idea

SVD minimises squared L2 error; the model is scored by KL.  For probability
vectors the square-root map is an isometry,

    ‖√p − √q‖² = 2 H²(p, q) ≈ 2 KL(p ‖ q)   for p ≈ q,

so factorise the Hellinger embeddings `X = √P` (rows unit norm) rather than `M`,
and **square the reconstruction back**: `p̂(b|a) ∝ x̂²`, `x̂ = (U Σ Vᵀ)_L`.

Two consequences:

* The reconstruction is minimised in the metric that matches KL, not the count
  scale.  This is worth far more than anything done to the raw SVD.
* The square is non-negative *however signed the latent scores are*, so the
  **model never has negative probabilities** — the negatives survive only in the
  latent `x̂`, where they are harmless (they perturb the Hellinger-space fit, not
  a probability).  So negative *probabilities* were never the real problem.

Two weightings, which turn out to be related:

* `hell` — SVD of `√P`, all rows equal.
* `hellw` — SVD of `diag(√N_a)·√P` then divide by `√N_a`, the exact minimiser of
  the occurrence-weighted `Σ_a N_a ‖x_a − x̂_a‖²`.
* `sqrtcnt` — the count-scale analogue, SVD of `√M` elementwise.  Because
  `√M[a,b] = √(N_a) · x_a,b`, this is *identical* to `hellw` (verified to 4 d.p.
  with the exact SVD); dividing by `√N_a` and renormalising cancels.  **Rooting
  the counts is the same as occurrence-weighting the Hellinger fit.**

## Metric correction (important)

The KL metric used so far (in `latent_probabilities.py`, `rank1_marginals.py`
and the report) is documented as "occurrence-weighted", but it is not: it
weights each row by `P.sum(1)`, and `P` is row-normalised, so every weight is 1.
It is a plain **uniform** mean over rows.  A genuinely occurrence-weighted mean
needs the raw row counts passed separately.

The two metrics can even disagree on the winner, so this matters (see below).

## Results

`L = 16`, `alpha = 0`, exact SVD.  `sqrtcnt ≡ hellw`.

Occurrence-weighted KL (bits):

| threshold (N) | clip | abs | backoff .1 | nmf | **hellw** | hell | independence |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100000 (159) | 1.174 | 0.732 | 0.679 | 0.719 | **0.480** | 0.552 | 1.623 |
| 50000 (316) | 1.672 | 1.265 | 1.199 | 1.278 | **0.945** | 1.046 | 2.329 |
| 20000 (911)* | 2.630 | 2.333 | 2.206 | 2.292 | **1.860** | 1.997 | 3.475 |

\* randomised SVD (exact is 31 s on N=911 with reference BLAS).

The pipeline's randomised SVD gives the same picture (T = 100000 and 50000,
`L = 16`, `alpha = 0`, occurrence-weighted): `hellw` 0.493 / 0.964 vs exact
0.480 / 0.945, `hell` 0.575 / 1.065, `backoff` 0.685 / 1.228 — i.e. the exact /
randomised difference is ~0.02 bits and does not touch the ordering.

Uniform KL (the metric reported until now):

| threshold | clip | abs | backoff .1 | nmf | hellw | **hell** | independence |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100000 | 1.525 | 0.995 | 0.920 | 0.970 | 0.643 | **0.589** | 1.952 |
| 50000 | 2.009 | 1.584 | 1.501 | 1.594 | 1.174 | **1.122** | 2.696 |
| 20000* | 3.056 | 2.779 | 2.623 | 2.712 | 2.213 | **2.196** | 3.919 |

**The winner flips with the metric.**  On the metric we actually want
(occurrence-weighted) the *weighted* Hellinger fit `hellw` wins; on the uniform
metric the unweighted `hell` wins.  That is exactly what theory predicts, and it
is independent evidence that the occurrence-weighted metric is the right one to
report.

## Rank dependence (T = 100000, exact, occurrence-weighted)

| L | clip | abs | backoff .1 | nmf | **hellw** | hell |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 1.491 | 1.386 | 1.380 | 1.433 | **1.372** | 1.449 |
| 4 | 1.401 | 1.149 | 1.129 | 1.182 | **1.074** | 1.105 |
| 8 | 1.340 | 0.962 | 0.930 | 0.970 | **0.778** | 0.840 |
| 16 | 1.174 | 0.732 | 0.679 | 0.719 | **0.480** | 0.552 |
| 32 | 0.833 | 0.451 | 0.399 | 0.462 | **0.212** | 0.277 |
| 64 | 0.390 | 0.189 | 0.168 | 0.229 | **0.046** | 0.073 |

`hellw` wins at every rank from L=4 up, and by a factor approaching 4× at
L=64 (0.046 vs 0.168 for the best previous remedy).  The advantage *grows* with
L: the Hellinger space makes the extra ranks count.

## Smoothing towards independence

Add `alpha · M_mar`, `M_mar = r cᵀ / T`, before factorising (the user's second
idea).  It does what was hoped and something was not:

* it **reduces the latent negatives**, a lot — `hell` goes 14% → 4% → 1% at
  `alpha = 0, 0.05, 0.2` (T=100000);
* but it **raises the KL** for every good method.  At T=100000 (weighted):
  `hellw` 0.480 → 0.487 → 0.543, `hell` 0.552 → 0.557 → 0.607, `nmf` 0.719 →
  0.716 → 0.733;
* it does help the *naive* family: `clip` improves 1.174 → 1.090 → 0.973, but
  never gets near `hellw` at `alpha = 0`.

So smoothing is a trade of KL for fewer negatives — and since the squared
reconstruction already gives a non-negative *model*, the negatives it removes
are only in the latent scores, so it buys nothing worth the KL it costs.

## Tentative conclusions

1. Factorise `√M` (equivalently, the occurrence-weighted Hellinger embedding)
   and square back.  Best KL at every threshold and every rank; model is
   non-negative by construction; no extra hyper-parameters.
2. The count-scale root `sqrtcnt` is not an approximation to the weighted
   Hellinger fit — it *is* it.
3. Don't smooth `M` towards independence unless you specifically need the latent
   scores to be non-negative; it costs KL.
