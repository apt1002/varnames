# Structural zeros in the word adjacency prior

Status: **negative (negligible).**  The structural zeros are real and can be
listed exactly, but correcting the independence prior `P_mar` for them moves the
held-out code length by at most **0.06 bits/identifier** — the prior is itself a
small correction and the impossible cells are a small fraction of it.

## What a structural zero is

The word × word adjacency matrix of the run-aware dictionary
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
| `tw96` | 160 | 20,499 | 371 | 3.87% |
| `tw512` | 576 | 149,932 | 3,461 | 4.18% |
| `tw2040` | 2,104 | 802,606 | 26,068 | 3.51% |

Most observed zeros are simply unobserved tail pairs, not structural ones; the
structural cells are ~3–4% of the independence prior's mass.  Following the
recipe of [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md), `P_mar = (r/T)(c/T)ᵀ` is
computed, the structural cells are set to zero, and the rest is renormalised to
sum 1 before forming `M_ref = M + alpha·P_mar`.

## Effect on held-out compression

`tw2040`, stride-20 sample of `work/camel/merged_validation.txt` (11,477
identifiers), mean bits under `P_ref`:

| `kappa` | plain `P_mar` | structural zeros | Δ |
|---:|---:|---:|---:|
| 100 | 45.87 | 45.86 | −0.01 |
| 300 | 45.76 | 45.75 | −0.01 |
| 1000 | 45.95 | 45.92 | −0.03 |
| 3000 | 46.86 | 46.80 | −0.06 |

Under the **factorised** model (rank-`L` Hellinger, `kappa = 300`):

| model | plain | structural zeros |
|---|---:|---:|
| `sqrtcnt` `L = 256` | 47.10 | 47.09 |
| `sqrtcnt` `L = 128` | 48.61 | 48.60 |
| `sqrtcnt` `L = 64` | 50.59 | 50.59 |

The correction is always in the right direction and grows slowly with `kappa`
(larger prior ⇒ the impossible cells carry more mass), but it is an order of
magnitude below the 0.1-bit resolution that matters here, and it does not move
the rank-`L` model at all (the reconstruction smooths the small local change
away).

## Why so small

The prior has a fixed mass `alpha = kappa·V` against a token total `T`.  At the
held-out optimum `kappa = 300`, `alpha/T ≈ 4.5%`, and of the prior mass only
~3.5% sits on structurally impossible cells — so the correction touches
~0.16% of the probability mass.  Zeroing a few percent of a few percent cannot
move the code length appreciably.

## Conclusion

Structural zeros are a correct refinement of the independence prior and are
implemented (`hfactor_words.py --struct-zeros`), but they do **not** improve
compression meaningfully.  They are not a lever on the model; they are recorded
here so the negative is on the books.  (This is the same verdict, for the same
reason, that [`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md) §9.1 reached on the
*absorbed* cells of the break-open prior: those extra zeros are not structural —
but even the genuinely structural ones barely matter.)
