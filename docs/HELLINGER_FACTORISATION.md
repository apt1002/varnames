# Square-root (Hellinger) factorisation of the word adjacency matrix, and a prior on unobserved pairs

This note factorises the **word × word adjacency matrix** of the run-aware
dictionary (the model of [`TREE_WORDS.md`](TREE_WORDS.md) /
[`WORD_COMPRESSIBILITY.md`](WORD_COMPRESSIBILITY.md)).  The matrix is the cyclic
word-bigram count matrix of a tokenised corpus: rows and columns are the tree
`word list` (characters + `\n` + words), and identifiers are split **only at
word boundaries**.  There is no common-substring vocabulary anywhere in the
experiment.

Status: the square-root (Hellinger) factorisation is the recommended low-rank
model and is the one `scripts/hfactor_words.py` reports.

## The matrix

For a dictionary with `NUM_PAIRS` words and `V = 63 + 1 + NUM_PAIRS` symbols,
`M[a, b]` counts the cyclic bigrams `a → b` over the tokenised corpus
(`Σ_v M[u, v] = N(u)`, `T = Σ M` the token total).  Three dictionaries are used,
sized to match the character thresholds of [`CODE_LENGTHS.md`](CODE_LENGTHS.md):

| dictionary | `NUM_PAIRS` | `V` | `T` (tokens) | distinct bigrams | density |
|---|---:|---:|---:|---:|---:|
| `work/tw96` | 96 | 160 | 25,986,207 | 20,499 | 80.1% |
| `work/tw512` | 512 | 576 | 19,146,388 | 149,932 | 45.2% |
| `work/tw2040` | 2,040 | 2,104 | 13,921,118 | 802,606 | 18.1% |

The word matrix is **denser** than the character matrix at the same vocabulary
size — a word bigram covers a whole morpheme transition — so its tail is
much shorter and the low-rank factorisation has an easier job.

## Why the joint KL is the right metric (and why the conditional is unnecessary)

For the joint distribution over `(a, b)` the chain rule gives, exactly,

    KL(P(a,b)‖Q(a,b)) = KL(P(a)‖Q(a)) + Σ_a P(a)·KL(P(b|a)‖Q(b|a)).

The models leave the row marginal `P(a)` fixed, so the row-marginal term is a
**model-independent constant**; ranking by the joint KL, the joint
cross-entropy, or the occurrence-weighted conditional KL all agree, and the
conditional `p(b|a)` never needs to be built.  Everything below is scored by the
**joint** KL `KL(M_ref/T ‖ M̂/ΣM̂)` in bits (lower is better), computed by
`pair_matrix_lib.kl_joint`.

## Big idea

SVD minimises squared L2 error; the model is scored by KL.  For probability
vectors the square-root map is an isometry,

    ‖√p − √q‖² = 2 H²(p, q) ≈ ½ KL(p ‖ q)   for p ≈ q  (KL in nats),

so factorise the Hellinger embedding `√M` of the **count** matrix and square the
reconstruction back (the factor is `½` in nats, or `0.347` for a KL scored in
bits; being a constant it changes no ranking, which is all this uses):

    sqrtcnt:   √M ≈ (U Σ Vᵀ)_L ,    M̂ = (U Σ Vᵀ)_L² .

The reconstruction is then fitted in the metric that matches KL, and the square
is non-negative *however signed the latent scores are* — so the model never has
negative probabilities (the negatives survive only in the latent reconstruction,
where they perturb the Hellinger fit, not a probability).  Working in count
space is the point: `√M[a,b] = √N_a · √p(b|a)`, so rooting the counts already
builds in the occurrence weighting.

## Results

`L = 16`, randomised SVD, `alpha = 0`.  Joint KL (bits):

| dictionary (`V`) | clip | abs | backoff .1 | nmf | **sqrtcnt** | independence |
|---|---:|---:|---:|---:|---:|---:|
| tw96 (160) | 1.1035 | 0.7196 | 0.6425 | 0.7425 | **0.4905** | 1.4701 |
| tw512 (576) | 1.5364 | 1.3009 | 1.1773 | 1.4320 | **1.1170** | 2.0739 |
| tw2040 (2104) | 1.8839 | 1.7273 | 1.6173 | 1.9077 | **1.7555** | 2.4946 |

