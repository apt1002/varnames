# Building the adjacency matrix

This is the canonical reference for how the **prefix/suffix adjacency matrix**
`M` is built, and for the prior (`κ`) that fills its unobserved cells.  The
documents that *study* this matrix — the Hellinger factorisation
([`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md)) and the character
successor model ([`CODE_LENGTHS.md`](CODE_LENGTHS.md)) — refer back here rather
than restating the construction.

The idea in one sentence: for each split of an identifier, record the longest
known **left context** (something that can end the left half) paired with the
longest known **right context** (something that can start the right half), and
count the pairs.  The result is a roughly `N × N` matrix of how often those
contexts meet.

## 1. What a cell counts

Prepare the corpus as usual: case-normalise to CamelCase
([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)) and wrap each identifier as

```
^identifier$
```

(`^`, `$` mark the ends; `$` is the stop character used everywhere in this
project).  For a string of length `len`, consider every split into a non-empty
left half and a non-empty right half (so there are `len − 1` splits).

For a given split define

* `a`, the **left context** — the longest substring that is a *suffix of the
  left half* and appears in the common-substring vocabulary.  It never ends in
  `$`.
* `b`, the **right context** — the longest substring that is a *prefix of the
  right half* and appears in the vocabulary.  It may end in `$`.

Then `M[a, b]` is incremented once.  So `M` is the joint count of "what the left
piece ends with" against "what the right piece starts with", over all
identifiers and all their splits.  It is **symmetric data** crossed with the
vocabulary: `a` and `b` range over the same set of substrings, but the matrix is
square only because both halves draw on the one vocabulary.

## 2. The vocabulary: common substrings

The vocabulary is the set of **common substrings** — substrings of the wrapped
identifiers (within `^…$`) occurring at least `T` times — enumerated by
`scripts/common_substrings.py`.  `T` is the size knob: it fixes `N`, the number
of contexts.  Sizes on the current corpus (`work/camel/merged.txt`):

| `T` | `N` (contexts) | max length |
|---:|---:|---:|
| 100000 | 278 | 5 |
| 50000 | 613 | 6 |
| 20000 | 1,788 | 9 |
| 10000 | 3,935 | 13 |
| 5000 | 8,038 | 14 |
| 2000 | 20,198 | 15 |
| 1000 | 40,168 | 30 |
| 500 | 80,869 | 44 |

(Rows count the empty string.  Below `T = 2000` the longest entry is a padding
run of `o`, not a word — see [`CASE_NORMALISATION.md`](CASE_NORMALISATION.md).)

## 3. The empty context (backoff)

The empty string `""` is included in the vocabulary and serves as the
**backoff context** on either side: when the longest known suffix/prefix is
empty, `a` or `b` is `""`.  Keeping it explicit matters — a split with no known
left context is still a split, and folding it away would silently reshape the
marginals.  (The right context may be `$` itself, the "nothing follows" case.)

## 4. Symmetry under reversal is exact

The construction is mirror-symmetric: reverse an identifier and swap `^ ↔ $`
and every left context becomes a right context.  Consequently, building `M` on
the corpus and `Mᴿ` on the all-reversed corpus gives, exactly,

```
Mᴿ[ φ(b), φ(a) ] = M[a, b]        (φ = reverse + swap ^↔$)
```

with relative Frobenius residual `0.0` (`scripts/symmetry_check.py`, on
`T = 10000`: max discrepancy `0` against a max count of 104,614).  This is a
useful debugging invariant, and it is why a *reversed* corpus is a genuinely
different dataset: the identifier corpus is **not** reversal-symmetric, so the
row (left-context) and column (right-context) behaviour legitimately differ.

## 5. Density and structural zeros

`M` counts only pairs that actually occur, so it is dense for small `N` (the few
frequent contexts meet constantly) and sparse for large `N` (rare pairs are
nearly unique):

| `T` | `N` | `nnz` | density | largest count |
|---:|---:|---:|---:|---:|
| 100000 | 278 | 55,297 | 71.6% | 198,881 |
| 20000 | 1,788 | 753,302 | 23.6% | 144,214 |
| 5000 | 8,038 | 3,331,843 | 5.2% | 42,195 |
| 1000 | 40,168 | 9,818,809 | 0.61% | 18,293 |

(Measured on `work/camel/merged.txt`, the 10-ecosystem corpus: 4,226,707
identifiers, 81,455,598 positions in total.  Because `N` grows much faster than
the number of occurring pairs, the density falls by two orders of magnitude
across the table — the matrix is not an object one can store densely at any
useful vocabulary.)

A structural zero is **not** an impossibility: it only says the pair was not
seen.  The next section fills those cells.

## 6. Filling unobserved cells: the counting prior

Add a small amount of pseudo-count mass, shaped like the independence model, to
form a **corrected reference**

```
M_ref = M + alpha · P_mar ,   P_mar = (r / T) (c / T)ᵀ   (sum = 1),
                              r = M 1,  c = Mᵀ 1,  T = 1ᵀM1,   alpha = kappa · N .
```

Here `P_mar` is the rank-1 independence (outer-product) shape rescaled to unit
mass, and `alpha` is the prior mass.  Three design points:

* **Fixed total mass, not a fraction of the corpus.**  `alpha = kappa·N` does
  *not* scale with `T`, so the correction washes out as the corpus grows — it is
  a prior on *unseen pairs*.  Adding the *unnormalised* `alpha·M_mar`
  (`M_mar = r cᵀ / T`) would instead inject `alpha·T` pseudo-counts — at
  `alpha = 1` that is half the matrix — and would never vanish.  (That was an
  earlier error; `M_mar` is retained **only** as the convex-mixing partner of
  the `backoff` *reconstruction* remedy, where its sum-`T` normalisation is what
  makes the weight `λ` meaningful.)
* **Mass per context.**  The optimal mass turns out to be a constant multiple of
  `N` (below), so one `kappa` serves every vocabulary size.  A fixed per-cell
  pseudo-count `c` would force `alpha = c·N²` and the optimum would drift like
  `1/N`.
* **`M_ref` is the reference for the whole analysis.**  Every model is fitted to
  `M_ref` and scored against it, so results are **not comparable across
  `kappa`** by design: `kappa` is a counting fix, not a reconstruction knob.

## 7. Choosing `kappa`: held-out predictive likelihood

`kappa` must **not** be chosen by the KL.  The KL `KL(M_ref ‖ M̂/ΣM̂)` decreases
monotonically in `kappa` for *every* method, because as `kappa → ∞` the reference
`M_ref` tends to the rank-1 `P_mar`, which any rank-`L` model fits almost
exactly.  Instead, fix it by **predictive** performance.

`scripts/choose_kappa.py` binomial-thins the counts into train/test
(`p_train = 0.5`), fits the `sqrtcnt` model (see
[`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md)) to
`M_train + kappa·N·P_mar(train)`, and scores the test counts as cross-entropy in
bits per held-out event (lower is better; mean over 3 splits).  The test set
contains pairs *unseen in train*, so this is the criterion that can reward the
prior.  The sweep is over `kappa` directly, so the fitted mass is `alpha =
kappa·N` at every `N`.

