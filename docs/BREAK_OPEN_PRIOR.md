# Breaking open the pair: a structured prior for the word adjacency

`docs/WORD_COMPRESSIBILITY.md` models the tokenised corpus with a first-order
Markov chain over **words**, filling unobserved bigrams with the *unstructured*
independence prior of `docs/ADJACENCY_MATRIX.md` §6,

    P_ref(v | u) = [ N(u,v) + alpha·(r_u/T)(c_v/T) ] / [ r_u·(1 + alpha/T) ] ,

whose shape `P_mar` treats every vocabulary item alike.  But the words are
**built**, not given: a word `(uv)` is two earlier words glued together, on down
to single characters.  That structure is information the independence prior
throws away.  This note designs a prior that uses it — *breaking open the pair*.

**This is a design note, and the design is rejected.**  It is not wired into
the model.  The independence prior `P_mar` stays.  §8 measures the alternative
and §8.7 re-measures it at the canonical grid, where it is 10–11 bits worse at
the best `kappa` and 13–14 points worse on the 64-bit fit.  It fixes the two
errors of the first draft: the recursion is an *estimation rule* for a missing
count (not a free-floating "seed"), and it is defined by building the matrix
**bottom-up** so that its normalisation is available when it is needed.

## 1. The dictionary as a merge tree

Recall the dictionary of `docs/TREE_WORDS.md`.  A word `a` is either a single
character or a merge of two earlier words, its children.  Write `lc(a)` and
`rc(a)` for the **left** and **right** child of a pair `a = (lc(a), rc(a))`; the
right child sits against whatever **follows** `a`, the left child against
whatever **precedes** it.  A single character has no children.

Think of the words as born in the wordlist order; each new word costs one
`NUM_PAIRS` increment.  Words born earlier are (roughly) the more frequent; a
**larger creation rank means a later, rarer word**.  Ranks are unique, so "the
later of two words" is always well defined — no ties.

## 2. What we are estimating

The reference matrix is the corrected adjacency

    M_ref(a, b) = N(a, b) + (prior mass for the cell) ,

where `N` is the observed (cyclic) word-bigram count and the prior fills what
`N` leaves empty.  The claim of this note is that the prior mass of the cell
`(a, b)` should be **shaped like the cell you get by breaking open the later of
the two words**:

    M_ref(a, b) = N(a, b) + alpha · P( break(a,b) ) ,

where

    break(a, b) = (rc(a), b)    if a is the later of the two,
                = (a, lc(b))    if b is the later of the two,

and `P` is the **joint** matrix of bigram probabilities
`P(a,b) = M(a,b) / ΣM` for the `M` built so far (see §4 — this is the crux;
joint, not row-conditional — see §5).  In words: to guess what follows
`a`, look at what follows the last piece of `a`; to guess what precedes `b`,
look at what precedes the first piece of `b`.  Break the **later** word because
it is the one whose *internal* structure carries less information (its children
are already old, well-measured words), so replacing it by its boundary child
loses less.

If the child we exposed is itself a pair, apply the rule again — this is the
recursion.  The **base case is when both `a` and `b` are single characters**;
there the prior is the character-level `P_mar` of `docs/ADJACENCY_MATRIX.md` §6
(`P_mar(a,b) = (r_a/T)(c_b/T)`).

Two special cases fall out of "break the **later** word":

* **`a = b` (a self-loop).**  The two endpoints are the *same* word, so there is
  no later one; breaking a single side would be asymmetric.  Break **both**, so
  the prior of a self-loop `(w,w)` is `alpha·P(rc(w), lc(w))` (§4 fixes this for
  a newly created `w`).
* **Run words (retired).**  A flat `(u^k)` is one **`k`-ary** node, not a chain
  of binary merges, so it has `lc = rc = u`: breaking it drops straight to `u`.
  The run rule has since been deleted — every `dict.txt` rule is now `P a b` —
  so this case is historical and nothing below depends on it.

## 3. The recursion, top-down (for intuition)