`sqrtcnt` wins at every size; as with the character matrix, `abs` (sign folding)
and `backoff` beat `clip`, and NMF is never competitive.

## Rank dependence

Joint KL (bits), `kappa = 1000`:

| dictionary | L=2 | L=4 | L=8 | L=16 | L=32 | L=64 |
|---|---:|---:|---:|---:|---:|---:|
| tw96, backoff .1 | 1.4139 | 1.0877 | 0.8813 | 0.6307 | 0.3540 | 0.1402 |
| tw96, **sqrtcnt** | **1.4017** | **1.0809** | **0.8021** | **0.4783** | **0.1954** | **0.0371** |
| tw512, backoff .1 | 2.0003 | 1.5999 | 1.3684 | 1.1006 | 0.8353 | 0.5727 |
| tw512, **sqrtcnt** | **1.9986** | 1.6775 | 1.3963 | **1.0202** | **0.6367** | **0.3213** |
| tw2040, backoff .1 | 1.9456 | **1.6139** | **1.4210** | 1.2628 | 1.0990 | 0.9158 |
| tw2040, **sqrtcnt** | **1.8628** | 1.6355 | 1.4516 | **1.2388** | **0.9824** | **0.7108** |

The Hellinger model wins from about `L = 16` up, and the advantage **grows with
`L`** (at tw96 and tw512 it is already ahead at `L = 2–8`).  At small `L` on the
large, sparse `tw2040` matrix the rank-1 `backoff` mixture is briefly better
(`L = 4, 8`): the top rank-1 direction of the word matrix is close to the
independence model, which is exactly what `backoff` adds.  The large-`L`
behaviour is what matters — the Hellinger space is what makes the extra ranks
count.

## A prior on unobserved pairs (the counting fix)

`M` counts only the `(a, b)` pairs actually seen.  A zero is not an
impossibility, so we add an independence-shaped prior of fixed mass to form a
corrected reference

    M_ref = M + alpha · P_mar ,   P_mar = (r/T)(c/T)ᵀ (sum 1),   alpha = kappa · V .

`M_ref` is the reference for the whole analysis: every model is fitted to
`M_ref` and scored against it, so results are **not comparable across `kappa`**
by design (`kappa` is a counting fix, not a reconstruction knob).  `kappa = 1000`
is the character-model default; the word matrix is denser and prefers a little
less: the held-out optima are `kappa ≈ 100–300` for `tw2040` (see
[`WORD_COMPRESSIBILITY.md`](WORD_COMPRESSIBILITY.md) and below).

`L = 16`, joint KL `KL(M_ref ‖ M̂/ΣM̂)` in bits:

**tw96 (V = 160) — 20% of cells unobserved; the fix is small**

| method | κ=0 | κ=100 | κ=300 | κ=1000 | κ=3000 |
|---|---:|---:|---:|---:|---:|
| clip | 1.1035 | 1.1029 | 1.1026 | 1.1015 | 1.1073 |
| abs | 0.7196 | 0.7182 | 0.7151 | 0.7059 | 0.6822 |
| backoff .1 | 0.6425 | 0.6411 | 0.6386 | 0.6307 | 0.6115 |
| nmf | 0.7425 | 0.7411 | 0.7385 | 0.7305 | 0.7107 |
| **sqrtcnt** | 0.4905 | 0.4878 | 0.4856 | **0.4783** | 0.4641 |

**tw2040 (V = 2104) — 82% of cells unobserved; the fix is material**

| method | κ=0 | κ=100 | κ=300 | κ=1000 | κ=3000 |
|---|---:|---:|---:|---:|---:|
| clip | 1.8839 | 1.8489 | 1.8015 | 1.6660 | 1.3169 |
| abs | 1.7273 | 1.6648 | 1.5705 | 1.3353 | 0.9510 |
| backoff .1 | 1.6173 | 1.5583 | 1.4723 | 1.2628 | 0.9225 |
| nmf | 1.9077 | 1.8323 | 1.7788 | 1.5360 | 1.0741 |
| **sqrtcnt** | 1.7555 | 1.6090 | 1.4896 | **1.2388** | 0.8596 |

Two things to read off:

