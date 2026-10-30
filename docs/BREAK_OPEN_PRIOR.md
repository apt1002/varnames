# Breaking open the pair: a structured prior for the word adjacency

`docs/WORD_COMPRESSIBILITY.md` models the tokenised corpus with a first-order
Markov chain over **words**, filling unobserved bigrams with the *unstructured*
independence prior of `docs/ADJACENCY_MATRIX.md` §6,

    P_ref(v | u) = [ N(u,v) + alpha·(r_u/T)(c_v/T) ] / [ r_u·(1 + alpha/T) ] ,

whose shape `P_mar` treats every vocabulary item alike.  But the words are
**built**, not given: a word `(uv)` is two earlier words glued together, on down
to single characters.  That structure is information the independence prior
throws away.  This note designs a prior that uses it — *breaking open the pair* —
and reports a feasibility pass.  **This is a design note; it is not yet wired
into the model.**

## The idea

A word's **successor** is governed mostly by how it *ends*.  `(uv)` should be
followed by roughly what `v` is followed by; and if `v` is itself a pair `(xy)`,
by roughly what `y` is followed by; on down to single characters.  So for an
unobserved bigram `((uv), w)` we *break the pair open* and seed it from the
observed `(v, w)`, recursively.

## The recursion

Let the dictionary be the merge tree of `docs/TREE_WORDS.md`: a word `a` created
by a merge has children `(u, v)`, with `v` the **right** child (adjacent to
whatever follows `a`) and `u` the left child (adjacent to whatever precedes).
Write `rc(a)` for the right child and `lc(a)` for the left child; a single
character has neither.

For a target bigram `(a, b)` with a word `b` as successor, the back-off shape is

    seed( (a, b) ) =  seed( (rc(a), b) )                     if a is a pair and rc(a) is observed,

i.e. "look at what follows the last piece of `a`".  Recurse on `rc(a)` until
either the bigram `(·, b)` is observed, or `a` is a single character (base
case), in which case fall back to the independence/`kappa` shape.

**When both words are pairs:** `(a, b) = ((uv), (xy))`.  Breaking `a` gives
`(v, (xy))`; breaking `b` gives `((uv), x)` — both are one level down.  The rule
is to break the **later (rarer)** one: count-wise `b` is the successor word, and
breaking the *rarer* of the two loses less information, so

    seed( ((uv),(xy)) ) = seed( (v,(xy)) )      if N((xy)) <= N((uv)),
                         = seed( ((uv),x) )      otherwise,

then recurse.  (Rarer = smaller `N(·)`; ties break to the right word, matching
the left-to-right reading.)

**Base case:** single characters, at which point `seed` is the character-level
successor distribution — the same object `docs/CODE_LENGTHS.md` estimates with
its long-suffix variable-order model, so the two studies share a boundary.

## Using the seed in the prior

The seed gives a **shape** `S_b(a) = seed((a,b)) / Σ_{b'} seed((a,b'))`, which
replaces `P_mar` column-wise:

    M_ref((a,b)) = N(a,b) + alpha · N(a) · S_b(a) ,

so the prior mass is still "per context" (`alpha·N(a)` for context `a`) and
falls back to `P_mar` exactly where the recursion has no information.  The
existing `kappa` sweep (`docs/ADJACENCY_MATRIX.md` §7) then re-tunes `alpha`.

## Feasibility pass

Is `rc(a)`'s successor distribution actually close to `a`'s?  Measured on the
`tw2040` word model (2040 merges, `work/tw2040/adj.npz`), over the **182** words
`a` whose right child `v` is itself a surviving word with `N ≥ 10`, as the mean
Jensen–Shannon divergence (bits) between the two row distributions:

| comparator for `row(a)` | mean JS |
|---|---:|
| **right child `rc(a)`** | **0.471** |
| last character of `a` | 0.477 |
| independence `P_mar` | 0.508 |
| left child `lc(a)` | 0.642 |
| random same-vocabulary word | 0.702 |

Reading:

* the right child is the **best single predictor**, and its base case (the last
  character) is a hair behind — the recursion does bottom out usefully;
* breaking open the pair beats the **left** child decisively (right child is
  closer in **86 %** of the 182 cases) — the boundary information is on the
  right, as expected;
* but the margin over the **independence** prior is small (0.471 vs 0.508, ≈0.04
  bits JS) and **per word it only wins about half the time** (51 %).  So the
  current prior is a strong baseline and this one is not an obvious win.

## Verdict and next steps

*Plausible but unproven.*  The structure is real and points the right way, but
the gain over independence is modest on this evidence, so it must be judged the
way `kappa` was — by **held-out predictive likelihood** (`choose_kappa.py`'s
train/test binomial thinning), not by row similarity.  Concretely:

1. implement `seed` on the merge tree (one pass over the `wordlist`; cheap);
2. build `S_b(a)` and splice it into `M_ref` as above;
3. sweep `kappa` and compare the held-out cross-entropy against the current
   independence prior, at `tw96`/`tw512`/`tw2040`;
4. keep it only if it beats independence by more than noise *and* the win grows
   with sparsity (the signature the `kappa` prior showed).

Open questions: whether to recurse on **both** words (a “product” seed) rather
than one; whether the "rarer" tie-break should be by `N` or by depth; and how the
seed interacts with the *cyclic* structure (the target bigrams include `(a,\n)`).

Reproduce the table with the `tw2040` files and `scripts/tree_words.py`
(`load_dictionary`, `load_adj`).