For a cell `(a, b)`, repeatedly replace the later word by its boundary child: if
`a` is the later word, break the **left** word (`a → rc(a)`); if `b` is later,
break the **right** word (`b → lc(b)`).  On `((uv),(xy))`:

    break = (v, (xy))   if a = (uv) is the later word  (break a, expose rc(a) = v),
          = ((uv), x)   if b = (xy) is the later word  (break b, expose lc(b) = x),

and recurse until both endpoints are characters; then the prior shape is
`P_mar(break*(a,b))` on the fully-broken cell `break*`.  Concretely, at the top
level,

    prior( ((uv),(xy)) ) = P( v, (xy) )   if a = (uv) is the later word,
                         = P( (uv), x )   if b = (xy) is the later word,

and the right-hand `P(·)` is itself the corrected matrix at the level where that
cell was created.

**This is where the first draft was wrong.**  It wrote `seed((v,(xy)))` for the
case `N((xy)) ≤ N((uv))` — i.e. it broke the *more frequent* word and it used
`N` to choose.  Both are fixed: break the **later** word (§1), by wordlist
order.

## 4. Defining `P`: build `M` bottom-up

`P(a,b) = M(a,b)/ΣM` cannot be evaluated with a fully built `M`, because `M` is
what we are constructing.  The resolution is to build `M` **in `NUM_PAIRS`
order**, so that every prior is taken from an `M` that is already complete *for
the words involved*.

**Level 0 — characters only.**  `M₀(a,b) = N₀(a,b) + alpha·P_mar(a,b)`, the
character×character counts with the character-marginal prior.  Track
`S = ΣM₀`.

**Level `r` — create the word `w = (uv)`.**  Its children `u, v` were born
earlier, so they are already rows/columns of `M`; `w` is the **later** word, so
by §2 we break `w` and add its row and column with the two rules

    M_ref(w, y) = N(w, y) + alpha · P(v, y)      (new row;  v = rc(w))
    M_ref(x, w) = N(x, w) + alpha · P(x, u)      (new column; u = lc(w))

for every already-present `x, y` (and the `(w,w)` cell by either rule).  Here
`P = M / S` is read off the **current** `M`, *before* `w` is inserted — that is
exactly why every cell it references, `(v,y)` and `(x,u)`, is already built.
Update `S` by the mass added.

**Merge bookkeeping.**  Introducing `w` moves count-mass out of the cells the
merge consumes, exactly as in `docs/TREE_WORDS.md` §5.  Subtract
`N(x, w)` from `M(x, u)` (the `(x,u)` bigram lost its `u→v` continuations) and
`N(w, y)` from `M(v, y)`, drop the `(u,v)` cell, correct the `(v,u)` cell by
`A(v) + B(u) − Q`, and add the remaining new cells `(a,w)`, `(v,w)`, `(w,u)`,
`(w,b)`, `(w,w)` from the corresponding `A`, `B`, `Q`.  These are count changes
only: the **prior** term of a cell is fixed once, when the cell is created, and
never recomputed.

### Where the dead cell's mass goes

Once `(uv)` is a word, **no tokenised string contains `u` immediately followed
by `v`**, so `M(u,v)` must be *exactly zero* — count *and* prior.  It is a
structural zero, not a knob.  The two parts of the cell travel differently:

* **The observed count is absorbed by the new word.**  Each of the `N(u,v)`
  occurrences sits in a context `x u v y` and becomes `x w y`; the count mass
  reappears in row `w` / column `w`, spread over the new cells `(x,w)`, `(w,y)`,
  `(w,w)` exactly as the §5 bookkeeping says.  Equivalently `N(w)` gains
  `N(u,v)` while `u` and `v` each lose it — and that `N(u,v)` is precisely the
  number of tokens the merge deletes (the compression gain).  So the dead cell's
  mass goes **into `w`**.
