# Building the word adjacency matrix

This is the canonical reference for the **word × word adjacency matrix** `M`
and for the prior (`κ`) that fills its unobserved cells.  The documents that
*study* this matrix — the Hellinger factorisation
([`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md)), the block
clustering ([`CLUSTER_WORDS.md`](CLUSTER_WORDS.md),
[`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md)) and the rejected break-open prior
([`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md)) — refer back here rather than
restating the construction.

The idea in one sentence: tokenise each identifier into words, and for every
split at a word boundary count the word on the left paired with the word on the
right.

## 1. What a cell counts

Prepare the corpus as usual: case-normalise to CamelCase
([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)), build the pair-merge
dictionary ([`DICTIONARY_RULES.md`](DICTIONARY_RULES.md),
[`TREE_WORDS.md`](TREE_WORDS.md) §2) and tokenise each identifier by replaying
its rules ([`TREE_WORDS.md`](TREE_WORDS.md) §3).

Append the stop character `\n` to each identifier and bend it into a cycle, so
that the tokenised identifier `w₁ w₂ … wₙ` is the cycle

```
w₁ → w₂ → … → wₙ → \n → w₁
```

and contributes `n + 1` adjacent pairs.  For a split between two consecutive
tokens define

* `a`, the **left context** — the token immediately to the left of the split;
* `b`, the **right context** — the token immediately to the right.

Then `M[a, b]` is incremented once for that split.  Because the tokenisation is
a partition of the identifier, the word-boundary splits are *exactly* the
adjacent pairs, so

```
M[a, b]  =  the number of occurrences of the word b immediately after the word a.
```

That is the whole construction.  It is the **dictionary split**: a context is a
whole word, and the characters inside a word are not looked at.  Both sides
range over the same `V` symbols — the `63` characters, `\n`, and the
`NUM_PAIRS` words — which is why the matrix is square; it is not a claim that
the two sides are independent.

The stop closes the cycle.  `M[\n, b]` counts the identifiers that *begin* with
`b`, and `M[a, \n]` counts those that *end* with `a`.  `M[\n, \n] = 0`: there
are no empty identifiers.  A word never spans two identifiers, because `\n` is
a separator and is not merged across.

> The earlier **prefix/suffix** matrix — left and right contexts are the
> longest common substrings at every *character* split — belonged to the
> character-level successor model.  That model is retired; its construction is
> recorded in [`SUCCESSOR_MODEL.md`](SUCCESSOR_MODEL.md) and
> [`CODE_LENGTHS.md`](CODE_LENGTHS.md).  This note describes the word matrix
> only.

## 2. The vocabulary: the word list

The vocabulary is the tree word list: the characters plus `\n` plus
`NUM_PAIRS` pair words, `V = 63 + 1 + NUM_PAIRS`.  There is no threshold to
choose: the vocabulary is fixed by the dictionary, and the size knob is
`NUM_PAIRS`.  The adopted grid is
`V ∈ {4096, 6144, 8192}` (see the build-directory key in `PLAN.md`).  The word
list is built from a 5 % sample of the corpus (`--sample 20`); the matrix is
then counted over the full training split (`--stride 0`).

On the 10-ecosystem training split (3,804,036 identifiers; 422,671 are held
out):

| `V` | `NUM_PAIRS` | tokens `T` | distinct bigrams | density |
|---:|---:|---:|---:|---:|
| 4,096 | 4,032 | 21,697,898 | 1,813,165 | 10.8 % |
| 6,144 | 6,080 | 20,145,653 | 2,237,618 | 5.9 % |
| 8,192 | 8,128 | 19,241,177 | 2,507,680 | 3.7 % |

`T` *falls* as `V` grows: the extra words merge tokens, so an identifier that
took eight words at `V = 4 096` may take seven at `8 192`.  The matrix gets
larger while the number of events it counts gets smaller.

## 3. The cycle and the stop

Every identifier contains exactly one `\n`, at the end of its token sequence.
Bending the sequence into a cycle gives the string's first word the stop as its
predecessor and the stop the first word as its successor, so each identifier
contributes

```
(\n, w₁), (w₁, w₂), …, (wₙ, \n)        — n + 1 pairs.
```

The cycle is load-bearing.  It is what makes `Σ_v N(u,v) = N(u)` hold for every
`u`, including `\n` (§4), and it is why `N(\n)` is exactly the number of
identifiers.

There is no empty context: every context is a word.  The smoothing that a
character model gets from shorter suffixes has no word-level analogue; the
prior of §6 is the whole backoff.

## 4. Row and column marginals are equal

For every symbol `a`,

```
Σ_b M[a, b]  =  Σ_b M[b, a]  =  N(a),
```

the unigram count of `a`; in matrix form `M 1 = Mᵀ 1 = u`.  Each occurrence of
a word has exactly one successor and exactly one predecessor in the cycle, and
`\n` occurs once per identifier, so both marginals count the same events.

This is exact, and it is the invariant to check after any change to the
builder.  It does **not** say `M` is symmetric — it is not, and reversal is not
a symmetry of the word tokenisation.  It also supplies the denominator of the
prior in §6, which is why it is stated here rather than left implicit.

## 5. Density and unobserved cells

The matrix is sparse at every grid size, but its mass is not: half the tokens
sit in under 1 % of the cells, and nine tenths in a quarter to a third of them.

| `V` | positive cells | density | largest count | cells with 50 % of mass | cells with 90 % of mass |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 1,813,165 | 10.8 % | 117,588 | 0.6 % | 25.8 % |
| 6,144 | 2,237,618 | 5.9 % | 102,990 | 0.7 % | 30.8 % |
| 8,192 | 2,507,680 | 3.7 % | 91,412 | 0.8 % | 35.0 % |

A zero is **not** an impossibility.  Most of the zeros are unobserved tail
pairs — a rare word simply never met another rare word — and the next section
fills them.  A small minority are *structural*: a cell `(a, b)` is impossible
when the word list contains the merged word `(ab)`, because then an adjacent
`a, b` is always merged.  The structural cells are 77,110 / 144,948 / 227,364
at `V = 4 096 / 6 144 / 8 192` (2.5–3 % of the independence prior's mass), and
correcting the prior for them changes held-out length by at most 0.06
bits/identifier, so §6 does not.  The full statement, including the absorbed
left-context case, is [`STRUCTURAL_ZEROS.md`](STRUCTURAL_ZEROS.md).

## 6. Filling unobserved cells: the counting prior

Add a small amount of pseudo-count mass, shaped like the independence model, to
form a **corrected reference**

```
M_ref = M + alpha · P_mar ,    P_mar = (r / T) (c / T)ᵀ   (sum = 1),
                               r = c = u,   T = 1ᵀ M 1 = Σ_a N(a),   alpha = kappa · V .
```

`P_mar` is the rank-1 independence (outer-product) shape rescaled to unit mass,
and `alpha` is the prior mass.  Because the matrix is cyclic, `r` and `c` are
both the unigram vector `u` (§4), but the formula is written symmetrically so
that it also covers a non-cyclic build.

Three design points:

* **Fixed total mass, not a fraction of the corpus.**  `alpha = kappa·V` does
  *not* scale with `T`, so the correction washes out as the corpus grows — it
  is a prior on *unseen pairs*.  Adding the *unnormalised* `alpha·M_mar`
  (`M_mar = r cᵀ / T`) would instead inject `alpha·T` pseudo-counts — at
  `alpha = 1` that is half the matrix — and would never vanish.  (`M_mar` is
  retained **only** as the convex-mixing partner of the `backoff`
  *reconstruction* remedy, where its sum-`T` normalisation is what makes the
  weight `λ` meaningful.)
* **Mass per context.**  With `alpha = kappa·V` the prior adds `alpha·r_a/T`
  pseudo-counts to row `a`; since the mean of `r_a` is `T/V`, that is `kappa`
  per row on average.  `kappa` is therefore the quantity the optimum holds
  fixed, which is why one value serves every vocabulary size.  A fixed
  per-cell pseudo-count `c` would force `alpha = c·V²` and the optimum would
  drift like `1/V`.
* **`M_ref` is the reference for the whole analysis.**  Every model is fitted
  to `M_ref` and scored against it, so results are **not comparable across
  `kappa`** by design: `kappa` is a counting fix, not a reconstruction knob.

At the recommended `kappa = 300` (§7) the prior is 5.7 % of the token mass at
`V = 4 096` (`alpha = 1.23 × 10⁶`) and 12.8 % at `V = 8 192`
(`alpha = 2.46 × 10⁶`).

## 7. Choosing `kappa`: held-out predictive likelihood

`kappa` must **not** be chosen by the factorisation's in-sample KL.  That KL
decreases monotonically in `kappa` for every method, because as
`kappa → ∞` the reference `M_ref` tends to the rank-1 `P_mar`, which any
rank-`L` model fits almost exactly.  Nor can it be chosen on the training
identifiers: the prior exists for cells that the training data did not see.

Choose it on **held-out identifiers**, the quantity the product ships: tokenise
the validation split, code each identifier under `P_ref(v | u) ∝ M_ref(u,v)`,
and take the mean bits/identifier (lower is better).  Swept on the full-table
model at stride 10 (`n = 42,268`):

| `kappa` | 3 | 10 | 30 | 100 | **300** | 1,000 | 3,000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `V = 4,096`, mean bits | 43.30 | 42.95 | 42.64 | 42.33 | **42.15** | 42.27 | 43.11 |
| `V = 4,096`, fit ≤ 64 | 89.2 % | 89.6 % | 89.9 % | 90.2 % | **90.3 %** | 90.2 % | 89.3 % |
| `V = 8,192`, mean bits | 41.75 | 41.17 | 40.66 | 40.18 | **39.95** | 40.31 | 41.63 |
| `V = 8,192`, fit ≤ 64 | 91.5 % | 92.1 % | 92.6 % | 92.9 % | **93.1 %** | 92.7 % | 91.5 % |

The optimum is `kappa = 300` at both ends of the grid, and the curve is flat
within 0.2 bit between 100 and 300.  `kappa = 0` diverges: a bigram unobserved
in training has no mass at all.  Larger `kappa` costs more at the top of the
grid, because the prior's mass `kappa·V` grows with `V` against a shrinking
token total (§2).

Scored on held-out *pairs* instead of identifiers, the optimum is flatter and
slightly lower — `kappa = 300` at `V = 4 096` and `100` at `V = 8 192`
([`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md) §8.7) — which is the same range.
Both the factorisation and the shipped word model use the one value:

