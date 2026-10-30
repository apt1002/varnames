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
  determine.  In a perfectly first-order (bigram-Markov) corpus `Δ = 0`: no merge
  changes the description length.
* The four-count dependence means the greedy "most frequent pair" rule, which
  sees only bigrams, is a proxy for greedy-by-`Δ` only up to the `m`'s.

### The doubled-word merge is the exception

For `u = v = z` one merge consumes *two* copies of `z`, and `Δ⁽¹⁾` does **not**
vanish.  It still collapses, now to a function of the two counts
`N(z), N(z,z)` alone:

    Δ⁽¹⁾ = L(N(z) − 2N(z,z)) − L(N(z)) + 2L(N(z,z))
           − 2(N(z) − N(z,z)) · h( N(z,z)/N(z) ) .

### The `m − 1` part

Since `Δ = Δ⁽ᵐ⁾`, the whole effect is the higher-order term.  To first order,
`L(n+δ) − L(n) ≈ (1 + ln n)·δ`, so `Δ⁽ᵐ⁾` is *linear* in `m − 1`, each
perturbed count `n` contributing a weight `1 + ln n`, with the sign read off
`ΔS2`.  The exact statement: the merge's effect on the description length is a
weighted sum of the trigram (and one 4-gram) dependence factors `m − 1`, whose
weights are `1 + ln(count)`.

The identity `Δ⁽¹⁾ = 0` (and the `u = v` closed form) is checked in
`scripts/check_merge_delta.py`.

Two remarks:

* The gain is **not** a pointwise-mutual-information term.  Merging a
  deterministic alternation `ab ab` changes `CS` by nothing, though its PMI is
  positive — the whole effect is already in the pair counts, and `CS` is an
  entropy, not a likelihood ratio.
* The greedy rule picks the pair with the largest `N(u,v)`.  That is a *proxy*
  for the smallest `Δ`; `Δ` also depends on how the pair is embedded (`A`, `B`,
  `Q`), so a "greedy by gain" variant would rank candidates by `Δ` instead.

**Checked numerically.** `scripts/check_merge_delta.py` merges a pair by brute
force (recount, then recompute `CS`) and compares against the formula above, on
random cyclic corpora, for every pair (including `u = v`, and including corpora
that contain `uvuv` so that `Q > 0`).  It agrees to `1e−9` on ~22k cases.


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

(If it is ever relaxed — the deferred work — the plan is a word-level
run-length-encoding step before each search-and-replace: it collapses any run of
identical adjacent words, so *no two adjacent identical words exist at the
moment `uv` is chosen*, and overlap (which needs `uuu`) cannot occur. E.g.
`ababab` is untouched by the first RLE (all neighbours distinct), then merged to
`(ab)(ab)(ab)`, then RLE'd to `(ab)³`. An alternative is simply to define the
merge as "replace a maximal set of leftmost non-overlapping occurrences"; that
also works for any corpus but makes `N(u,v)` convention-dependent. How run
tokens such as `(ab)³` enter the adjacency matrix — one symbol, the bigrams of
their expansion, or a weighted edge — is a genuine choice with several reasonable
answers, and is out of scope for now.)

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