Re-checked on the 10-ecosystem corpus at both ends of the grid
(`work/camel/merged.txt`, 73.0M transitions):

| `T` (`N`) | best `kappa` | best `alpha` | CE\* at best | CE `kappa=300` | CE `kappa=1000` | CE `kappa=0` | CE indep. |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100000 (278) | 1500 | 4.2×10⁵ | 13.73332 | 13.73435 | 13.73354 | 13.73582 | 15.03257 |
| 5000 (8 038) | 700 | 5.6×10⁶ | 21.87699 | 21.94077 | 21.88038 | 22.66604 | 23.33078 |

(\*cross-entropy of the test table under the model, bits/event; "CE indep." is
the no-latent-structure baseline `P_mar(train)`; the `std` over the 3 splits is
0.0001–0.0012, so the differences between `kappa = 700` and `1000` are about 1σ
at the small end and ~3σ at the large end.)

* The prior helps, and the benefit **grows with sparsity** — 0.0025
  bits/event at `N = 278` (within noise) to 0.79 bits/event at `N = 8 038`.
  Every `kappa > 0` beats `kappa = 0`, and the independence model is far worse
  than either (1.3 and 1.45 bits/event).
* The optimum is prior mass **per context**, not per cell: the best `kappa` is
  700–1500 across a 29× range of `N`, effectively a constant ≈10³.  A *single*
  fixed `kappa` transfers across sizes.

