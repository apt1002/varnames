# Fixed-budget compressibility of identifiers

This note estimates how many identifiers can be represented in a fixed budget
(say 64 bits, with ~2 bits reserved for capitalisation style, so also 62 bits)
by a statistical model of identifiers, and studies a low-rank model of which
prefixes and suffixes may sit next to each other.

No concrete bit-packing is proposed here; the aim is a *rate* estimate: the
ideal arithmetic-code length of an identifier under the model, and the fraction
of identifiers (and of real occurrences in source code) whose length fits the
budget. Identifiers that do not fit fall back to a hash + global-dictionary
scheme, so they are counted as failures.

## The model

Case-normalise the corpus to CamelCase (see *CamelCase normalisation* in the
README), wrap each identifier as `^identifier$`, and enumerate the **common
substrings** — substrings of the wrapped identifiers occurring at least *T*
times — for a threshold *T*. The model is the **longest-suffix
(variable-order) successor model**: at each split of `^identifier$` the next
character is predicted by the longest common substring that is a *suffix* of
the prefix, e.g. after `^Ac` the successor is credited to `^Ac` rather than to
`Ac` or `c`. Sparse contexts are smoothed toward the global successor marginal
`q` with a Dirichlet prior (`alpha = 1`):

```
p(c | ctx) = (n_{ctx,c} + alpha * q_c) / (n_ctx + alpha).
```

`scripts/code_lengths.py` computes, for every identifier, the ideal arithmetic
code length

```
L(id) = sum_j  -log2 P(c_j | longest common substring that is a suffix of
                              ^ c_1 ... c_{j-1})
```

which is the number of bits a coder based on the model would spend.

* **Static success rate** = percentage of distinct identifiers in
  `work/camel/merged.txt` (2,295,340 after normalisation) with `L(id) <= budget`.
* **Dynamic success rate** = percentage of *occurrences* in real source code
  with `L(id) <= budget`, weighting each identifier by how often it occurs.
  Occurrences are sampled by `scripts/sample_occurrences.py` (see below); the
  counts are case-normalised by `scripts/normalise_counts.py` so they can be
  joined with the normalised corpus.

### Occurrence sample

`scripts/sample_occurrences.py` draws a random sample of source files per
ecosystem, scrubs each with `extract.scrub`, and counts every identifier
occurrence with `extract.IDENT_RX`:

| ecosystem | files | occurrences | distinct |
|---|---:|---:|---:|
| ruby | 1,200 | 208,015 | 15,599 |
| rust | 1,200 | 1,148,532 | 57,402 |
| go | 1,200 | 936,887 | 52,705 |
| python | 1,200 | 922,232 | 51,873 |
| javascript | 1,200 | 593,413 | 8,526 |
| perl | 752 | 274,601 | 17,304 |
| **all** | | **4,083,680** | **184,414** |

After case normalisation these 184,414 distinct spellings become 174,215
normalised identifiers; 92.65% of the 4,083,680 occurrences match a normalised
corpus identifier. The remaining 7.35% are spellings absent from the corpus
(chiefly keywords, tokens with characters we do not keep, and identifiers from
packages not in the corpus) and would need the fallback.

## Results: success rates vs threshold

| T | common substrings | max len | mean bits | static ≤64 | static ≤62 | dyn ≤64 | dyn ≤62 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100000 | 159 | 5 | 71.45 | 52.3% | 49.6% | 90.5% | 90.2% |
| 50000 | 316 | 5 | 67.03 | 57.8% | 55.2% | 90.9% | 90.7% |
| 20000 | 911 | 7 | 60.17 | 66.4% | 64.1% | 91.3% | 91.2% |
| 10000 | 2,102 | 9 | 55.19 | 72.6% | 70.4% | 91.6% | 91.5% |
| 5000 | 4,478 | 13 | 51.35 | 77.4% | 75.4% | 91.8% | 91.7% |
| 2000 | 11,758 | 14 | 49.21 | 79.8% | 78.0% | 91.9% | 91.8% |
| 1000 | 23,284 | 25 | 44.55 | 86.0% | 84.4% | 92.2% | 92.2% |
| 500 | 46,346 | 33 | 42.51 | 88.7% | 87.3% | 92.3% | 92.3% |

Observations:

* **More contexts keep helping, with diminishing returns.** Each halving of the
  threshold buys a few more points of static coverage; 500→100000 spans
  88.7%→52.3%. The gain is concentrated in the *long tail*: the common, short
  identifiers are already cheap at every threshold.
