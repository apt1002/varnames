# Corpus

Corpus is a multiset of strings of characters (e.g. programming language identifiers).

Suppose, as a warm-up exercise, that the corpus does not contain three consecutive repeats of any substring. We can relax this condition later.

Suppose the characters `(`, `)` and `\n` do not appear in the corpus.

Append to each string a stop character (I will use `\n`) and bend it into a cycle.


# Build a dictionary

Initialise the set of *words* to be the set of characters plus `\n`. The corpus will hereafter be treated as a multiset of cyclic strings of words.

Initialise the *wordlist* to be an empty list of pairs of words.

Repeat NUM_PAIRS times:

- Find in the corpus the most common length-2 substring `uv` where `u` and `v` are words.

- Add `(uv)` to the set of words.

- Append `(uv)` to the wordlist.

- Replace in the corpus every occurrence of `uv` with `(uv)`. Note that other occurrences of `u` and `v` are unaffected.


# Tokenise an unseen string.

Given an unseen string `s` of characters, append `\n`, bend it into a cycle, and reinterpret it as a string of words.

For each `uv` in the wordlist:

- Replace in `s` every occurrence of `uv` with `(uv)`.

Thus, building the dictionary turns the corpus from a multiset of strings into a multiset of tokenised strings.


# Measure statistics of the corpus

Measured:

- N is number of words (maybe \n) in corpus

- N(u) is number of occurrences of word `u` in the corpus.

- N(u, v) is number of occurrences of `uv` in the corpus.

Note that an occurrence of the word `(uv)` does not count as an occurrence of the word `u`. The count does not look inside brackets.

Derived quantities:

- N(\n) is number of strings.

- N - N(\n) is number of actual words.

- P(u) is N(u) / N

- P(u, v) is N(u, v) / N

- P(v | u) = P(u, v) / P(u)


# Estimate the probability of a string.

We model of the probability of a tokenised string `u_0 u_1 ... u_n` with `u_0` = `u_{n+1}` = `\n`. The probability is expressed in terms of the probabilities of its length-2 substrings.

P(u0 ... u_n) = product over i in 0 .. n of P(u_{i+1} | u_i)
    = (product of P(u_i, u_{i+1})) / (product of P(u_i))

Compressed size of the strings is -log2(its probability).


# Corpus size

The corpus size `CS` (smaller better) is the sum over the corpus of the compressed size of its strings.

In the limit of plentiful training data (`N` much larger than `NUM_PAIRS`) no
smoothing is needed, and, with `L(z) = z·log z` (any log base; `L(0) = 0`), the
corpus size is the unsmoothed bigram model's

    CS = S1 - S2 ,   S1 = sum over u of L(N(u)) ,   S2 = sum over u, v of L(N(u, v))

where `S1` collects the unigram counts and `S2` the bigram counts.


# Effect of incrementing `NUM_PAIRS`

One increment merges a single pair of words `u`, `v` into a new word `w`.  Each
occurrence of `uv` sits in a context `a u v b`, with `a` the predecessor word and
`b` the successor word.  The *only* aggregates that enter are

    A(x) = N(x, u, v)     occurrences of uv whose predecessor is x  (sum_x A = N(u,v))
    B(y) = N(u, v, y)     occurrences of uv whose successor   is y  (sum_y B = N(u,v))
    Q    = N(u, v, u, v)  adjacent uvuv patterns                    (see below)

`Q` is the one awkward piece: two *adjacent* occurrences of `uv` (pattern
`uvuv`) merge into the bigram `ww`.  It is a 4-gram count.  Under the
three-consecutive-repeats assumption each `uvuv` is isolated (three consecutive
`uv` pairs would be `(uv)³`, which is forbidden), so `Q` counts every adjacency
exactly once.  If the adjacency is ignored (`Q = 0`) only 3-gram counts remain.