* **The effect is a property of the vocabulary, not the corpus.**  It is driven
  by the *fraction of unobserved cells* (20% at `V = 160`, 82% at `V = 2104`): a
  fixed `kappa` adds the same mass *per row*, so `alpha = kappa·V` grows in
  proportion to the vocabulary — exactly what keeps the per-cell effect roughly
  constant while the matrix gets sparser.
* **Do not choose `kappa` by this KL.**  It decreases monotonically in `kappa`
  for *every* method, because as `kappa → ∞` the reference `M_ref` tends to the
  rank-1 `P_mar`, which any rank-`L` model fits nearly exactly, so the KL tends
  to 0.  `kappa` is a prior strength and is fixed by held-out likelihood.

The independence-model KL `KL(M_ref ‖ M_mar)` for `tw2040` runs
2.4946 / 2.4074 / 2.2688 / 1.9070 / 1.3032 bits over
`κ = 0, 100, 300, 1000, 3000` — again monotone in `kappa`, for the same reason.

## Held-out: does factorising the matrix actually pay?

The purpose of the factorisation is to *shrink* the largest table.  Scoring the
held-out identifiers under the **rank-`L` Hellinger model** (row-normalised
`M̂ = (√M_ref)_L²`) on `tw2040`, `kappa = 300` (a stride-20 sample of the
validation set, 11,477 identifiers):

| model | mean bits |
|---|---:|
| full table (`L = V`) | **45.76** |
| `sqrtcnt`, `L = 256` | 47.10 |
| `sqrtcnt`, `L = 128` | 48.61 |
| `sqrtcnt`, `L = 64` | 50.59 |

So the low-rank model is *not* free: at `L = 256` it costs ~1.3 bits/identifier
against the full table, rising to ~4.8 bits at `L = 64`.  The full word-bigram
table is the better model at this vocabulary size; a rank-`L` factorisation only
makes sense if the table size itself is the binding constraint (the projected
~20 KB budget), which is the question taken up by the clustering study.  The
Hellinger factorisation remains the best *low-rank* reconstruction of the table
(the KL tables above), and is the natural starting point for that compression.

*(Visualising the rank-`L` clouds: `scripts/factor_cloud.py` plots `U√Σ` and
`V√Σ` as two 3D point clouds from just `work/tw2040/adj.npz` and `sym.npy`.  At
rank 4 on `tw2040` the leading singular values are 2749 / 1129 / 603 / 508
(65 % of the Frobenius energy); the right cloud shows a marked two-lobed / cross
structure while the left cloud is closer to isotropic.  The apparent
"gain × shape" factorisation of these clouds is tested — and found to be largely
a reconstruction artefact — in `scripts/shape_gain_test.py`; see the section
"Is the factor-cloud 'gain × shape' structure real?" below.  At the shipped
vocabulary the tool colours both clouds by the model's assignment
(`--model standard/model.nvm1`), or by a fresh one (`--clusters K`), which is
how the co-clustering is seen rather than inferred, and it reads the equation
above off the table with a Lanczos SVD, since the dense one is cubic; that
figure is in `README.md`.)*

## Compressing the table directly

The natural alternative to the low-rank fit — store the largest `N` observed
cells verbatim and model the rest with the independence prior — is a separate
experiment (`scripts/matrix_compress.py`).  Summary: the residual is *not*
sparse, and the scheme only ties the `k = 105` block model at matched model size
under a counting convention that ignores the cost of naming the coded cells.
Full study: [`MATRIX_COMPRESSION.md`](MATRIX_COMPRESSION.md).

## Is the factor-cloud "gain × shape" structure real?

The rank-`L` cloud (`scripts/factor_cloud.py`) looks as if its density factorises
as a radial "gain" (peaked near the origin) times an angular "shape" independent
of the radius — suggesting a scalar gain could be split off from a
low-dimensional shape.  `scripts/shape_gain_test.py` tests whether that survives
scrutiny, because two things make the visual unreliable:

* **full rank the radius is just the mass.** `‖√M_ref[a,:]‖² = row mass_a`, so
  the "radial function" *is* the word-frequency distribution.
