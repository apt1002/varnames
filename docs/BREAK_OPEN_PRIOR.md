# Breaking open the pair: a structured prior for the word adjacency

`docs/WORD_COMPRESSIBILITY.md` models the tokenised corpus with a first-order
Markov chain over **words**, filling unobserved bigrams with the *unstructured*
independence prior of `docs/ADJACENCY_MATRIX.md` §6,

    P_ref(v | u) = [ N(u,v) + alpha·(r_u/T)(c_v/T) ] / [ r_u·(1 + alpha/T) ] ,

whose shape `P_mar` treats every vocabulary item alike.  But the words are
**built**, not given: a word `(uv)` is two earlier words glued together, on down
to single characters.  That structure is information the independence prior
throws away.  This note designs a prior that uses it — *breaking open the pair*.

**This is a design note; it is not yet wired into the model.**  It fixes the two
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
* **Run words.**  A flat `(u^k)` is one **`k`-ary** node, not a chain of binary
  merges, so it has `lc = rc = u`: breaking it drops straight to `u`.

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

(Tracked as **C5** in `PLAN.md`; C5 is compared against the **run-aware C6
baseline**.)

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
  total prior mass as the vocabulary grows.  To be swept in C5.
* **Run words are `k`-ary with `lc = rc = u`.**  A flat run word `(u^k)` is one
  **`k`-ary** merge of `k` copies of `u` (one word per length, per A2), *not*
  `k−1` nested binary merges.  So `lc((u^k)) = rc((u^k)) = u`: breaking it once
  drops to `u`, its row/column priors use `P(u,·)` / `P(·,u)`, and its self-loop
  prior is `alpha·P(u,u)`.  The dictionary is run-aware throughout (C6), so C5
  sees run words only.

Still open: whether "break the later word" should key on creation rank (chosen,
for determinism) versus depth or `N`; and how the prior interacts with the
*cyclic* structure (the target bigrams include `(a, \n)` and `(\n, b)`).  The
joint-vs-conditional choice is settled: both `M` and `P` are the joint — §5.

Reproduce the table with the `tw2040` files and `scripts/tree_words.py`
(`load_dictionary`, `load_adj`).