With `Δ = CS' − CS` (so a merge that *improves* compression gives `Δ < 0`):

    Δ = ΔS1 − ΔS2

    ΔS1 = L(N(u)−N(u,v)) − L(N(u))  +  L(N(v)−N(u,v)) − L(N(v))  +  L(N(u,v))

    ΔS2 =  −L(N(u,v))                                       (u,v)  -> gone
        + Σ_{x≠v} [ L(N(x,u) − A(x)) − L(N(x,u)) ]         (x,u)  decremented
        +       [ L(N(v,u) − A(v) − B(u) + Q) − L(N(v,u)) ]  (v,u)  both decrements
        + Σ_{y≠u} [ L(N(v,y) − B(y)) − L(N(v,y)) ]         (v,y)  decremented
        + Σ_{a≠v} L(A(a))                                  (a,w)  created
        +       L(A(v) − Q)                                (v,w)
        +       L(B(u) − Q)                                (w,u)
        + Σ_{b≠u} L(B(b))                                  (w,b)  created
        +       L(Q)                                       (w,w)  created

(`Σ_{x≠v}` is over all words in the current vocabulary; `w` itself is new, so
it never appears in the "decremented" sums.)

Reading the cases.  The pair `(u,v)` disappears, hence `−L(N(u,v))`.  Every bigram
`(x,u)` whose `u` is consumed loses one per matching occurrence, hence `A(x)`;
symmetrically `(v,y)` loses `B(y)`.  Where a `w` token appears it contributes a
*new* bigram, hence the `L(A(·))` and `L(B(·))` terms.

The `(v,u)` line is the only place the two decrements collide: a `(v,u)` bigram
is removed both because its `u` is matched (giving `A(v)`) and because its `v`
is matched (giving `B(u)`), and the pattern in which both are true — `uvuv` —
has been counted twice, hence `+Q`.  The same `uvuv` patterns are what produce
the `(w,w)` bigram, hence the paired `−Q` in the `(v,w)` and `(w,u)` lines and
`+L(Q)` at the end: mass is moved from `(v,w)` and `(w,u)` into `(w,w)`.

**The pair can be `(u,u)`.**  Merging a doubled word `(z,z)` (allowed: `uu`
occurs, only `uuu` is forbidden) is a special case, because one merge consumes
*two* copies of `z`, and the three-repeats assumption forces
`Q = A(z) = B(z) = 0`:

    ΔS1 = L(N(z)−2N(z,z)) − L(N(z)) + L(N(z,z))

    ΔS2 =  −L(N(z,z))                                   (z,z)  -> gone
        + Σ_{x≠z} [ L(N(x,z) − A(x)) − L(N(x,z)) ]     (x,z)
        + Σ_{y≠z} [ L(N(z,y) − B(y)) − L(N(z,y)) ]     (z,y)
        + Σ_{a≠z} L(A(a)) + Σ_{b≠z} L(B(b))            (a,w), (w,b)

(No `(w,w)` term: a `ww` would need `uuuu`.)

Total effect of incrementing `NUM_PAIRS` by `K` is the sum of `Δ` over the `K`
successive merges.

## In terms of the trigram factor `m(a,b,c)`

With the definition

    m(a,b,c) = N(a,b,c) N(b) / ( N(a,b) N(b,c) )

i.e. `N(a,b,c) = m(a,b,c) · N(a,b) · N(b,c) / N(b)`, the aggregates become pure
functions of the bigram counts and the `m`'s:

    A(x) = m(x,u,v) · N(x,u) · N(u,v) / N(u)
    B(y) = m(u,v,y) · N(u,v) · N(v,y) / N(v)
    A(v) = m(v,u,v) · N(v,u) · N(u,v) / N(u)
    B(u) = m(u,v,u) · N(u,v) · N(v,u) / N(v)

and `Q` needs the 4-gram analogue,
`m(a,b,c,d) = N(a,b,c,d) N(b,c) / ( N(a,b,c) N(b,c,d) )`.  Here the middle pair
is `(b,c) = (v,u)`, so the normaliser is `N(v,u)`, *not* `N(u,v)`:

    Q    = m(u,v,u,v) · B(u) · A(v) / N(v,u) .

`m(a,b,c) = 1` is exactly the statement that the 3-gram is fixed by the pair
counts — that the next word depends on the previous one but not on the one
before it.