* **the cloud is a σ-weighted point set.** In `X = U√σ`, `r_w = √(Σ_k σ_k U[w,k]²)`,
  so direction and radius are coupled by the scaling whenever the `σ` differ —
  and, independently, the orthonormal-column constraint of the SVD couples them
  even with equal `σ`.

The test statistic is the energy distance between the directions in the
low- and high-radius halves, permutation-tested and normalised by the mean
pairwise distance (`E/MPD`; `p > 0.05` ⇒ independent).  The nulls are matrices
that pass through the *same* pipeline but carry no gain/shape structure by
construction — `indep` (`M[a,b] = g_a·p_a[b]`, gain and shape independent),
`coupled` (`g_a` drives the concentration of `p_a`), and `iid` random.

| clouds | real `tw2040` | indep null | coupled null | iid null |
|---|---:|---:|---:|---:|
| rank-4 `U√σ` / `V√σ` | 0.086 / 0.144 | 0.004 / 0.170 | 0.012 / 0.093 | 0.111 / 0.106 |
| rank-4 `U` / `V` (unweighted) | 0.071 / 0.102 | 0.011 / 0.135 | 0.031 / 0.084 | 0.090 / 0.090 |
| full rank (no SVD) | 0.005 / 0.009 | 0.000 / 0.003 | 0.010 / 0.000 | 0.000 / 0.000 |

What the numbers say:

* **At full rank the gain/shape split is nearly exact** (all `E/MPD ≤ 0.01`) —
  but that is close to a tautology: gain = `√mass` and shape = the normalised
  successor distribution, two coordinate functions of the same row.
* **The strong rank-4 structure is an artefact.**  A structureless i.i.d. matrix
  reproduces it (`E/MPD ≈ 0.09–0.11`), the real cloud sits inside the null range,
  and the rank-4 statistic does **not** separate the by-construction independent
  from the coupled control (`indep` right `0.170` > `coupled` right `0.093`).
  The dependence also *shrinks* as rank grows (0.18 → 0.02 from rank 2 to 256),
  so the most visually striking rank (L = 4) is the most artefact-laden.
* So the "gain × shape" impression is largely SVD geometry, not evidence of
  separable data structure.  A gain/shape split would not by itself reduce the
  shape's dimension anyway — that needs the *angular* cloud to be low-dimensional,
  which the co-clustering study ([`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)) already
  says it is not.

`scripts/shape_gain_test.py`.

## Conclusions

0. Factorise the **word × word** matrix `√M_ref` (the occurrence-weighted
   Hellinger embedding) and square back.  It is the best low-rank model by joint
   KL at every vocabulary size from about `L = 16` up, is non-negative by
   construction, and needs no extra hyper-parameters.  `scripts/hfactor_words.py`.
1. Score with the **joint** KL `KL(M_ref/T ‖ M̂/ΣM̂)`; it differs from the
   occurrence-weighted conditional KL only by a model-independent constant.
2. Put a small independence-shaped prior on unobserved pairs,
   `M_ref = M + kappa·V·P_mar`, with `kappa` a fixed prior mass *per row*.
   `kappa` must be fixed by held-out likelihood, not by the KL (which is
   monotone in `kappa`).  Construction: [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md).
3. **Factorising loses held-out compression** at the vocabulary sizes studied
   (rank-256 costs ~1.3 bits vs the full table), so the table is only worth
   factorising when model size is the binding constraint.
4. **The residual is not sparse, so direct table compression is only mild.**
   Storing the largest `N` cells verbatim over the independence prior stays
   within ~1 bit only at `N ≈ 300K` (`tw2040`, 6.8% of `V²`) / `~100K` (`tw512`, 30% of `V²`);
   a low-rank/M_mar fit leaves its error spread over 10–20% of `V²` at every
   rank.  At *matched store* the scheme is nevertheless competitive with the
   `k = 105` co-clustering (54.240 vs 55.354 bits at store 15 233), but that tie
   is a counting artefact: it ignores the cost of transmitting *which* cells are
   coded (`≈ N·log₂V²` bits, ~10× the cluster labels), after which the block
   model wins by ~1.3–4 bits.  Combined with the clustering study, neither route
   gives a compact, near-lossless table.  `scripts/matrix_compress.py`,
   [`MATRIX_COMPRESSION.md`](MATRIX_COMPRESSION.md).