* **The prior is re-expressed, not conserved.**  The prior is a per-cell *shape*
  `alpha·P(break(a,b))`, not a fluid to be balanced.  A dead cell carries no
  shape (otherwise `P_ref(v|u) > 0` for an impossible transition), and the new
  word's cells draw theirs from the boundary child — row `w` from `P(v,·)`
  (`v`'s successors), column `w` from `P(·,u)` (`u`'s predecessors).  The
  internal transition `u→v` is now subsumed by `w`, so its prior *reappears*,
  reshaped, on the new word rather than disappearing.

This is why "prior frozen at creation" needs the qualifier "until the cell is
invalidated": a cell's prior survives a mere count decrement, but a cell that
becomes structurally impossible is zeroed outright.

**`N` and `M` are built together.**  The sweep carries *two* matrices forward,
one per level: the observed counts `N_r` (the level-`r` token-bigram counts,
updated by the §5 bookkeeping or recomputed) and the reference
`M_r = N_r + prior`, whose new-cell priors read `P = M_{r−1}/S` from the level
just passed.  So `N` cannot be skipped — it is both the thing the merge
bookkeeping moves and the base the recursion bottoms out on — and only the
triple `(N_r, M_r, S_r)` need be carried across levels; no level is stored.

**Why this is well defined.**  Every prior quoted at level `r` is `P(ref)` of a
cell whose two endpoints already exist at level `r−1`, so it has a value.  No
circularity, no fully-built `M` required, and `S` is maintained incrementally
(add the new row/column mass, subtract the absorbed mass) rather than summed
from scratch each level.

**Equivalence to §3.**  Building `w`'s row/column with the two rules is exactly
the top-down recursion with "break the later word" at each step: the recursion
on `(rc(a), b)` bottoms out at a cell already present in `M` at the level where
its endpoints were born, whose `P` is the level's normalised matrix.  So the
bottom-up iteration *is* the recursive pair-breaking, reordered so that `P`
exists before it is asked for.

## 5. Joint, not conditional

Both `M` and `P` are the **joint** objects: `M(a,b)` is a count-like mass on the
cell `(a,b)` (its row sums are *not* normalised), and `P(a,b) = M(a,b)/ΣM` is the
**joint** bigram probability, summing to `1` over all cells.  So the prior mass
of a cell is `alpha·P(break(a,b))` with this joint `P` — *not* a row-conditional
`P(y | rc(a))`.  (An earlier draft used a row-normalised shape `alpha·N(a)·S_b(a)`;
that is a different object and is rejected.)  The `kappa` sweep of
`docs/ADJACENCY_MATRIX.md` §7 then re-tunes `alpha` as before.

## 6. Feasibility pass

Is `rc(a)`'s successor distribution close to `a`'s — i.e. is `P(rc(a), ·)` a
reasonable proxy for `P(a, ·)`?  Measured on the `tw2040` word model (2040
merges, `work/tw2040/adj.npz`), over the **182** words `a` whose right child `v`
is itself a surviving word with `N ≥ 10`, as the mean Jensen–Shannon divergence
(bits) between the two row distributions:

| comparator for `row(a)` | mean JS |
|---|---:|
| **right child `rc(a)`** | **0.471** |
| last character of `a` | 0.477 |
| independence `P_mar` | 0.508 |
| left child `lc(a)` | 0.642 |
| random same-vocabulary word | 0.702 |

Reading:

* the right child is the **best single predictor**, and its base case (the last
  character) is a hair behind — the recursion bottoms out usefully;
* breaking open the pair beats the **left** child decisively (right child is
  closer in **86 %** of the 182 cases) — the boundary information is on the
  right, as expected;
* but the margin over the **independence** prior is small (0.471 vs 0.508, ≈0.04
  bits JS) and **per word it only wins about half the time** (51 %).  The current
  prior is a strong baseline; this one is not an obvious win.

## 7. Verdict and next steps

*Plausible but unproven.*  The structure is real and points the right way, but
the gain over independence is modest on this evidence, so it must be judged the
way `kappa` was — by **held-out predictive likelihood** (`choose_kappa.py`'s
train/test binomial thinning), not by row similarity.  Concretely:

1. implement the bottom-up build of §4 on the merge tree (one pass over the
   `wordlist`; the only new code is the two row/column rules and the incremental
   `S` and merge bookkeeping);
