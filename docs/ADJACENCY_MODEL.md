# The low-rank prefix/suffix adjacency model

This note studies a low-rank model of which prefixes and suffixes may sit next
to each other — a richer structure than the character successor model of
[`CODE_LENGTHS.md`](CODE_LENGTHS.md). It is an independent line of research:
the question is whether the adjacency of left and right contexts can be captured
by a small number of latent dimensions, and how best to turn a low-rank
factorisation back into a probability model.

The square-root (Hellinger) factorisation, now the default, is developed in its
own companion report [`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md).

## The model

The construction of `M` — the corpus preparation, the common-substring
vocabulary, the longest-common-suffix/prefix edge rule, the empty backoff
context, the reversal-symmetry invariant and the density — is documented once in
[`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md); the properties we use are
summarised there. `scripts/pair_matrix.py` builds `M` and approximates it as
`M ≈ U Vᵀ` with `U` (`N x L`) and `V` (`L x N`), `L << N`.

Relative Frobenius error of the randomized-SVD approximation in the
**square-root (Hellinger) domain**, `√M ≈ (U Σ Vᵀ)_L` (the current default), for
the vocabulary sizes of [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md):

| T | N | nnz | density | L=2 | L=4 | L=8 | L=16 | L=32 | L=64 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100000 | 159 | 20,061 | 79.4% | 0.615 | 0.552 | 0.486 | 0.399 | 0.283 | 0.136 |
| 50000 | 316 | 64,434 | 64.5% | 0.713 | 0.656 | 0.600 | 0.525 | 0.422 | 0.286 |
| 20000 | 911 | 292,630 | 35.3% | 0.805 | 0.761 | 0.713 | 0.651 | 0.567 | 0.458 |
| 10000 | 2,102 | 736,006 | 16.7% | 0.849 | 0.812 | 0.770 | 0.716 | 0.641 | 0.545 |
| 5000 | 4,478 | 1,514,392 | 7.6% | 0.880 | 0.848 | 0.811 | 0.763 | 0.695 | 0.610 |

(T = 2000 and below are skipped: the dense `N x N` matrix no longer fits in the
882 MB machine. At T = 5000, `N = 4478` and the build + factorisation already
take ~6.5 min.)

Observations:

* `M` gets **sparser and harder to compress** as `N` grows: at T = 100000 it is
  79% dense (the same few contexts repeat), whereas at T = 5000 it is 7.6%
  dense. A rank-64 factor explains 86% of the Frobenius norm at T = 100000 but
  only 39% at T = 5000. In other words the adjacency of the *frequent* contexts
  is genuinely low-rank, but the long tail of rare contexts is close to
  full-rank (each rare pair is nearly unique).
* The error curve is smooth and, for the smaller sets, decays roughly like a
  power law — there is no obvious "elbow" at which a small latent dimension
  captures most of the mass. A useful low-dimensional model therefore wants a
  modest, not tiny, `L` (tens), and benefits from keeping the backoff ("empty")
  context explicitly.

## L = 1: the independence model vs the leading singular pair

The rank-1 factorisation has a clean interpretation. Write `M ≈ σ u vᵀ` with
unit `u, v`; then the implied conditional is `p(b | a) = v_b / Σ_b v_b`, a
function of `b` alone — i.e. **the right context is independent of the left**.
The question is *which* `v`, and the answer depends on the objective:

* the **maximum-likelihood** (KL / Poisson) rank-1 fit is the independence
  model `M_mar = r cᵀ / T` with `r = M 1`, `c = Mᵀ 1`, `T = 1ᵀM1` — literally
  "global distribution over prefixes times global distribution over suffixes";
* the **Frobenius** rank-1 fit is the leading SVD term `σ₁ u₁ v₁ᵀ`.

`scripts/rank1_marginals.py` compares them. `cos(u₁, r/‖r‖)` and
`cos(v₁, c/‖c‖)` measure how close the SVD vectors are to the marginals
(1.0 = same direction); the same two rank-1 models are then scored as
probability models.

| T | cos(u₁, prefix marg.) | cos(v₁, suffix marg.) | relerr marg. | relerr r1 | KL marg. | KL r1 |
|---:|---:|---:|---:|---:|---:|---:|
| 100000 | 0.984 | 0.976 | 0.856 | 0.840 | 1.623 | 1.704 |
| 50000 | 0.957 | 0.924 | 0.922 | 0.891 | 2.329 | 2.591 |
| 20000 | 0.939 | 0.563 | 0.982 | 0.909 | 3.475 | 4.514 |
| 10000 | 0.932 | 0.294 | 1.024 | 0.890 | 4.340 | 6.576 |
| 5000 | 0.962 | 0.268 | 1.093 | 0.905 | 5.060 | 7.990 |