## Separating the `NUM_PAIRS` part from the `m` part

Substituting the `m`'s into `Δ` splits it into a piece fixed by the bigram table
and a piece carrying the higher-order dependence:

    Δ = Δ⁽¹⁾ + Δ⁽ᵐ⁾

* **`Δ⁽¹⁾`** is `Δ` with every `m(·)` set to 1:

      A₁(x) = N(x,u) · N(u,v) / N(u)    B₁(y) = N(u,v) · N(v,y) / N(v)
      A₁(v) = N(v,u) · N(u,v) / N(u)    B₁(u) = N(u,v) · N(v,u) / N(v)
      Q₁    = N(v,u) · N(u,v)² / ( N(u) N(v) )

  — the `NUM_PAIRS` contribution, the change you would see if the corpus were
  first-order (bigram) consistent under its own pair counts.
* **`Δ⁽ᵐ⁾ = Δ − Δ⁽¹⁾`** carries everything else: it is a function of the
  deviations `m(a,b,c) − 1` and `m(u,v,u,v) − 1`, and it vanishes identically
  when the corpus is first-order consistent.

### `Δ⁽¹⁾` vanishes for a distinct-pair merge

The surprise is that `Δ⁽¹⁾` **is identically zero** when `u ≠ v`.  The context
sums collapse.  Write `λ = N(u,v)/N(u)`, so `A₁(x) = λ·N(x,u)` and the three
terms contributing to `ΔS2` at each predecessor `x ≠ v` are

    −L(N(x,u)) + L(N(x,u) − A₁(x)) + L(A₁(x))
      = −L(N(x,u)) + L(N(x,u)(1−λ)) + L(N(x,u)λ)
      = N(x,u) · h(λ) ,

where `h(λ) = (1−λ) log(1−λ) + λ log λ`.  The `log N(x,u)` cancels exactly — so
the whole `x`-sum depends only on `Σ_{x≠v} N(x,u) = N(u) − N(v,u)`, and likewise
the `y`-sum on `N(v) − N(v,u)`:

    Σ_{x≠v} [ … ] = (N(u) − N(v,u)) · h(λ) ,   λ = N(u,v)/N(u)
    Σ_{y≠u} [ … ] = (N(v) − N(v,u)) · h(μ) ,   μ = N(u,v)/N(v)

The boundary terms (the gap, the new `(v,w)`, `(w,u)`, `(w,w)` bigrams) are
    `−L(N(u,v)) + L(N(v,u)(1−λ)(1−μ)) − L(N(v,u)) + L(N(v,u)λ(1−μ))
     + L(N(v,u)μ(1−λ)) + L(N(v,u)λμ)`
and `ΔS1 = L(N(u)−N(u,v)) − L(N(u)) + L(N(v)−N(u,v)) − L(N(v)) + L(N(u,v))`.
A two-line expansion of `L` (done symbolically, in the regression test) shows
`ΔS1 − ΔS2 = 0` in the four counts `N(u), N(v), N(u,v), N(v,u)`.

Consequences:

* `Δ = Δ⁽ᵐ⁾` **exactly**.  A merge changes the corpus size only through the part
  of the trigram (and 4-gram) statistics that the bigram table does not already
  determine.  In a corpus that is **genuinely first-order Markov** — no trigram
  *and* no 4-gram dependence — `Δ = 0`: no merge changes the description length.
  Consistency of the trigram factors *alone* (`m ≡ 1`) is **not** enough; see
  "`Δ` can be negative with all trigram factors `m = 1`" below.
* The four-count dependence means the greedy "most frequent pair" rule, which
  sees only bigrams, is a proxy for greedy-by-`Δ` only up to the `m`'s.

### The doubled-word merge is the exception

For `u = v = z` one merge consumes *two* copies of `z`, and `Δ⁽¹⁾` does **not**
vanish.  It still collapses, now to a function of the two counts
`N(z), N(z,z)` alone:

    Δ⁽¹⁾ = L(N(z) − 2N(z,z)) − L(N(z)) + 2L(N(z,z))
           − 2(N(z) − N(z,z)) · h( N(z,z)/N(z) ) .

