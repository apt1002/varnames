# Structural zeros in the word adjacency prior

Status: **negative (negligible).**  The structural zeros are real and can be
listed exactly, but correcting the independence prior `P_mar` for them moves the
held-out code length by at most **0.06 bits/identifier** — the prior is itself a
small correction and the impossible cells are a small fraction of it.

## What a structural zero is

The word × word adjacency matrix of the pair-merge dictionary
([`TREE_WORDS.md`](TREE_WORDS.md)) has cells that are **impossible for any
corpus**, not merely unobserved.  Writing `w = (ab)` for the word created by
merging tokens `a` and `b`, and `rank(w)` for the creation order:

1. **Merged pair.**  `M(a, b) = 0` when the word list contains the word `(ab)`.
   Once `(ab)` exists, an adjacent `a, b` is always merged, so the two never
   survive as separate tokens.  This covers pair rules and the run word `(u²)`
   (which removes the `u, u` bigram).
2. **Absorbed left context.**  `M(a, w) = 0` when the left spine of `w`
   (`n₀ = w, n₁ = lc(w), n₂ = lc(n₁), …` down to the leftmost leaf) contains a
   node `nᵢ` such that `(a, nᵢ)` is a word created **before `n_{i-1}` was** —
   then `a` absorbs `nᵢ` before `w` can form.  Symmetrically `M(w, b) = 0` over
   the right spine with `(nᵢ, b)`.

The second condition needs care.  The naive reading "any left ancestor `b` with
`(ab)` a word" is **wrong**: it over-zeros.  For example `tw96` has `ent = (en,
t)`, `en` created before `re`; the leaf of `ent` is `e`, and `(r,e) = re` is a
word, yet `r → ent` **does** occur (7,547 times) — because `en` formed first and
absorbed the `e` before `re` could.  The spine condition compares the rank of
`(a, nᵢ)` with the rank of `n_{i-1}`, which is the correct order.  With it the
mask has **zero false positives**: every masked cell is zero in the observed
matrix (checked for all three dictionaries).

`scripts/hfactor_words.py` implements `structural_mask`.

## Size of the effect

| dictionary | `V` | positive cells | structural cells | `P_mar` mass on them |
|---|---:|---:|---:|---:|
| `tw4096ns` | 4,096 | 1,813,165 | 77,110 | 3.09% |
| `tw6144ns` | 6,144 | 2,237,618 | 144,948 | 2.72% |
| `tw8192ns` | 8,192 | 2,507,680 | 227,364 | 2.48% |
| `tw96` (legacy) | 160 | 20,499 | 371 | 3.87% |
| `tw512` (legacy) | 576 | 149,932 | 3,461 | 4.18% |
| `tw2040` (legacy) | 2,104 | 802,606 | 26,068 | 3.51% |

Most observed zeros are simply unobserved tail pairs, not structural ones; the
structural cells are 2.5–3% of the independence prior's mass at the grid (3.5–4%
at the legacy vocabularies).  The absolute number grows with `V` (77,110 cells at
4,096, 227,364 at 8,192, i.e. 0.46% and 0.34% of `V²`) while their prior mass
share shrinks, because the extra words are the rare ones whose rows and columns
carry little independent mass.  Following the
recipe of [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md), `P_mar = (r/T)(c/T)ᵀ` is
computed, the structural cells are set to zero, and the rest is renormalised to
sum 1 before forming `M_ref = M + alpha·P_mar`.

## Effect on held-out compression

`tw4096ns`, stride-20 sample of `work/camel/merged_validation.txt` (21,134
identifiers), mean bits under `P_ref`:

| `kappa` | plain `P_mar` | structural zeros | Δ |
|---:|---:|---:|---:|
| 100 | 42.27 | 42.26 | −0.01 |
| 300 | 42.08 | 42.07 | −0.01 |
| 1000 | 42.20 | 42.17 | −0.03 |
| 3000 | 43.03 | 42.97 | −0.06 |

Under the **factorised** model (rank-`L` Hellinger, `kappa = 300`):

| model | plain | structural zeros |
|---|---:|---:|
| `sqrtcnt` `L = 256` | 43.76 | 43.76 |
| `sqrtcnt` `L = 128` | 45.09 | 45.09 |
| `sqrtcnt` `L = 64` | 46.61 | 46.63 |

The correction is always in the right direction and grows slowly with `kappa`
(larger prior ⇒ the impossible cells carry more mass), but it is an order of
magnitude below the 0.1-bit resolution that matters here, and it does not move
the rank-`L` model at all (the reconstruction smooths the small local change
away).

## Why so small

The prior has a fixed mass `alpha = kappa·V` against a token total `T`
(`T = 21,697,898` at `V = 4,096`, so `alpha/T = 5.7%` at `kappa = 300` and 5.4%
of `M_ref`).  Of that prior mass only 3.1% sits on structurally impossible
cells, so the correction touches **0.17%** of the probability mass.  Zeroing a
few percent of a few percent cannot move the code length appreciably.

The same arithmetic explains the `kappa` trend in the table above: the prior's
share of `M_ref` is 1.9%, 5.4%, 15.9% and 36.2% at `kappa` 100, 300, 1,000 and
3,000, so the structural correction covers 0.06%, 0.17%, 0.49% and 1.1% of the
mass — and even at 1.1% it buys only 0.06 bits.

## Conclusion

Structural zeros are a correct refinement of the independence prior and are
implemented (`hfactor_words.py --struct-zeros`), but they do **not** improve
compression meaningfully.  They are not a lever on the model; they are recorded
here so the negative is on the books.  (This is the same verdict, for the same
reason, that [`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md) §9.1 reached on the
*absorbed* cells of the break-open prior: those extra zeros are not structural —
but even the genuinely structural ones barely matter.)