2. sweep `kappa` and compare the held-out cross-entropy against the current
   independence prior at `tw96`/`tw512`/`tw2040`;
3. keep it only if it beats independence by more than noise *and* the win grows
   with sparsity — the signature the `kappa` prior showed.

### Details, now settled

(This experiment is judged against the **pair-merge dictionary baseline** of
`docs/TREE_WORDS.md` §9.1 / `docs/WORD_COMPRESSIBILITY.md`.  These builds
predate the deletion of the run rule, which is why run words appear below.)

* **`M_ref(w,w)` = `alpha·P(v,u)`.**  Both endpoints of the self-loop are the
  *same* word `w = (uv)`, so "break the later word" is undefined and breaking one
  side only would be asymmetric.  Break **both** ends to get the internal
  junction `(rc(w), lc(w)) = (v, u)`.  This also matches the observed self-loop
  term — `Q = N(u,v,u,v)` is exactly the `v→u` junction.  Rejected alternatives:
  breaking only the left (a `P(v,w)` prior, i.e. via `N(v,(uv))`) or only the
  right (`P(w,u)`, via `N((uv),u)`).
* **Decrement by `N`; zero a dead cell's `M`.**  A count decrement touches only
  the observed `N`; the prior is frozen at creation.  A cell that becomes
  *structurally impossible* (the dead `(u,v)`) is zeroed outright — count and
  prior (§4).
* **`alpha`** — its best value, and whether it must depend on `NUM_PAIRS`: every
  new word adds a row and a column, so a fixed per-cell `alpha` inflates the
  total prior mass as the vocabulary grows.  Swept below (§8).
* **Run words are `k`-ary with `lc = rc = u`** (historical — the run rule is
  gone).  A flat run word `(u^k)` is one
  **`k`-ary** merge of `k` copies of `u` (one word per length), *not*
  `k−1` nested binary merges.  So `lc((u^k)) = rc((u^k)) = u`: breaking it once
  drops to `u`, its row/column priors use `P(u,·)` / `P(·,u)`, and its self-loop
  prior is `alpha·P(u,u)`.  The dictionary is run-aware throughout, so this build
  sees run words only.

Still open: whether "break the later word" should key on creation rank (chosen,
for determinism) versus depth or `N`; and how the prior interacts with the
*cyclic* structure (the target bigrams include `(a, \n)` and `(\n, b)`).  The
joint-vs-conditional choice is settled: both `M` and `P` are the joint — §5.

Reproduce the table with the `tw2040` files and `scripts/tree_words.py`
(`load_dictionary`, `load_adj`).

## 8. Implemented, and judged on held-out data

*Code: `scripts/break_open_prior.py`.  Runner: `scripts/run_break_open_prior.sh`;
logs `work/tw*_breakopen*.log`; saved traces `work/tw*_trace*.npy`.  Every number
below is **mean bits per held-out identifier, lower is better**.*

### 8.1 The build

`trace_replay` carries the triple `(N_r, M_r, S_r)` of §4 level by level.  The
per-level counts `N_r` come from a *trace* that `tree_words.build_dictionary`
records in the same pass that grows the dictionary: for every pair merge it
stores the left/right neighbours of each merged occurrence (the stop token at a
line boundary, so the counts are the *cyclic* ones), and, in the builds that had
one, the cyclic count matrix after every run step.  One expensive pass therefore yields every level, and the
prior is then rebuilt for a new `alpha` in ~10 s.

Checked (`--selfcheck`, and the trace pass at stride 20, which reproduces the
saved `tw*` dictionaries rule-for-rule):

* the replayed cyclic counts equal a direct count of the finished tokenisation on
  **every** vocabulary cell (0 mismatches);
* on a hand-checked corpus the row, column and self-loop priors equal
  `alpha·P(v,·)`, `alpha·P(·,u)`, `alpha·P(v,u)` read off the *previous* level;
* every dead cell `(u,v)` is exactly `0` in `M`.