### `Δ` in terms of conditional entropies

Since `Δ = Δ⁽ᵐ⁾`, substitute the `m`'s into the aggregates and cancel.  Each
occurrence pair `L(N(x,u) − A(x)) + L(A(x))` collapses.  With
`q_x = N(x,u,v)/N(x,u)` (and `A(x) = N(x,u)·q_x`) and the binary entropy
`H(q) = −q·log q − (1−q)·log(1−q)`,

    L(N(x,u) − A(x)) + L(A(x)) = N(x,u)·[ log N(x,u) + H(q_x) ] ,

so the `log N(x,u)` cancels against the `−L(N(x,u))` in `ΔS2`.  Exactly as for
`Δ⁽¹⁾`, the `x`-sum therefore carries only entropies, and likewise the `y`-sum,
leaving the exact identity

    Δ = Σ_{x≠v} N(x,u)[ H(P(v|x,u)) − H(P(v|u)) ]
      + Σ_{y≠u} N(v,y)[ H(P(u|v,y)) − H(P(u|v)) ]
      − N(v,u)[ H(P(v|u)) + H(P(u|v)) − H(p) ] ,

where `P(v|x,u) = N(x,u,v)/N(x,u)`, `P(v|u) = N(u,v)/N(u)`, and `p` is the
four-way distribution over the `(v,u)` bigram split by (predecessor is `v`) ×
(successor is `u`), whose product baseline `P(v|u) ⊗ P(u|v)` has entropy
`H(P(v|u)) + H(P(u|v))`.  So a merge's effect on the corpus size is (minus) the
drop in the conditional entropy of the next word, summed over the consumed
contexts, less a four-way dependence term.  No trace of `log N(x,u)` remains.

### `Δ` can be negative with all trigram factors `m = 1`

The entropy form makes the two contributions explicit.  The first two sums
vanish whenever every trigram factor equals one — `m(x,u,v) = m(u,v,y) = 1`,
i.e. the corpus is first-order Markov at the **trigram** level — leaving only
the four-way term

    Δ = −N(v,u) [ H(λ) + H(μ) − H(p) ] .

That vanishes only when the four-way table `p` is its product baseline, i.e.
when there is no **4-gram** dependence around the merged bigram.  Trigram
consistency does *not* imply this.  Example (three strings, `\n` appended and
bent into cycles):

    "01",  "01",  "00111010100011"

has `N(0,1) = 6` and `N(a,b) = 3` for the five other observed bigrams.  All
thirteen trigram factors `m` are exactly `1`, yet merging `01` **reduces** `CS`
by `0.523` nats (`0.755` bits).  With `λ = μ = 2/3`, `N(v,u) = N(1,0) = 3`,
`a = N(1,0,1) = 2`, `b = N(0,1,0) = 2`, `Q = N(0,1,0,1) = 1`, the four-way table
is `p = (0, 1/3, 1/3, 1/3)`, whose entropy `ln 3 = 1.099` is below
`H(2/3) + H(2/3) = 1.273`.  Twelve of the sixteen 4-grams have `m₄ ≠ 1`: the
corpus is trigram-Markov but not a genuine first-order Markov chain, and the
whole `Δ` is that 4-gram term.  So `Δ = 0` requires a *genuinely* first-order
Markov corpus (as the periodic regression corpora are), not merely `m ≡ 1`.

### A checkable sufficient condition for `Δ = 0`

The counterexample above was trigram-Markov but failed one 4-gram identity.
Adding that identity is enough.  Precisely, suppose that for every `a, b, c`

    N(a,b,c) · N(b) = N(a,b) · N(b,c)                      (trigram factors `m = 1`)

**and** that for every `a, b`

    N(a,b,a,b) · N(b,a) = N(a,b,a) · N(b,a,b)              (4-gram `(a,b,a,b)`, `m₄ = 1`)