* **Dynamic coverage saturates near 92%.** Because occurrences are dominated by
  short, highly predictable names, the dynamic rate is essentially flat (90.5%
  → 92.3%) and barely moved by the extra contexts. The last few points of
  *static* coverage are the hardest.
* **~2 bits for capitalisation costs ~1.5–2 points** (compare the ≤64 and ≤62
  columns): reserving capitalisation style is cheap, and cheaper at larger T
  because the model is sharper.
* These are *model-based* numbers. A real coder also needs to spend bits on
  choosing the model, on the fact that the model is fixed, and so on; treat them
  as an upper bound on the achievable rate.

## Prefix/suffix adjacency and its low-rank factorisation

A richer structure than the successor model is the **adjacency of a left and a
right context**. For every split of `^identifier$` define

* `a` = the longest common substring that is a **suffix of the left half**
  (the "left context"; never ends in `$`), and
* `b` = the longest common substring that is a **prefix of the right half**
  (the "right context"; may end in `$`),

and count how often the pair `(a, b)` occurs. This gives a roughly `N x N`
matrix `M` (`N` = number of common substrings, the empty string included as the
backoff context on either side). `scripts/pair_matrix.py` builds `M` and
approximates it as `M ≈ U Vᵀ` with `U` (`N x L`) and `V` (`L x N`), `L << N`.

Density and relative Frobenius error of the randomized-SVD approximation:

| T | N | nnz | density | L=2 | L=4 | L=8 | L=16 | L=32 | L=64 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100000 | 159 | 20,061 | 79.4% | 0.772 | 0.692 | 0.570 | 0.427 | 0.267 | 0.111 |
| 50000 | 316 | 64,434 | 64.5% | 0.835 | 0.779 | 0.693 | 0.588 | 0.455 | 0.286 |
| 20000 | 911 | 292,630 | 35.3% | 0.848 | 0.778 | 0.737 | 0.681 | 0.600 | 0.483 |
| 10000 | 2,102 | 736,006 | 16.7% | 0.823 | 0.784 | 0.749 | 0.711 | 0.657 | 0.575 |
| 5000 | 4,478 | 1,514,392 | 7.6% | 0.830 | 0.809 | 0.784 | 0.756 | 0.715 | 0.649 |

(T = 2000 and below are skipped: the dense `N x N` matrix no longer fits in the
882 MB machine. At T = 5000, `N = 4478` and the build + factorisation already
take ~6.5 min.)

Observations:

* `M` gets **sparser and harder to compress** as `N` grows: at T = 100000 it is
  79% dense (the same few contexts repeat), whereas at T = 5000 it is 7.6%
  dense. A rank-64 factor explains 89% of the Frobenius norm at T = 100000 but
  only 35% at T = 5000. In other words the adjacency of the *frequent* contexts
  is genuinely low-rank, but the long tail of rare contexts is close to
  full-rank (each rare pair is nearly unique).
* The error curve is smooth and, for the smaller sets, decays roughly like a
  power law — there is no obvious "elbow" at which a small latent dimension
  captures most of the mass. A useful low-dimensional model therefore wants a
  modest, not tiny, `L` (tens), and benefits from keeping the backoff ("empty")
  context explicitly.

### L = 1: the independence model vs the leading singular pair

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
| 100000 | 0.987 | 0.975 | 0.856 | 0.841 | 1.623 | 1.704 |
| 50000 | 0.950 | 0.922 | 0.922 | 0.891 | 2.329 | 2.644 |
| 20000 | 0.939 | 0.562 | 0.981 | 0.909 | 3.475 | 4.530 |
| 10000 | 0.928 | 0.293 | 1.023 | 0.890 | 4.340 | 6.762 |
| 5000 | 0.961 | 0.268 | 1.091 | 0.904 | 5.060 | 8.079 |

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

#### Is the row/column asymmetry a bug? (no)

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
  `cos(u₁, prefix) = 0.928`, `cos(v₁, suffix) = 0.293`; the **reversed**
  corpus gives `0.299` and `0.933` — exactly the predicted exchange.
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

### Metric correction: from the conditional to the joint

The KL metric used throughout this report was for a while documented as
"occurrence-weighted" but was actually a plain **uniform** mean over the rows
that occur (it multiplied each row by `P.sum(1)` where `P` is the
*row-normalised* conditional, so every weight was 1).  That was fixed, and the
conditional itself has now been dropped entirely.  By the chain rule

    KL(P(a,b)‖Q(a,b)) = KL(P(a)‖Q(a)) + Σ_a P(a)·KL(P(b|a)‖Q(b|a))