Run words are `k`-ary with `lc = rc = u`: their row and column priors are
`alpha·P(u,·)` / `alpha·P(·,u)` and their self-loop `alpha·P(u,u)`.

### 8.2 Protocol

Dictionary and counts both come from the dictionary's own training sample
(stride 20); the held-out identifiers are `merged_validation` (stride 20,
disjoint from training; §8.7 re-runs the comparison at stride 10,
`n = 42,268`), scored under the first-order word Markov model
`P_ref(b|a) = M(a,b) / Σ_y M(a,y)`, with `alpha = kappa·V`.  The `unobs%` column
is the share of held-out bigram tokens whose *training* count is zero — exactly
the cells the prior is there to fill.

*Why not literal binomial thinning.*  `choose_kappa.py` thins the **final** count
matrix.  This prior needs the counts at **every** level, and `N_r` cannot be
recovered from a thinned `N_final` — thinning the final matrix is simply not
defined for it.  The line-level held-out split used instead is the "fully
faithful split … re-derive `(a,b)` from held-out identifiers" that
`choose_kappa.py`'s own docstring calls the ideal, and is strictly cleaner than
the thinning approximation.

### 8.3 Results

`mar` = independence `P_mar` (the pair-merge-dictionary baseline); `break` = the
break-open prior of §4; `breakz` = the same shape rescaled to total prior mass
`alpha` (see §8.4).  Best row per model in **bold**.

**`tw96`** — vocab 160, 7.5% of held-out tokens unobserved in training

| kappa |   mar | break | breakz |
|------:|------:|------:|-------:|
|    10 | 78.41 | 79.45 |  82.41 |
|    30 | 76.81 | 77.92 |  80.80 |
|   100 | 75.08 | 76.48 |  79.04 |
|   300 | 73.60 |**75.82**| 77.49 |
|  1000 | 72.36 | 76.58 |  76.11 |
|  3000 |**72.27**| 79.11 | 75.83 |

**`tw512`** — vocab 576, 11.5% unobserved

| kappa |   mar | break | breakz |
|------:|------:|------:|-------:|
|    10 | 65.67 | 67.61 |  71.73 |
|    30 | 63.87 |**66.57**| 69.83 |
|   100 | 62.09 | 66.84 |  67.92 |
|   300 |**61.00**| 68.72 | 66.68 |
|  1000 | 61.31 | 72.20 |  66.70 |
|  3000 | 63.72 | 76.05 |  68.59 |

**`tw2040`** — vocab 2104, 22.8% unobserved

| kappa |   mar | break | breakz |
|------:|------:|------:|-------:|
|    10 | 56.22 |**60.34**| 65.39 |
|    30 | 53.84 | 60.54 |  62.69 |
|   100 |**52.10**| 62.26 | 60.70 |
|   300 | 52.15 | 64.75 |**60.21**|
|  1000 | 54.35 | 68.13 |  61.34 |
|  3000 | 57.26 | 71.15 |  63.67 |

### 8.4 The `alpha` sweep, and the mass inflation §7 predicted

§7 asked whether `alpha` must shrink as `NUM_PAIRS` grows.  It must: the break
rule gives every new word a full row *and* column of prior, so the total prior
mass is `alpha · Σ_w [marg(rc(w)) + marg(lc(w))]`, and that factor grows with the
vocabulary — **7.7×** (`tw96`), **14.2×** (`tw512`), **23.8×** (`tw2040`),
**29–65×** (`tw4096ns`), **40–66×** (`tw8192ns`).  The
best `kappa` consequently drifts downwards as the vocabulary grows (3000 → 300 →
10 for `break`), so §8.3 does *not* compare the two priors at equal mass.

`breakz` removes that confound by rescaling the break shape to total prior mass
`alpha`, the same as `P_mar`.  It does not help: `breakz`'s best is within
0.1 bits of `break`'s at every size (75.83 vs 75.82, 66.68 vs 66.57, 60.21 vs
60.34).  **The deficit is in the shape, not in the mass.**

### 8.5 Findings