**Recommendation for the factorisation: a fixed `alpha = 1000·N`
(`kappa = 1000`).**  It is within 0.0002 bits/event of the optimum at `N = 278`
and 0.003 at `N = 8 038`, and needs no per-corpus tuning.  `choose_kappa.py`
remains available to re-check it.  Caveat: with a single corpus we cannot
separate the `N`- from the corpus-size dependence, so ≈10³ is an empirical
constant for this corpus.

### The two `kappa`s are different knobs

The **shipped word model** also carries a `kappa` (`alpha = kappa·V`, applied to
the word × word matrix before clustering), and its measured optimum is **300**,
not 1000 — [`WORD_COMPRESSIBILITY.md`](WORD_COMPRESSIBILITY.md) sweeps it at both
ends of the grid: 42.15 bits/identifier at 300 against 42.27 at 1000 (`V = 4 096`)
and 39.95 against 40.31 (`V = 8 192`).

That is not a contradiction; the two numbers optimise different things:

| | this section (factorisation) | shipped word model |
|---|---|---|
| object | rank-`L` `sqrtcnt` fit of `M` | `k`-means block model + coding |
| criterion | held-out pair cross-entropy | held-out bits per identifier |
| prior share of the counts | 11 % at 1000 (`N = 8 038`) | 5.7 % at 300, 19 % at 1000 (`V = 4 096`, `T = 21.7 M`) |
| optimum | 700–1 500 | 300 |

Scoring identifiers rather than pairs punishes the prior harder, because the
prior's mass is spread over the whole matrix and each identifier touches only
5–6 transitions: at `kappa = 1000` the reference is 19 % independence-shaped and
the block model's within-cell detail is diluted.  The cost of one value serving
both is small either way — 0.1–0.4 bits/identifier if the product used 1000, and
0.0002–0.003 bits/event on this section's own criterion if it used 300 — so the
choice is settled by the product: **`kappa = 300` for the word model,
`kappa = 1000` for the factorisation analyses in this note**, and every table
states which one it used.  As everywhere else in the project, `kappa` is a
counting fix rather than a third design knob.

**Pre-expansion record** (2.07M-identifier corpus, five thresholds; the
unobserved-cell column counts cells, not contexts, which the current script no
longer reports):

| `T` (`N`) | cells unobs. | best `kappa` | best `alpha` | CE\* best | CE `kappa=0` | CE indep. |
|---:|---:|---:|---:|---:|---:|---:|
| 100000 (159) | 21% | 1000 | 1.6×10⁵ | 12.4049 | 12.4061 | 13.5351 |
| 50000 (316) | 36% | 1500 | 4.7×10⁵ | 14.0671 | 14.0754 | 15.4134 |
| 20000 (911) | 65% | 1500 | 1.4×10⁶ | 16.6422 | 16.7232 | 18.1551 |
| 10000 (2102) | 83% | 1000 | 2.1×10⁶ | 18.6564 | 18.9291 | 20.1605 |
| 5000 (4478) | 92% | 700 | 3.1×10⁶ | 20.5217 | 21.0966 | 21.9917 |

## 8. Reproducing

```sh
# build the matrix (writes M.npz, and the low-rank factors) for a threshold
python3 scripts/pair_matrix.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000 \
        --lsvd 2,4,8,16,32,64

# re-check kappa by held-out likelihood (grid outdirs: /tmp/cs100000, /tmp/cs5000)
python3 scripts/choose_kappa.py work/camel/merged.txt \
        --outdirs /tmp/cs5000 --L 16 --reps 3 \
        --kappas 0,300,700,1000,1500,3000

# the κ-parameterised KL tables
python3 scripts/sqrt_and_smooth.py work/camel/merged.txt \
        --outdirs work/common10000 --ls 16 --kappas 0,100,300,1000,3000

# reversal-symmetry invariant
python3 scripts/symmetry_check.py work/camel/merged.txt \
        work/common10000/common_substrings.txt \
        work/rev/merged_rev.txt work/rev/common10000/common_substrings.txt
```

`scripts/run_sweep.sh` runs the construction and the analyses over a list of
thresholds.