Then `Δ = 0` for every merge.  Proof: fix the merge `uv`.  The first identity,
applied to `m(x,u,v)` and `m(u,v,y)`, makes the two conditional-entropy sums of
the entropy form vanish.  Applied to the two special trigrams it also pins the
marginals of the four-way table: `m(v,u,v) = 1` gives `A(v) = λ·N(v,u)` and
`m(u,v,u) = 1` gives `B(u) = μ·N(v,u)`.  The second identity, with
`(a,b) = (u,v)`, then gives `Q = λμ·N(v,u)`, so

    p = ( (1−λ)(1−μ), λ(1−μ), μ(1−λ), λμ ) = p₀ ,

the product baseline, and the last term is `0`.  Hence `Δ = 0`.  ∎

The two identities are on their face weaker than "first-order Markov at every
order" — only the `(a,b,a,b)` 4-grams are constrained, not all of them.  Whether
they *secretly* force every `m₄ = 1` is left open: every corpus we have tested
that satisfies them is also fully Markov, but that is no reason to expect it in
general (a counterexample, if one exists, is probably large).  In any case the
pair is exactly what the four-way term needs, and is what the regression test
below exercises.  Note the trigram identity is used **twice**: once to zero the
entropy sums and once to fix the marginals of `p`.

### Expanding in `m = e^E`: `Δ` is second order

Write `m(a,b,c) = e^{E(a,b,c)}` so that `E = 0` is first-order consistency.  The
aggregates become `A(x) = N(x,u)λ·e^{E(x,u,v)}` (with `λ = N(u,v)/N(u)`), and the
context sums satisfy, **exactly** (it is just `Σ_x N(x,u,v) = N(u,v)`),

    Σ_x N(x,u)·( m(x,u,v) − 1 ) = 0 ,    Σ_y N(v,y)·( m(u,v,y) − 1 ) = 0 .

Expanding the entropy form to first order in `E` — `H(λ(1+ε)) − H(λ) ≈
H′(λ)λ ε`, `H′(λ) = log((1−λ)/λ)` — the `x`- and `y`-sums combine with the
boundary terms and the sums *complete*: the `x = v` (the `A(v)`) and `y = u` (the
`B(u)`) contributions are exactly the missing terms of a full sum over contexts,
and `Q` drops out entirely:

    Δ ≈ −λ log(λ/(1−λ)) Σ_x N(x,u) E(x,u,v)
        − μ log(μ/(1−μ)) Σ_y N(v,y) E(u,v,y) ,      μ = N(u,v)/N(v) .

Both sums are themselves `O(E²)` (by the sum rule above), so this *linear* form
vanishes to leading order.  Working to `O((m−1)²)` instead, the sums close
up into a manifestly negative quadratic form:

    Δ ≈ −½ [ λ/(1−λ) Σ_{x≠v} N(x,u)·( m(x,u,v) − 1 )²
           + μ/(1−μ) Σ_{y≠u} N(v,y)·( m(u,v,y) − 1 )²
           + N(v,u)·χ² ] ,

where `χ² = Σ_i (p_i − p₀_i)² / p₀_i` is the Pearson `χ²` of the four-way table
`p` against its product baseline `p₀`.  Three consequences:

* **The linear term in `m − 1` cancels exactly**, just as `Δ⁽¹⁾` did; what is
  left is a term *quadratic* in `m − 1` **plus** the four-way term `N(v,u)·χ²`.
* At leading order **`Δ ≤ 0`**: every merge weakly decreases the corpus size.
  (Observed for all 36 000+ usable merges tested; the quadratic form shows why.)
* `Q` (the 4-gram) enters only through `χ²`, the four-way term.  Unlike the
  `(m−1)²` pieces this is **not** controlled by `m − 1` — it survives when
  `m ≡ 1` (see below), so it is a leading effect, not a second-order one.

The exact entropy form, the zero `Δ⁽¹⁾`, the `u = v` closed form, the latent sum
rule and the quadratic scaling are checked in `scripts/check_merge_delta.py`.

### Is `Δ` always negative?

`Δ < 0` for *every* merge would say that adding a word to the dictionary never
enlarges `CS`.  It holds to leading (second) order — the quadratic form above is
non-positive — and it holds exactly in every case we can enumerate; but it is
**not** a trivial consequence of "each score sum shrinks", and we have only a
partial proof of the all-orders statement.  Here is how far we get.