1. **It loses at every size and every `alpha`.**  At each prior's own best
   `kappa` the deficit is **3.55** bits (`tw96`), **5.57** (`tw512`), **8.24**
   (`tw2040`) — and it grows with the vocabulary.
2. Mass-matching does not rescue it (§8.4), and neither does a mixture: on
   `tw2040` the mean bits fall **monotonically** towards `lambda = 1` (pure
   `P_mar`) at every `kappa`, e.g. `kappa=30`: 62.69 (λ=0) → 56.20 → 54.96 →
   54.26 (λ=0.75) → 53.85 (λ=0.99) → 53.84 (λ=1).  Even a 1% weight on the
   break shape hurts.  **The break shape carries nothing the marginal lacks on
   these cells.**
3. **The loss sits on exactly the cells the prior exists to fill.**  Restricted
   to held-out bigrams *unseen in training*, `mar` gives 6.9 / 7.0 / 8.5 bits
   (`tw96`/`tw512`/`tw2040`; 5.6 / 4.9 / 6.5 at `kappa=3000`) where `break` gives
   9.6 / 11.5 / 12.6.  The prior is *worse* where it is meant to help.
4. **It is not an estimation artefact of too little data.**  Growing the training
   set 4-fold (a fresh dictionary at each stride, so both priors see the same
   model) barely moves the deficit — **8.75 / 8.24 / 8.03** bits at strides
   **40 / 20 / 10**, while the unobserved share falls only 25.5% → 22.8% → 20.3%.
   Rows (best `kappa` per model):

   | train stride | train ids | unobs% |   mar | break | deficit |
   |---:|---:|---:|---:|---:|---:|
   | 40 |  51646 | 25.5% | 51.96 | 60.71 | 8.75 |
   | 20 | 103291 | 22.8% | 52.10 | 60.34 | 8.24 |
   | 10 | 206581 | 20.3% | 51.95 | 59.98 | 8.03 |

   The **sign of the sparsity trend is the opposite** of the one §7 hoped for
   ("keep it only if it … wins more as sparsity grows").

   The literal **thinning-style protocol** agrees: a 9:1 split *within* the
   sample (dictionary and counts from the 92 961 train lines, scored on the
   10 330 held-out lines of the same sample, `unobs%` 28.4%) gives `mar` 53.99,
   `break` 62.78, `breakz` 62.94 at `tw2040` — again a **8.79**-bit deficit.
   (`work/tw2040_breakopen_split.log`.)
5. **5.6% of the cells between occurring words get exactly zero mass** (`tw2040`
   `break`: 248 334 of 4 414 201; `mar`: 0).  They are the cells whose `break`
   parent is itself a dead cell — the structural zero propagates outwards along
   the recursion — so the rule is *not* a smoothing: it can assign probability
   zero to a possible bigram.  None was hit by this held-out set, but it is a
   latent hazard.
6. **Row similarity is not the operative criterion.**  §6's ordering *does*
   reproduce on this data (raw count rows, 1275 words): mean JS right child
   **0.687** < independence 0.716 < random 0.806 < left child 0.844, the right
   child winning against independence **59%** of the time.  And yet the prior
   built from it loses by 8 bits.  §7 was right to insist on held-out
   likelihood: the child's row is close to the word's row *on the cells the word
   has*, which is not where a prior earns its keep — on the unobserved cells the
   child's row is a *spiky* guess (mass where the child's own successors were),
   and cross-entropy punishes exactly those spikes.

### 8.6 Verdict

**Do not adopt the break-open prior as specified.**  It is 3.5–8.2 bits worse
than the independence prior at `tw96`/`tw512`/`tw2040` and **10.1–10.9 bits**
worse at the canonical grid (§8.7), it is worse precisely on the unobserved
cells, the deficit grows with the vocabulary as well as with sparsity, and
neither mass-matching nor any mixture with the marginal recovers it.  §6's "plausible but modest" row-similarity signal was real, but it is not
the signal that decides.