(KL in bits, computed as the **joint** KL `KL(M/T ‖ M̂/ΣM̂)`; `relerr` is the
relative Frobenius error.)

Observations:

* The leading **left** singular vector stays close to the prefix marginal
  (`cos ≈ 0.93–0.99` at every threshold): the row space is dominated by a few
  very frequent left contexts, so `u₁` and `r` point the same way almost
  regardless of `N`.
* The leading **right** singular vector falls away from the suffix marginal as
  `N` grows (`0.98 → 0.92 → 0.56 → 0.29 → 0.27`): the column space has a long,
  heavy tail, and least squares, dominated by the few largest counts, latches
  onto a direction that is not the one the mass of contexts actually follows.
  By `T = 10000` `v₁` is close to orthogonal to `c`, and it stops falling
  after that (the direction that least squares prefers stabilises).
* Consequently the Frobenius rank-1 wins on **Frobenius error** at every
  threshold, while the marginal model wins on **KL** at every threshold, and by
  a widening margin. Because `v₁` is nearly orthogonal to `c`, the SVD rank-1
  spreads its mass along a suffix direction that the mass of contexts does not
  follow; so from `T = 10000` down the independence model even has `relerr > 1`
  — it is further from `M` than the zero matrix — and is *still* the better
  probability model. Optimising the wrong norm does not merely mis-calibrate
  the probabilities, it can move them further from the empirical distribution.

This is the concrete form of the "the objective decides the answer" point, and
it is the sharpest argument for fitting the adjacency model in **KL/Poisson**
rather than least squares.

### Is the row/column asymmetry a bug? (no)

The construction is symmetric under *reversing* the identifiers: a left
context (longest common **suffix of the left half**) becomes a right context
(longest common **prefix of the right half**) under `s ↦ φ(s)` = reverse and
swap `^`↔`$`. So one might expect the row and column behaviour to match, and
the large gap in the table above looks suspicious. It is not a bug.
`scripts/symmetry_check.py` verifies three things:

* **Entrywise.** Building `M` on the corpus and `Mᴿ` on the corpus with every
  identifier reversed, `Mᴿ[φ(b), φ(a)] = M[a, b]` **exactly** (relative
  Frobenius residual `0.0`, max discrepancy `0` against a max count of
  104,614). `φ` maps the two vocabularies onto each other with no missing
  entries.
* **The cosines swap.** At `T = 10000` the corpus gives
  `cos(u₁, prefix) = 0.932`, `cos(v₁, suffix) = 0.294`; by the exact reversal
  symmetry above the **reversed** corpus gives the exchange, `0.294` and
  `0.932`.
* **Symmetric data ⇒ symmetric behaviour.** Run on a synthetic
  reversal-closed corpus (every identifier and its reverse), an *exact* SVD
  gives `cos(u₁, r) = cos(v₁, c) = 0.779237`, agreement to `5e-15`.

So the asymmetry is a genuine property of the **data**: the corpus is not
reversal-symmetric, i.e. `M` is not equal to `φ Mᵀ φ`, or equivalently the
distribution of contexts that *precede* a split differs from those that
*follow* it. Measured over the left contexts, `cos(r_C, φ(c_C)) = 0.787`: the
two marginals are strongly but not perfectly correlated. The pattern is
morphological — English word-parts sit preferentially at the front or the back
of identifiers. Examples (count as a preceding context vs a following one, at
`T = 10000`):

| string | as left context | as right context |
|---|---:|---:|
| `test` | 3,471 | 107,952 |
| `est` | 30,190 | 135,882 |
| `ion` | 5,924 | 119,680 |
| `St` | 89,697 | 15,213 |
| `h` | 44,510 | 155,475 |

So reversing the corpus is a genuinely different (though related) dataset, and
the row/column behaviours legitimately differ. Two caveats: (i) the reported
`cos` values come from a *randomised* SVD and carry a small approximation
error (≈0.02 in a small-`N` control), which does not affect the large
asymmetry; (ii) the effect is a property of *identifier* corpora in general —
English-like word structure — and would largely vanish on reversal-symmetric
data.

## Metric: the joint KL

The KL metric used throughout is the **joint** KL `KL(M/T ‖ M̂/ΣM̂)` in bits,
computed by `pair_matrix_lib.kl_joint`. It was for a while documented as
"occurrence-weighted" but was actually a plain **uniform** mean over the rows
that occur; and for a while a conditional `p(b|a)` was formed. Both are gone.
By the chain rule

    KL(P(a,b)‖Q(a,b)) = KL(P(a)‖Q(a)) + Σ_a P(a)·KL(P(b|a)‖Q(b|a))