**Each sum really does shrink.**  One merge removes `M = N(u,v)` copies of `u`
and of `v` and creates `M` copies of `w`, so the unigram part is

    ΔS1 = L(U − M) − L(U) + L(V − M) − L(V) + L(M) .

Since `L(a − c) + L(c) − L(a) = −a·H(c/a) ≤ 0` (the binary entropy is
non-negative), each `u`/`v` piece is `≤ 0` and the whole thing is `≤ 0`.  The
same lemma, applied cell by cell, gives `ΔS2 ≤ 0`: a bigram cell that loses `c`
of its count contributes `L(a − c) − L(a) = −[L(a) − L(a − c)] ≤ −L(c) ≤ 0`, and
the new `(·, w)`, `(w, ·)`, `(w, w)` cells only repackage counts deleted
elsewhere.  So **both** `S1` and `S2` fall.

**Why that is not enough.**  `Δ = ΔS1 − ΔS2` is a difference of two *negative*
numbers, and the exact statement is `ΔS2 ≤ ΔS1` — the bigram sum must fall *at
least as much* as the unigram sum.  Neither `S1 ≥ S2` nor its reverse holds in
general.  In the form `CS = N·H` (with `H = H(next | word)`), putting
`N' = N − M` and writing `H'` for the merged conditional entropy, the claim is

    Δ ≤ 0   ⟺   N'·H' ≤ N·H .

The merge **deletes** `M` tokens (a gain proportional to `M`) while it **raises**
the conditional entropy per token (the merged transition table is less
predictable); `Δ ≤ 0` says the deletion always wins.  Both effects are visible
in an i.i.d. corpus: merging two of `k` symbols pushes `H` from `log k` toward
`log(k−1)`, yet the corpus still gets shorter.  Neither effect dominates by
inspection.

**What we can prove, and what we test.**  The doubled-word merge `u = v` is the
one case where the `m ≡ 1` part does not cancel, and it is the source of every
counterexample to the raw inequality.  Enumerating *every* cyclic corpus over
`≤ 4` symbols (all sizes with at most `20 000` sequences) and every merge pair
gives:

* `u ≠ v`: `0` positive `Δ` out of `447 384` merges, worst `0`;
* `u = v`, under the standing "no threefold repeat" assumption: `0` positive
  out of `102 306` merges;
* `u = v` *without* that assumption: `8 956` positives, and every one lies in a
  corpus containing a run `uuu` — e.g. `u^11` with `u = v` gives `Δ ≈ +26.4`.

A broad random scan (a few `10⁵` merges, all alphabet sizes `2…5`) adds no
counterexample.  So within the assumptions of this document `Δ ≤ 0` holds
exactly, and the only way to break it is precisely the run-length case that A2
removes.  An all-orders symbolic proof of the `u ≠ v` case is still open: the
leading-order quadratic form and the exact entropy form are the sharpest handles
we have found, and both fail to close term by term.  The sign is checked
exhaustively (and for the two sums separately) in
`scripts/check_merge_delta.py --exhaustive`.

Two remarks:

* The gain is **not** a pointwise-mutual-information term.  Merging a
  deterministic alternation `ab ab` changes `CS` by nothing, though its PMI is
  positive — the whole effect is already in the pair counts, and `CS` is an
  entropy, not a likelihood ratio.
* The greedy rule picks the pair with the largest `N(u,v)`.  That is a *proxy*
  for the smallest `Δ`; `Δ` also depends on how the pair is embedded (`A`, `B`,
  `Q`), so a "greedy by gain" variant would rank candidates by `Δ` instead
  (measured in `docs/DICTIONARY_RULES.md` §A3: the `Δ` rule wins on structured
  data but barely on real identifiers).

**Checked numerically.** `scripts/check_merge_delta.py` merges a pair by brute
force (recount, then recompute `CS`) and compares against the formula above, on
random cyclic corpora, for every pair (including `u = v`, and including corpora
that contain `uvuv` so that `Q > 0`).  It agrees to `1e−9` on ~22k cases.