The last conceivable rescue — interpolating the child row with the marginal,
`prior(w,y) = alpha·[(1-lambda_w)·(child row) + lambda_w·P_mar(w,y)]`, with a
*per-row* `lambda_w` — is **retired (dropped 2026-10-31; not needed)**.
§8.5(2) already answers the global-lambda version (no `lambda < 1` beats
`lambda = 1`, and even a 1% weight on the break shape hurts), and findings 1 and
3–5 locate the loss in the *shape* on exactly the unobserved cells the prior is
meant to fill, so a per-row `lambda_w` has no failure mode left to repair.  The
prior stays the independence `P_mar` over the pair-merge dictionary.

### 8.7 At the canonical grid (10-ecosystem corpus)

Re-measured on `work/tw4096ns` and `work/tw8192ns`, same protocol
(dictionary and counts from the build's own 5 % sample; held-out
`merged_validation` at stride 10, `n = 42,268`), modes `mar` and `break`
(`breakz` is within 0.1 bits of `break` and is not repeated).  The `break − mar`
column is the deficit at that `kappa`; bold marks the best row of each prior.

**`V = 4,096`, 29.9 % of held-out bigram tokens unobserved**

| kappa | mar | break | break − mar | prior mass / α (break) |
|---:|---:|---:|---:|---:|
| 10 | 53.680 | **58.851** | +5.17 | 65.2 |
| 30 | 50.965 | 58.750 | +7.79 | 44.1 |
| 100 | 48.911 | 59.626 | +10.72 | 34.9 |
| 300 | **48.635** | 61.333 | +12.70 | 31.4 |
| 1000 | 50.173 | 63.971 | +13.80 | 29.9 |
| 3000 | 52.239 | 66.455 | +14.22 | 29.4 |

**`V = 8,192`, 36.7 % unobserved**

| kappa | mar | break | break − mar | prior mass / α (break) |
|---:|---:|---:|---:|---:|
| 10 | 50.466 | **57.324** | +6.86 | 66.2 |
| 30 | 47.860 | 57.505 | +9.65 | 50.8 |
| 100 | **46.448** | 58.696 | +12.25 | 43.9 |
| 300 | 46.874 | 60.636 | +13.76 | 41.4 |
| 1000 | 48.458 | 63.210 | +14.75 | 40.3 |
| 3000 | 49.981 | 65.294 | +15.31 | 40.0 |

At the best `kappa` the deficit is **10.1 bits at 4096 and 10.9 at 8192**
(48.635 / 46.448 against 58.750 / 57.324), and on the 64-bit fit it is
**12.8 / 13.6 points** (83.8 / 87.1 % against 71.0 / 73.5 %).  The pre-grid
deficits were 3.5, 5.6 and 8.2 bits at `tw96` / `tw512` / `tw2040`, so the growth
with vocabulary is not only confirmed but steepened, and the mass inflation
(29–66× against the 23.8× at `tw2040`) tracks it.

The mixture test, re-run at 4096 (`--mix`, `kappa = 10…1000`): **`lambda = 1`
wins at every `kappa`**, and the loss from a 1 % weight on the break shape is
0.005–0.008 bits (48.916 against 48.911 at `kappa = 100`), so the shape has no
weight worth carrying.  The unobserved cells — the ones the prior exists to fill
— are still the worst ones: 11.32 bits against `mar`'s 8.34 at 8192,
`kappa = 300`.

**Verdict: unchanged, and stronger.**  The grid result is not a borderline call
that a different `kappa` might rescue; the best break point is 10 bits behind
the best independence point, and the gap widens with `V`.

```sh
python3 scripts/break_open_prior.py --dir work/tw4096ns --score-stride 10 \
  --kappas 10,30,100,300,1000,3000 --modes mar,break --save-trace /tmp/tw4096_trace.npy
python3 scripts/break_open_prior.py --dir work/tw8192ns --score-stride 10 \
  --kappas 10,30,100,300,1000,3000 --modes mar,break --save-trace /tmp/tw8192_trace.npy
python3 scripts/break_open_prior.py --dir work/tw4096ns --load-trace /tmp/tw4096_trace.npy \
  --score-stride 10 --mix --kappas 10,30,100,300,1000
```