| criterion | what is held out | optimum |
|---|---|---|
| held-out bits/identifier (shipped) | identifiers | 300 at both grid ends |
| held-out pair cross-entropy (factorisation) | `(a, b)` pairs | 100–300 |

**Recommendation: a fixed `alpha = 300·V` (`kappa = 300`).**  It is the minimum
of the identifier curve at both ends of the grid, within 0.2 bit of the optimum
everywhere in 100–300, and needs no per-corpus tuning.  Caveat: with a single
corpus we cannot separate the `V`- from the corpus-size dependence, so ≈300 is
an empirical constant for this corpus.  Re-check it with the sweep in §8.

## 8. Reproducing

```sh
# the whole grid: dictionaries on the 5% sample, adjacency over all lines
bash scripts/h5_build.sh ns

# or one vocabulary, then its matrix summary
python3 scripts/tree_words.py train --corpus work/camel/merged_training.txt \
        --num-pairs 4032 --sample 20 --stride 0 --outdir work/tw4096ns
python3 scripts/tree_words.py stats --dir work/tw4096ns

# the kappa sweep (held-out bits/identifier; the full-table figure)
for k in 3 10 30 100 300 1000 3000; do
    python3 scripts/model_fit_rates.py --dir work/tw4096ns --ks 16 \
            --kappa "$k" --stride 10
done

# the factorisation study (joint KL, and its kappa dependence)
python3 scripts/hfactor_words.py factor --dirs work/tw4096ns,work/tw8192ns \
        --ls 16 --kappas 0,100,300,1000,3000
```

`scripts/hfactor_words.py score` runs the same held-out criterion at a single
`kappa`, and `scripts/cluster_words.py` consumes `adj.npz` directly once the
matrix exists.