the joint KL splits into a row-marginal term plus the occurrence-weighted
conditional KL; the models leave the prefix marginal `P(a)` fixed, so the
row-marginal term is a **model-independent constant**.  So the weighted
conditional KL, the joint cross-entropy, and the **joint KL
`KL(M/T ‖ M̂/ΣM̂)`** all give the same ranking — and the conditional `p(b|a)`
need never be built.  All KL figures in this report are now the joint KL
`KL(M/T ‖ M̂/ΣM̂)` in bits, computed by `pair_matrix.kl_joint` (see
`docs/HELLINGER_FACTORISATION.md`).  It differs from the old occurrence-weighted
conditional KL only by the small row-marginal mismatch, model by model (`sqrtcnt`
0.480 → 0.494 at T=100000), so every ordering below is unchanged.

## Coping with negative probabilities

(This section analyses the *count-space* factorisation, i.e. `pair_matrix.py
--no-sqrt`.  The default is now the square-root domain, where the model is
non-negative by construction and the remedies below are unnecessary — see
`docs/HELLINGER_FACTORISATION.md`.)

The truncated SVD is the best rank-`L` approximation in Frobenius norm, but its
factors `U`, `V` (and hence the reconstructed `M̂`) generally contain **negative
entries** — the problem the brief anticipated. Measured on `M̂` at `L = 16`:

| T | negative entries of M̂ |
|---:|---:|
| 100000 | 19.5% |
| 50000 | 21.8% |
| 20000 | 21.4% |
| 10000 | 21.1% |

`scripts/latent_probabilities.py` rebuilds `M`, reconstructs `M̂ = (UΣ)Vᵀ`, and
scores several ways of turning it back into a non-negative probability model.
Metric: the joint KL `KL(M/T ‖ M̂/ΣM̂)` in bits (lower is better) — no
conditional `p(b|a)` is formed (see the metric-correction note above).

| remedy | T=100000 | T=50000 | T=20000 |
|---|---:|---:|---:|
| `M̂` as-is (clip negatives to 0) | 1.072 | 1.648 | 2.528 |
| `|M̂|` (sign folding) | 0.765 | 1.352 | 2.423 |
| Euclidean projection onto the simplex | 23.40 | 22.86 | 22.04 |
| backoff mixture with the independence model (λ=0.1) | 0.695 | 1.244 | 2.256 |
| **NMF** (multiplicative updates, non-negative) | 0.730 | 1.290 | 2.367 |
| **`sqrtcnt`: square-root SVD, squared back** | **0.504** | **1.006** | **2.034** |

(cells are joint KL in bits, randomised SVD.  `sqrtcnt` is the model
recommended in `docs/HELLINGER_FACTORISATION.md` and computed by
`latent_probabilities.py` alongside the count-space remedies; it reads a little
above the exact 0.494 / 0.990 / 2.016.)

(Softmax of the latent scores is not tabulated here because it needs a
calibration scale: with the raw score scale the exponent underflows and the
matrix collapses to a one-hot.  Calibrated it lands mid-pack — at T = 50000,
joint KL ≈ 2.93.)

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
2. **Backoff mixture** — take the clipped factorisation and mix it with the
   rank-1 independence model `M_mar = r cᵀ / T`, `(1-λ)·clip(M̂) + λ·M_mar`
   with small λ. This repairs entries whose reconstruction is negative and
   guarantees full support (useful when the model must never assign zero
   probability). Think of it as Dirichlet smoothing of the latent model.
3. **Sign folding** `|M̂|` — preserves the ordering of the latent scores and is
   much better than clipping, at zero extra cost. Good if the goal is only "can
   `a` and `b` be adjacent?" rather than a calibrated probability.
4. **softmax of the latent scores** — a log-bilinear model
   `M̂ ∝ exp(⟨u_a, v_b⟩ / τ)`. Attractive (it is the natural exponential
   family for this bilinear form) but the temperature must be calibrated; the
   raw score scale makes the exponent underflow and collapses the model to a
   one-hot.
5. **clip negatives to 0** — simple but mediocre: zeroing ~20% of the entries
   hurts.
6. **Euclidean projection onto the simplex** — do **not** use: it is optimal in
   Euclidean distance but catastrophic in KL (the true successor is often
   projected to zero).

**Summary recommendation.** For a low-dimensional model that predicts which
prefixes and suffixes may be adjacent, use a non-negative bilinear
factorisation (NMF, ideally KL/Poisson NMF) optionally blended with the global
marginal as a backoff. If only a *score* for adjacency is needed, the
sign-folded SVD is a cheap and effective alternative. Avoid Euclidean
projection; avoid uncalibrated softmax.