## 9. Withdrawing the prior on absorbed row/column mass (tried, rejected)

Finding 5 said the rule can assign **exactly zero** to a bigram between two
occurring words, because the structural zero of a dead cell propagates outwards
along the recursion.  A structural zero raised by the tokeniser is *correct*:
if `(uv)` is a word, no tokenised string contains `u` then `v`.  The suspicion
(rationale from `rules/` design review) was that the prior is **under-retracted**:
when the word `(uv)` is made, observed mass moves from `N(x,u)` to `N(x,uv)`
(and from `N(v,y)` to `N(w,y)`), but the prior on `(x,u)` / `(v,y)` is left in
place, so a word that has been fully absorbed (`u` no longer occurs as a token)
still carries prior mass.  The proposed repair: retract it **in proportion**,

    prior(x,u) *= 1 - N(x,uv) / N(x,u)        (and prior(v,y) *= 1 - N(w,y)/N(v,y)),

applied at each pair step (`--shrink prop`), or only when the context is *fully*
absorbed (`--shrink hard`).

Both variants were implemented in `trace_replay` (the `shrink` argument of
`scripts/break_open_prior.py`).  `prop` and `hard` produce the **same set of
exact zeros** (a proportional factor `1 - c/den` is zero exactly when the cell
is fully absorbed), but `prop` also *reduces* the prior on partially absorbed —
still live — cells.

`tw2040`, best-`kappa` comparison (held-out `merged_validation`, stride 20,
11 477 identifiers; "live zeros" = cells that are `M = 0` while both words have
nonzero marginal count, i.e. finding 5's hazard metric):

| prior | mean bits | unobs bits | live zeros | live-zero % | prior mass / α |
|---|---:|---:|---:|---:|---:|
| `mar` | 52.10 | 8.50 | 0 | 0.00 % | 1.00 |
| `break` | 62.26 | 10.38 | 248 334 | **5.63 %** | 22.7 |
| `break` + `hard` | 67.22 | 13.45 | 849 744 | **19.25 %** | 20.7 |
| `break` + `prop` | 67.12 | 13.38 | 849 744 | **19.25 %** | 14.1 |

**It does not resolve finding 5 — it makes it three-and-a-half times worse.**
The retraction *adds* zeros (5.6 % → 19.3 % of live cells, 248 k → 850 k) and the
held-out rate gets *worse* (62.3 → 67.1 bits at `kappa = 100`; every `kappa`
shows the same direction).  The extra zeros are the "absorbed-context" cells: a
context `(x,u)` all of whose occurrences are swallowed by a word is indeed
structurally impossible, so *as zeros they are harmless*.  The harm is that the
withdrawn mass is **not redistributed** — it is simply removed — so the prior on
the still-live, still-unobserved cells is starved and the model loses the
smoothing it was there to give.  Retracting spurious mass is only useful if the
mass is moved somewhere live, which is a different repair (see the structural-
zero treatment of the *independence* prior, `ADJACENCY_MATRIX.md`).

Verdict: **rejected.**  Finding 5 is not the reason the break-open prior loses;
removing the offending zeros does not help, and the prior remains retired.

### 9.1 Are the extra zeros even structural? (no)

It is tempting to read the retraction as *discovering* structural zeros of the
word matrix and to feed them back into the **independence** prior: take
the 849 744 absorbed cells the retraction zeroes, zero `P_mar` there and
renormalise.  It fails the same way, and more sharply:

| prior (`tw2040`, `kappa = 100`) | mean bits | unobs bits |
|---|---:|---:|
| `mar` | 52.10 | 8.50 |
| `mar` zeroed on the absorbed cells, renormalised | 57.10 | 11.40 |

So the zeros the retraction produces are **not** structural: they include cells
whose two words both occur but which were merely *unobserved* in training, i.e.
exactly the bigrams the prior exists to predict.  Zeroing them is worse than
leaving the independence prior alone.  The genuinely structural cells (dead
`(uv)` pairs) are a negligible ~2 × 10³ out of 4.4 × 10⁶, and zeroing them
changes nothing.
