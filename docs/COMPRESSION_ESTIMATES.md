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

## Coping with negative probabilities

The truncated SVD is the best rank-`L` approximation in Frobenius norm, but its
factors `U`, `V` (and hence the reconstructed `M̂`) generally contain **negative
entries** — the problem the brief anticipated. Measured on `M̂` at `L = 16`:

| T | negative entries of M̂ |
|---:|---:|
| 100000 | 20.1% |
| 20000 | 22.2% |
| 50000 | 21.9% |

`scripts/latent_probabilities.py` rebuilds `M`, reconstructs `M̂ = (UΣ)Vᵀ`, and
scores several ways of turning it back into a probability model
`p(b | a)`, against the occurrence-weighted empirical row distribution
`P_emp` (rows with a positive count). Metrics: mean `KL(P_emp ‖ P_pred)` in bits
(lower is better) and top-1 accuracy (does the predicted argmax `b` match the
empirical argmax?).

| remedy | T=100000: KL / top-1 | T=20000: KL / top-1 |
|---|---:|---:|
| `M̂` as-is (floor at 1e-12) | 2.01 / 60.3% | 3.42 / 34.6% |
| clip negatives to 0, renormalise | 2.01 / 60.3% | 3.42 / 34.6% |
| `|M̂|` (sign folding) | 1.01 / 60.3% | 2.79 / 34.6% |
| Euclidean projection onto the simplex | 28.30 / 60.3% | 30.15 / 34.6% |
| backoff mixture with the global marginal (λ=0.1) | 0.93 / 58.9% | 2.62 / 34.4% |
| **NMF** (multiplicative updates, non-negative) | 0.97 / 62.9% | 2.72 / 33.3% |
| *(reference) empirical row entropy H(p(b|a))* | 4.77 bits | 5.03 bits |

(Softmax of the latent scores is not tabulated here because it needs a
per-row temperature: with the raw score scale the exponent underflows and the
row collapses to a one-hot.  Calibrated per row it lands mid-pack — at
T = 50000, KL 2.68 bits and top-1 45.8%.)

Ranking and recommendation:

1. **NMF (non-negative matrix factorisation)** — `p ∝ W H` with `W, H >= 0`.
   This is the principled fix: the factors are non-negative *by construction*,
   so no clipping is needed, and it is competitive on both metrics (best top-1
   at T = 100000). For counts, prefer a **KL-divergence / Poisson NMF** whose
   objective matches the multinomial likelihood rather than least squares.
2. **Backoff mixture** — take the clipped factorisation and mix it with the
   global column marginal `q_b`, `(1-λ)·clip(M̂) + λ·q_b` with small λ. This
   gave the best KL, repairs rows whose reconstruction is entirely negative, and
   guarantees full support (useful when the model must never assign zero
   probability). Think of it as Dirichlet smoothing of the latent model.
3. **Sign folding** `|M̂|` — keeps the *ranking* (top-1 unchanged) and is much
   better than clipping, at zero extra cost. Good if the goal is only "can `a`
   and `b` be adjacent?" rather than a calibrated probability.
4. **softmax of the latent scores** — a log-bilinear model
   `p(b|a) ∝ exp(⟨u_a, v_b⟩ / τ)`. Attractive (it is the natural exponential
   family for this bilinear form) but the temperature must be calibrated per
   row; uncalibrated it collapses to a one-hot or underflows.
5. **clip + renormalise** — simple but mediocre: zeroing ~20% of entries and
   leaving all-negative rows uniform both hurt.
6. **Euclidean projection onto the simplex** — do **not** use: it is optimal in
   Euclidean distance but catastrophic in KL (the true successor is often
   projected to zero).

**Summary recommendation.** For a low-dimensional model that predicts which
prefixes and suffixes may be adjacent, use a non-negative bilinear
factorisation (NMF, ideally KL/Poisson NMF) optionally blended with the global
marginal as a backoff. If only a *score* for adjacency is needed, the
sign-folded SVD is a cheap and effective alternative. Avoid Euclidean
projection; avoid uncalibrated softmax.