# Relaxing the three-consecutive-repeats assumption

The standing assumption ("no `uuu`) is what the sign argument leans on: every
counterexample to `Δ ≤ 0` is a **doubled-word** merge, and every one of them sits
in a corpus that contains a run `uuu` (e.g. `u¹¹`, where merging `(u,u)` raises
`CS` by `Δ ≈ +26.4`).  It can be relaxed by changing *what the dictionary emits
for a repeated word*.

**The run-aware rule.**  As usual, find the most common length-2 substring `uv`.
If `u ≠ v`, merge it.  If `u = v` — the doubled case, the only place the
assumption is needed — do **not** merge two copies.  Instead, collapse *every*
maximal run `uᵏ` (`k ≥ 2`) present in the corpus to a single flat word `(uᵏ)`,
**one word per observed run length** `k`.  (This is the "word-level
run-length-encoding step" sketched in the notes below, now made concrete: the
run token is the flat word `(uᵏ)`, not a nested `((uu)u)…`.)  After the step no
two adjacent `u` tokens remain, so the doubled pair `(u,u)` cannot recur.

Two things make the sign work again:

* **Distinct pairs are unaffected.**  For `u ≠ v` two occurrences of `uv` can
  never overlap (a shared token would have to be both `u` and `v`), even on the
  cycle — so "replace every occurrence" stays unambiguous and the earlier
  `Δ ≤ 0` result for `u ≠ v` applies verbatim, straddling matches included.
* **The run collapse never enlarges `CS`.**  Replacing a maximal run `uᵏ` by one
  token deletes `k − 1` tokens and merges their bigrams into the `(uᵏ)`-edges; in
  the degenerate all-`u` string both before and after have `CS = 0`, and
  otherwise the deleted `(u,u)` self-loop and the new boundary bigrams exactly
  rebalance.

**Verified.**  `scripts/check_merge_delta.py` (`check_run_aware`) enumerates small
cyclic corpora, applies up to four run-aware steps to each, and checks the sign
of every step's `Δ`:

* `0` positive `Δ` out of `41 167` steps (run steps `19 839`, pair steps
  `21 328`), worst `0`.

A heavier cross-check (all corpora over `≤ 3` symbols up to length `12`, up to
`40` steps each — `118 597` corpora; and `4 000` random run-heavy corpora, up to
`60` steps each) also finds `0` positives, and confirms the invariant "no two
adjacent `u` tokens after collapsing runs of `u`" every time.  So under the
run-aware rule `Δ ≤ 0` holds exactly on everything we can enumerate, and the
`uuu` pathology is gone.

What remains is the *choice* between the flat run word `(uᵏ)` and the ordinary
bigram `(uv)` when a run abuts a different word — e.g. `uuuuv` as `(u⁴)v` versus
`uuu(uv)`.  The run-aware rule is one consistent end of that spectrum;
`docs/DICTIONARY_RULES.md` §A4 measures the crossover (a single run word wins
iff `(k−1)·#runs(k) > N(u,v)`).

# Notes

*Explanatory notes added 2026-10-29. The sections above are the specification and
the merge-delta derivation; this is commentary on why they work, what is assumed,
and what is deliberately left out.*

## Why the three-consecutive-repeats assumption is there

It exists to make "replace **every** occurrence of `uv`" well-defined, i.e. to
guarantee that occurrences of the pair `uv` never **overlap**. Two occurrences of
`uv` can only overlap if `u = v` (the shared word would have to be both `v` and
`u`), and overlapping them needs the token `uuu` — three consecutive repeats of
`u`. So the assumption rules out exactly the ambiguous case.

It is also **preserved** by the merge step: a merge cannot create three
consecutive repeats of a substring `W` unless the original string already
contained `WWW`, and the assumption forbids that. So it need only be checked
once, on the input corpus.

Consequence: under the assumption, "occurrences of `uv`" is unambiguously the
same as "non-overlapping occurrences of `uv`", so `N(u,v)` and the identity
below are well-defined with no extra matching convention.

(If it is ever relaxed — see "Relaxing the three-consecutive-repeats
assumption" above — the plan is a word-level run-length-encoding step: when the
chosen pair is a doubled word `(u,u)`, collapse every maximal run `uᵏ` to the
flat word `(uᵏ)` instead of merging two copies, so *no two adjacent `u` tokens
exist afterwards* and overlap (which needs `uuu`) cannot occur.  That section
carries out exactly this, and shows `Δ ≤ 0` survives.  An alternative is to
define the merge as "replace a maximal set of leftmost non-overlapping
occurrences"; that also works for any corpus but makes `N(u,v)`
convention-dependent.  How run tokens such as `(uᵏ)` enter the adjacency matrix
— one symbol, the bigrams of their expansion, or a weighted edge — is a genuine
choice with several reasonable answers, and is out of scope for now.)

## Tie-breaking

"Most common length-2 substring" needs a deterministic rule when counts tie (in
particular a canonical order over the words, or "lowest pair in creation order").
Not yet specified.

## Tokenisation is trivially decodable

A sequence of words decodes to the original string simply by **removing the
brackets**: every word expands to a unique string of characters, so no side
information beyond the wordlist is needed. Note that this holds *regardless* of
the three-repeats assumption — even an "ambiguous" tokenisation such as `(aa)a`
versus `a(aa)` decodes to `aaa` either way. So the assumption protects the
*counts*, not the *code*.

## The score identity

The identity `CS = S1 - S2` is worth proving, because the derivation pins down
what it depends on.  Per string,

    -log2 P(u_0 ... u_n) = -sum_i log2 P(u_{i+1} | u_i)
                         = sum_i log2 [ N(u_i) / N(u_i, u_{i+1}) ] .

Summing over the corpus, each bigram `(u,v)` appearing `N(u,v)` times,

    CS = sum_{u,v} N(u,v) log2 [ N(u) / N(u,v) ]
       = sum_{u,v} N(u,v) log2 N(u)  -  sum_{u,v} N(u,v) log2 N(u,v) ,

and the first term collapses because `sum_v N(u,v) = N(u)` for every `u`,
giving

    CS = sum_u N(u) log2 N(u)  -  sum_{u,v} N(u,v) log2 N(u,v)  =  S1 - S2 .   ✓

Two consequences:

* `CS = N . H(next | word)`, since `N = sum_u N(u) = sum_{u,v} N(u,v)` and
  `CS/N = -sum_{u,v} P(u,v) log2 P(v | u)`. So the score is just *total tokens
  times conditional entropy per token*, and `CS / N(\n)` is the natural
  **average bits per string** (per identifier).
* The collapse uses `sum_v N(u,v) = N(u)` for **every** `u`, including `\n`.
  That holds only because every token has exactly one successor in a cycle — so
  "bend into a cycle" (and `u_0 = u_{n+1} = \n`) is load-bearing, not cosmetic:
  with linear strings `\n` would have no successor, `sum_v N(\n,v) = 0`, and the
  identity would fail.

**Caveat for later.** This closed form holds for the **MLE** model,
`P(v | u) = N(u,v) / N(u)`. The moment a prior / pseudo-count correction is
added (the unobserved-pairs counting fix), `P` is no longer the empirical ratio
and `CS` becomes a genuine cross-entropy — i.e. the joint KL already used
elsewhere. Under the present "enormous corpus" assumption this is moot.

## Model size: no MDL here

`CS` deliberately excludes the cost of the dictionary and the code table, so on
its own it is gameable (a corpus that is `M` copies of one string scores 0 bits
if that string is a single word). That is not a defect to fix *here*: following
`CLUSTER_SIZE_STUDY.md`, the model is built once and reused, so its byte size is
a **resource we choose to spend**, not a cost to amortise, and the question is a
pure Pareto one — *smallest score at a given model size*. In this document the
size knob is `NUM_PAIRS` (the dictionary) and the score should be the
**held-out** code length (bits/string) rather than in-sample `CS`; plot
held-out bits/string against dictionary bytes and keep the frontier.