the joint KL splits into a row-marginal term plus the occurrence-weighted
conditional KL; the models leave the prefix marginal `P(a)` fixed, so the
row-marginal term is a **model-independent constant**. So the weighted
conditional KL, the joint cross-entropy, and the **joint KL
`KL(M/T ‖ M̂/ΣM̂)`** all give the same ranking — and the conditional `p(b|a)`
need never be built (`sqrtcnt` 0.480 → 0.494 at T=100000). See
`docs/HELLINGER_FACTORISATION.md`.

## Coping with negative probabilities

(This section analyses the *count-space* factorisation, i.e. `pair_matrix.py
--no-sqrt`. The default is now the square-root domain, where the model is
non-negative by construction and the remedies below are unnecessary — see
`docs/HELLINGER_FACTORISATION.md`.)

The truncated SVD is the best rank-`L` approximation in Frobenius norm, but its
factors `U`, `V` (and hence the reconstructed `M̂`) generally contain **negative
entries**. Measured on `M̂` at `L = 16`:

| T | negative entries of M̂ |
|---:|---:|
| 100000 | 20.1% |
| 50000 | 21.7% |
| 20000 | 19.8% |
| 10000 | 18.1% |

`scripts/latent_probabilities.py` rebuilds `M`, reconstructs `M̂ = (UΣ)Vᵀ`, and
scores several ways of turning it back into a non-negative probability model.
Metric: the joint KL `KL(M/T ‖ M̂/ΣM̂)` in bits (lower is better) — no
conditional `p(b|a)` is formed.

| remedy | T=100000 | T=50000 | T=20000 |
|---|---:|---:|---:|
| `|M̂|` (sign folding) | 0.757 | 1.298 | 2.333 |
| Euclidean projection onto the simplex | 23.37 | 22.85 | 22.07 |
| backoff mixture with the independence model (λ=0.1) | 0.688 | 1.213 | 2.225 |
| **NMF** (multiplicative updates, non-negative) | 0.730 | 1.290 | 2.367 |
| **`sqrtcnt`: square-root SVD, squared back** | **0.493** | **0.990** | **2.036** |

(cells are joint KL in bits, randomised SVD.  `sqrtcnt` is the model
recommended in `docs/HELLINGER_FACTORISATION.md` and computed by
`latent_probabilities.py` alongside the count-space remedies; with the
re-orthonormalised randomised SVD (`n_iter = 8`) it now agrees with the exact
SVD to ~0.003 bits.)

Ranking and recommendation:

0. **Square-root (Hellinger) factorisation** `M̂ = (√M reconstruction)²` — the
   recommended model and now the default; non-negative by construction and the
   lowest KL by a wide margin.  The count-space remedies below are only for
   when you are stuck with the old `--no-sqrt` factorisation.  See
   `docs/HELLINGER_FACTORISATION.md`.
1. **NMF (non-negative matrix factorisation)** — `M̂ = W H` with `W, H >= 0`.
   This is the principled fix: the factors are non-negative *by construction*,
   so no clipping is needed, and it is competitive on KL while never producing
   a negative entry. For counts, prefer a **KL-divergence / Poisson NMF**
   whose objective matches the multinomial likelihood rather than least squares.
2. **Backoff mixture** — take the reconstructed factorisation and mix it with
   the rank-1 independence model `M_mar = r cᵀ / T`,
   `(1-λ)·M̂ + λ·M_mar` with small λ. This repairs entries whose reconstruction
   is negative and guarantees full support. Think of it as Dirichlet smoothing
   of the latent model; it trades some sharpness for robustness.
3. **Sign folding** `|M̂|` — preserves the ordering of the latent scores and is
   much better than discarding negative entries, at zero extra cost. Good if the
   goal is only "can `a` and `b` be adjacent?" rather than a calibrated
   probability.
4. **Euclidean projection onto the simplex** — do **not** use: it is optimal in
   Euclidean distance but catastrophic in KL (the true successor is often
   projected to zero).

**Summary recommendation.** For a low-dimensional model that predicts which
prefixes and suffixes may be adjacent, use a non-negative bilinear
factorisation (NMF, ideally KL/Poisson NMF) optionally blended with the global
marginal as a backoff. If only a *score* for adjacency is needed, the
sign-folded SVD is a cheap and effective alternative. Avoid Euclidean
projection.

## Reproducing

```sh
python3 scripts/pair_matrix.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000 \
        --lsvd 2,4,8,16,32,64
python3 scripts/rank1_marginals.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000
python3 scripts/latent_probabilities.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000 --L 16
python3 scripts/symmetry_check.py work/camel/merged.txt \
        work/common10000/common_substrings.txt \
        work/rev/merged_rev.txt work/rev/common10000/common_substrings.txt
```

`scripts/run_sweep.sh` runs the factorisation over a list of thresholds.
