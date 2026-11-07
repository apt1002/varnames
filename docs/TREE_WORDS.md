# The dictionary (pair-merge) model

This document defines a word-level model of a corpus of strings (in practice,
programming-language identifiers) and derives the effect of enlarging its
dictionary by one word.  It is written as a specification followed by a
derivation; §11 collects the remarks that are useful but not needed to follow
the argument.

## 1. The corpus

A corpus is a multiset of strings (identifiers).  Append a stop character `\n`
to each string and **bend it into a cycle**, so that every character has a
successor — including the `\n`.  From here on a string means this cyclic
sequence, and it contains exactly one `\n`.

Two assumptions are in force for §§2–8 and lifted in §9:

* `\n` does not appear inside a string;
* no three consecutive repeats of any substring occur (`uuu`).

The cycle is load-bearing, not cosmetic: it is what makes `Σ_v N(u,v) = N(u)`
hold for *every* `u`, including `\n`, on which the score identity of §4 rests
(§10).

## 2. The dictionary

Words start as the single characters plus `\n`; the wordlist starts empty.

Repeat `NUM_PAIRS` times:

1. find the most common length-2 substring `uv` in the corpus, where `u` and
   `v` are *words*;
2. append `(uv)` to the wordlist;
3. replace every occurrence of `uv` by `(uv)` (other occurrences of `u` and `v`
   are untouched).

An occurrence of `(uv)` is **not** an occurrence of `u` — counts never look
inside brackets.  Building the dictionary turns the corpus from a multiset of
strings into a multiset of *tokenised* strings: strings of words.

## 3. Tokenising an unseen string

Append `\n`, bend into a cycle, and replay the wordlist in creation order: for
each `uv`, replace every occurrence.  A newly created pair always has a higher
rank than the rule that built it, so this is the same as repeatedly merging the
lowest-ranked adjacent pair.

## 4. The score

Write `N` for the number of words in the tokenised corpus, `N(u)` for the
occurrences of the word `u`, and `N(u,v)` for the occurrences of the bigram
`uv`.  Then `N(\n)` is the number of strings and `P(v | u) = N(u,v) / N(u)`.

The model assigns a tokenised string `u₀ u₁ … u_n` (with `u₀ = u_{n+1} = \n`)
the probability of its length-2 substrings,

    P(u₀ … u_n) = ∏_{i=0}^{n} P(u_{i+1} | u_i) ,

and the compressed size of a string is `−log₂` of its probability.  The **corpus
size** `CS` is the total compressed size. An equivalent definition of `CS` is

    CS = S1 − S2 ,   S1 = Σ_u L(N(u)) ,   S2 = Σ_{u,v} L(N(u,v)) .

With `L(z) = z·log₂ z` (`L(0) = 0`). This identity is proved in §10.
Two immediate readings: `CS = N·H(next | word)` (total tokens times conditional
entropy per token), and `CS / N(\n)` is the average bits per string.  Smaller
`CS` is better.

## 5. The effect of one merge

One increment merges a pair of words `u`, `v` into a new word `w`.  Every
occurrence of `uv` sits in a context `x u v y`, with `x` the predecessor and `y`
the successor.  The only aggregates that matter are

    A(x) = N(x, u, v)     occurrences of uv with predecessor x   (Σ_x A = N(u,v))
    B(y) = N(u, v, y)     occurrences of uv with successor   y   (Σ_y B = N(u,v))
    Q    = N(u, v, u, v)  adjacent uvuv patterns.

`Q` is the awkward piece: two *adjacent* occurrences of `uv` (the pattern
`uvuv`) merge into the single bigram `ww`, so `Q` is a 4-gram count.  Under the
"no `uuu`" assumption each `uvuv` is isolated, and if it is ignored (`Q = 0`)
only 3-gram counts survive.

With `Δ = CS' − CS` (a merge that improves compression has `Δ < 0`),

    Δ = ΔS1 − ΔS2

    ΔS1 = L(N(u)−N(u,v)) − L(N(u))  +  L(N(v)−N(u,v)) − L(N(v))  +  L(N(u,v))

    ΔS2 =  −L(N(u,v))                                        (u,v)  -> gone
        + Σ_{x≠v} [ L(N(x,u) − A(x)) − L(N(x,u)) ]           (x,u)  decremented
        +       [ L(N(v,u) − A(v) − B(u) + Q) − L(N(v,u)) ]  (v,u)  both decrements
        + Σ_{y≠u} [ L(N(v,y) − B(y)) − L(N(v,y)) ]           (v,y)  decremented
        + Σ_{a≠v} L(A(a))                                    (a,w)  created
        +       L(A(v) − Q)                                  (v,w)
        +       L(B(u) − Q)                                  (w,u)
        + Σ_{b≠u} L(B(b))                                    (w,b)  created
        +       L(Q)                                         (w,w)  created

The `Σ` is over the current vocabulary; `w` is new, so it never appears in the
"decremented" sums.  Reading the lines: the pair `(u,v)` disappears
(`−L(N(u,v))`); each `(x,u)` whose `u` is consumed loses `A(x)`, symmetrically
`(v,y)` loses `B(y)`; each `w` token creates the new bigrams `(a,w)`, `(w,b)`.
The `(v,u)` line is the only place the two decrements collide — a `(v,u)` bigram
dies both because its `u` is matched (`A(v)`) and because its `v` is matched
(`B(u)`), and the doubly-counted pattern is exactly `uvuv`, hence `+Q`.  The
same `uvuv` patterns create the `(w,w)` bigram, so mass moves from `(v,w)` and
`(w,u)` into `(w,w)` (the paired `−Q` and the final `+L(Q)`).

**The doubled word `u = v = z`** (allowed — only `uuu` is forbidden) consumes
*two* copies of `z` per merge, and the assumption forces
`Q = A(z) = B(z) = 0`:

    ΔS1 = L(N(z)−2N(z,z)) − L(N(z)) + L(N(z,z))

    ΔS2 =  −L(N(z,z))                                  (z,z)  -> gone
        + Σ_{x≠z} [ L(N(x,z) − A(x)) − L(N(x,z)) ]     (x,z)
        + Σ_{y≠z} [ L(N(z,y) − B(y)) − L(N(z,y)) ]     (z,y)
        + Σ_{a≠z} L(A(a)) + Σ_{b≠z} L(B(b))            (a,w), (w,b)

(no `(w,w)` term: a `ww` would need `uuuu`).

Incrementing `NUM_PAIRS` by `K` costs the sum of `Δ` over the `K` successive
merges.

## 6. The trigram factor `m`, and the `NUM_PAIRS`-only part `Δ⁽¹⁾`

Define the **trigram factor**

    m(a,b,c) = N(a,b,c) · N(b) / ( N(a,b) · N(b,c) ) ,

so that `N(a,b,c) = m(a,b,c) · N(a,b) · N(b,c) / N(b)`.  `m ≡ 1` says the
trigram is fixed by the pair counts — that the next word depends on the previous
one but not on the one before it.  The aggregates become pure functions of the
bigram counts and the `m`'s:

    A(x) = m(x,u,v) · N(x,u) N(u,v) / N(u)
    B(y) = m(u,v,y) · N(u,v) N(v,y) / N(v)
    A(v) = m(v,u,v) · N(v,u) N(u,v) / N(u)
    B(u) = m(u,v,u) · N(u,v) N(v,u) / N(v)

and `Q` needs the 4-gram analogue of the same construction,
`m(a,b,c,d) = N(a,b,c,d) N(b,c) / ( N(a,b,c) N(b,c,d) )` with middle pair
`(b,c) = (v,u)` — note the normaliser is `N(v,u)`, not `N(u,v)`:

    Q = m(u,v,u,v) · B(u) · A(v) / N(v,u) .

Substituting the `m`'s splits `Δ = Δ⁽¹⁾ + Δ⁽ᵐ⁾` into a bigram-only piece and a
higher-order piece:

* `Δ⁽¹⁾` is `Δ` with every `m ≡ 1`:

      A₁(x) = N(x,u) N(u,v)/N(u)      B₁(y) = N(u,v) N(v,y)/N(v)
      A₁(v) = N(v,u) N(u,v)/N(u)      B₁(u) = N(u,v) N(v,u)/N(v)
      Q₁    = N(v,u) N(u,v)² / ( N(u) N(v) ) ;

* `Δ⁽ᵐ⁾ = Δ − Δ⁽¹⁾` carries all the `m − 1` and `m(u,v,u,v) − 1` dependence and
  vanishes identically when the corpus is first-order consistent.

### 6.1 `Δ⁽¹⁾` vanishes for a distinct-pair merge

For `u ≠ v`, `Δ⁽¹⁾` is **identically zero**.  Put `λ = N(u,v)/N(u)`, so
`A₁(x) = λ·N(x,u)`.  At each predecessor `x ≠ v` the three `ΔS2` contributions
collapse,

    −L(N(x,u)) + L(N(x,u) − A₁(x)) + L(A₁(x))
      = −L(N(x,u)) + L(N(x,u)(1−λ)) + L(N(x,u)λ)
      = N(x,u) · h(λ) ,   h(λ) = (1−λ) log(1−λ) + λ log λ ,

because `log N(x,u)` cancels exactly.  So the whole `x`-sum depends only on
`Σ_{x≠v} N(x,u) = N(u) − N(v,u)`, and likewise the `y`-sum on `N(v) − N(v,u)`:

    Σ_{x≠v}[…] = (N(u) − N(v,u)) · h(λ) ,   Σ_{y≠u}[…] = (N(v) − N(v,u)) · h(μ) ,   μ = N(u,v)/N(v) .

The boundary terms (`−L(N(u,v))`, the new `(v,w)`, `(w,u)`, `(w,w)` bigrams,
and the gap `(v,u)`) together with `ΔS1` are a two-line expansion of `L` in the
four counts `N(u), N(v), N(u,v), N(v,u)` (carried out symbolically in the
regression test), and `ΔS1 − ΔS2 = 0` there.

**Consequences.**  `Δ = Δ⁽ᵐ⁾` *exactly*: a merge changes the corpus size only
through the part of the trigram (and 4-gram) statistics the bigram table does
not already determine.  A corpus that is **genuinely first-order Markov** — no
trigram *and* no 4-gram dependence — has `Δ = 0` for every merge.  Trigram
consistency *alone* (`m ≡ 1`) is not enough; see §7.

### 6.2 The doubled word is the exception

For `u = v = z`, `Δ⁽¹⁾` survives, collapsing to a function of the two counts
`N(z), N(z,z)` alone:

    Δ⁽¹⁾ = L(N(z) − 2N(z,z)) − L(N(z)) + 2L(N(z,z))
           − 2(N(z) − N(z,z)) · h( N(z,z)/N(z) ) .

## 7. The entropy form, and what survives at `m ≡ 1`

Since `Δ = Δ⁽ᵐ⁾`, substitute the `m`'s and cancel.  Each pair
`L(N(x,u)−A(x)) + L(A(x))` collapses: with `q_x = N(x,u,v)/N(x,u)` and the
binary entropy `H(q) = −q log q − (1−q) log(1−q)`,

    L(N(x,u) − A(x)) + L(A(x)) = N(x,u) · [ log N(x,u) + H(q_x) ] ,

so `log N(x,u)` cancels against `−L(N(x,u))` in `ΔS2`.  The `x`-sum therefore
carries only entropies, and likewise the `y`-sum, leaving the exact identity

    Δ =  Σ_{x≠v} N(x,u)[ H(P(v|x,u)) − H(P(v|u)) ]
       + Σ_{y≠u} N(v,y)[ H(P(u|v,y)) − H(P(u|v)) ]
       − N(v,u)[ H(P(v|u)) + H(P(u|v)) − H(p) ] ,

where `P(v|x,u) = N(x,u,v)/N(x,u)`, `P(v|u) = N(u,v)/N(u)`, and `p` is the
four-way distribution over the `(v,u)` bigram split by
(predecessor is `v`) × (successor is `u`); its product baseline
`P(v|u) ⊗ P(u|v)` has entropy `H(P(v|u)) + H(P(u|v))`.  So a merge's effect is
(minus) the drop in the conditional entropy of the next word over the consumed
contexts, less a four-way dependence term.

At `m ≡ 1` the first two sums vanish, leaving only `Δ = −N(v,u)[H(λ)+H(μ)−H(p)]`.
That is zero only when `p` is its product baseline, i.e. when there is no
**4-gram** dependence around the merged bigram.  Trigram consistency does not
imply this.  For example, the three strings

    "01",  "01",  "00111010100011"

(each `\n`-appended and bent into a cycle) have `N(0,1) = 6`, `N(a,b) = 3` for
the five other observed bigrams, and every one of the thirteen trigram factors
`m` exactly `1`, yet merging `01` **reduces** `CS` by `0.523` nats (`0.755`
bits).  Twelve of the sixteen 4-grams have `m₄ ≠ 1`: the corpus is trigram-Markov
but not a genuine first-order Markov chain, and the whole `Δ` is the 4-gram
term.

### 7.1 A checkable sufficient condition for `Δ = 0`

Suppose that for every `a, b, c`

    N(a,b,c) · N(b) = N(a,b) · N(b,c)                       (trigram `m = 1`)

**and** that for every `a, b`

    N(a,b,a,b) · N(b,a) = N(a,b,a) · N(b,a,b)               (4-gram `(a,b,a,b)`, `m₄ = 1`).

Then `Δ = 0` for every merge.  Fix the merge `uv`.  The trigram identity, applied
to `m(x,u,v)` and `m(u,v,y)`, zeros the two entropy sums; applied to the two
special trigrams it also pins the marginals of the four-way table,
`m(v,u,v) = 1` giving `A(v) = λ·N(v,u)` and `m(u,v,u) = 1` giving
`B(u) = μ·N(v,u)`.  The 4-gram identity with `(a,b) = (u,v)` then gives
`Q = λμ·N(v,u)`, so

    p = ( (1−λ)(1−μ), λ(1−μ), μ(1−λ), λμ ) = p₀ ,

the product baseline, and the last term is `0`.  Hence `Δ = 0`.  Note the
trigram identity is used **twice**.  The pair of identities is on its face weaker
than "Markov at every order" — only the `(a,b,a,b)` 4-grams are constrained —
and whether it secretly forces every `m₄ = 1` is left open.

## 8. Second-order expansion, and the sign of `Δ`

Write `m(a,b,c) = 1 + ε(a,b,c)`.  Since `Σ_x N(x,u,v) = N(u,v)` exactly, the
context sums obey the **sum rule**

    Σ_x N(x,u)·ε(x,u,v) = 0 ,    Σ_y N(v,y)·ε(u,v,y) = 0 .

Expanding the entropy form to first order in `ε`, the `x`- and `y`-sums combine
with the boundary terms and *complete* — the `x=v` and `y=u` contributions are
exactly the missing terms of a full context sum, and `Q` drops out:

    Δ ≈ −λ log(λ/(1−λ)) Σ_x N(x,u) ε(x,u,v)
        − μ log(μ/(1−μ)) Σ_y N(v,y) ε(u,v,y) .

Both sums are themselves `O(ε²)` by the sum rule, so this *linear* form vanishes
to leading order.  Working to `O(ε²)`, the sums close into a manifestly negative
quadratic form:

    Δ ≈ −½ [ λ/(1−λ) Σ_{x≠v} N(x,u)·ε(x,u,v)²
           + μ/(1−μ) Σ_{y≠u} N(v,y)·ε(u,v,y)²
           + N(v,u)·χ² ] ,

with `χ² = Σ_i (p_i − p₀_i)² / p₀_i` the Pearson `χ²` of the four-way table
against its product baseline.  So:

* the linear term in `ε` cancels exactly (as `Δ⁽¹⁾` did), leaving a term
  quadratic in `ε` **plus** the four-way term `N(v,u)·χ²`;
* at leading order **`Δ ≤ 0`**;
* `Q` enters only through `χ²`, and unlike the `ε²` pieces this is **not**
  controlled by `ε` — it survives at `ε = 0`, so it is a *leading* effect.

## 9. Is `Δ` always negative?

`Δ < 0` for every merge would say that adding a word never enlarges `CS`.  It
holds to leading order (§8), for every distinct-pair merge **exactly**, and in
every case we can enumerate.  Only the *doubled-word* merge (`u = v`) is not
covered by the proof below; the run-aware rule of §9.1 never performs it.

**Both sums fall.**  One merge removes `M = N(u,v)` copies of `u` and of `v` and
creates `M` copies of `w`, so

    ΔS1 = L(U − M) − L(U) + L(V − M) − L(V) + L(M) .

Because `L(a − c) + L(c) − L(a) = −a·H(c/a) ≤ 0`, each `u`/`v` piece is `≤ 0`
and `ΔS1 ≤ 0`.  The same lemma cell by cell gives `ΔS2 ≤ 0`.  So both `S1` and
`S2` fall.

**But that is not enough.**  `Δ = ΔS1 − ΔS2` is a difference of two *negative*
numbers; the exact claim is `ΔS2 ≤ ΔS1`.  In the form `CS = N·H` with
`N' = N − M`, it reads `Δ ≤ 0 ⟺ N'·H' ≤ N·H`: the merge deletes `M` tokens but
raises the per-token conditional entropy, and `Δ ≤ 0` says the deletion always
wins.

### 9.0 A proof for the distinct-pair merge (`u ≠ v`)

Take `u ≠ v` — the only kind of pair step the run-aware rule performs.  Write

    R = N(v,u),   a = N(v,u,v),   b = N(u,v,u),   α = a/R,   β = b/R ,

and let `p` be the four-way distribution of §7 over the `R` occurrences of the
bigram `(v,u)`, split by *(the `v` is preceded by `u`)* and *(the `u` is followed
by `v`)*.  Its two marginals are exactly `β` and `α`: the first event is the
trigram `u v u`, counted `b` times, and the second is `v u v`, counted `a` times.

Start from the exact entropy form of §7,

    Δ = Σ_{x≠v} N(x,u)[H(q_x) − H(λ)] + Σ_{y≠u} N(v,y)[H(r_y) − H(μ)]
        − R[H(λ) + H(μ) − H(p)] ,

with `q_x = P(v|x,u)`, `r_y = P(u|v,y)`.

*Jensen, `u`-side.*  The weights `N(x,u)` sum to `N(u)` and the `q_x` have
weighted mean `Σ_x N(x,u) q_x / N(u) = N(u,v)/N(u) = λ`; since `H` is concave,

    Σ_x N(x,u) H(q_x) ≤ N(u) H(λ) .

The `x = v` term is `R·H(α)`, so isolating it bounds the first sum,

    Σ_{x≠v} N(x,u)[H(q_x) − H(λ)] ≤ R[H(λ) − H(α)] .

*Jensen, `v`-side.*  Symmetrically the weights `N(v,y)` sum to `N(v)`, the
`r_y` have mean `μ`, and the `y = u` term is `R·H(β)`:

    Σ_{y≠u} N(v,y)[H(r_y) − H(μ)] ≤ R[H(μ) − H(β)] .

Substituting both bounds, `H(λ)` and `H(μ)` cancel and

    Δ ≤ R[H(p) − H(α) − H(β)] .

Finally `α` and `β` are the marginals of the joint `p`, so `H(p) ≤ H(α) + H(β)`
(subadditivity).  Hence **`Δ ≤ 0`**.  ∎

(If `R = 0` — the two words are never adjacent in the order `v u` — the four-way
term is absent and the same two Jensen inequalities give `Δ ≤ 0` directly: the
weights `N(x,u)` then already sum to `N(u)`, so each context sum is `≤ 0`.)

The proof *derives* the sufficient condition of §7.1 rather than assuming it:
equality needs both Jensen steps tight (`q_x = λ` for every `x` with
`N(x,u) > 0`, and `r_y = μ` for every `y` with `N(v,y) > 0` — the trigram
conditions `m(x,u,v) = m(u,v,y) = 1`) **and** `H(p) = H(α) + H(β)`, i.e. the two
events independent, which is the `(a,b,a,b)` 4-gram identity.  The key point is
that the `α`/`β` that enter the Jensen corrections are exactly the marginals of
`p`, so the three terms collapse to `H(p) − H(α) − H(β)`.

**What is proved, and what is tested.**  The theorem of §9.0 covers every
`u ≠ v` merge; the exhaustive and random checks below confirm it (and are the
regression test for the algebra — the checkable Jensen bound of §9.0,
`Δ ≤ R[H(p) − H(α) − H(β)] ≤ 0`, holds with no violation over 126 578 random
merges).  Only the doubled word remains outside the proof.  Enumerating every
cyclic corpus over `≤ 4` symbols (all sizes up to `20 000` sequences) with every
merge pair:

* `u ≠ v`: `0` positive `Δ` out of `447 384` merges;
* `u = v`, under "no `uuu`": `0` positive out of `102 306` merges;
* `u = v` *without* that assumption: `8 956` positives, **every one** in a corpus
  containing a run `uuu` (e.g. `u¹¹` with `u = v` gives `Δ ≈ +26.4`).

A broad random scan adds no counterexample.  So within the assumptions of this
document `Δ ≤ 0` holds exactly, and the only way to break it is precisely the
run-length case, which the next subsection removes.

### 9.1 Relaxing "no `uuu`": the run-aware rule

The standing assumption is needed only for the doubled-word merge.  Replace it
by a rule that never performs one:

**Run-aware rule.**  As usual find the most common pair `uv`.  If `u ≠ v`,
merge it.  If `u = v`, do **not** merge two copies; instead collapse every
maximal run `uᵏ` (`k ≥ 2`) to a single flat word `(uᵏ)`, **one word per observed
run length** `k`.  After the step no two adjacent `u` tokens remain.

Two facts make the sign survive:

* **Distinct pairs are unaffected.**  For `u ≠ v` two occurrences of `uv` can
  never overlap (a shared token would have to be both `u` and `v`), even on the
  cycle, so "replace every occurrence" stays unambiguous and the `u ≠ v` result
  of §9 applies verbatim.
* **A run collapse never enlarges `CS`.**  See the proof below.

**Proof for a run collapse.**  Consider a cyclic corpus with at least one non-`u`
token; the maximal runs of `u` have lengths `k_1, …, k_m` (`k_j ≥ 1`), run `j`
having left neighbour `p_j` and right neighbour `q_j` (both `≠ u`).  A run of
length `1` stays `u`; a run of length `k ≥ 2` becomes one fresh token `(uᵏ)`.
Write `N(u) = Σ_j k_j`, `c_k = #{j : k_j = k}`, `n_p = #{j : p_j = p}`,
`a_{p,k} = #{j : p_j = p, k_j = k}` and the right-side analogues `n^q, b_{q,k}`.

Only counts local to the runs change.  The unigrams give

    ΔS1 = Σ_{k≥1} L(c_k) − L(N(u)) ,

and the `N(u) − m` internal `(u,u)` bigrams vanish while each boundary bigram
`(p_j,u)` / `(u,q_j)` is relabelled by its run length:

    ΔS2 = Σ_{p,k} L(a_{p,k}) − Σ_p L(n_p) + Σ_{q,k} L(b_{q,k}) − Σ_q L(n^q) − L(N(u) − m) .

Each boundary double sum is a superadditivity gap: because `Σ_k a_{p,k} = n_p`,

    Σ_{p,k} L(a_{p,k}) − Σ_p L(n_p) = −Σ_p n_p H(k | p) = −m H(k | P) ,

with `P` the left-neighbour label — the *conditional entropy of the run length
given the context*.  The right sum is `−m H(k | Q)`.  Conditioning cannot raise
entropy, so `H(k|P), H(k|Q) ≤ H(k)`, where `H(k)` is the entropy of the
run-length distribution `c_k/m`.  Therefore

    ΔS2 ≥ −2m H(k) − L(N(u) − m)  =: ΔS2ᶠʳᵉᵉ ,

and

    Δ ≤ ΔS1 − ΔS2ᶠʳᵉᵉ = m [ H(k) − λ·H_b(1/λ) ] ,   λ = N(u)/m = E[K] .

Finally `H(K) ≤ λ·H_b(1/λ)` for **every** positive-integer run length `K` of mean
`λ`: the right-hand side is exactly the entropy of the geometric law of mean
`λ`, which maximises the entropy of a positive-integer variable at fixed mean.
Hence `Δ ≤ 0`.  ∎

Equality (`Δ = 0`) needs both `H(k|P) = H(k|Q) = H(k)` (run length independent of
its neighbours) **and** `K` geometric.  This is exactly what a first-order Markov
(i.i.d.-run) corpus gives, so `Δ = 0` there, as expected; real corpora satisfy
neither, so a run collapse is strictly improving.  (The degenerate corpus that is
a single run of `u` has `CS = 0` before and after, hence `Δ = 0` too.)

**Verified.**  Enumerating small cyclic corpora and applying up to four
run-aware steps to each: `0` positive `Δ` out of `41 167` steps (run steps
`19 839`, pair steps `21 328`).  A heavier cross-check (all corpora over `≤ 3`
symbols up to length `12`, up to `40` steps each — `118 597` corpora — and
`4 000` random run-heavy corpora up to `60` steps each) also finds `0`
positives, and confirms "no two adjacent `u` tokens after collapsing runs of
`u`" every time.  The remaining choice — run word `(uᵏ)` versus boundary `(uv)`
— is measured in `docs/DICTIONARY_RULES.md`.

All of §9 is checked in `scripts/check_merge_delta.py` (`--exhaustive`,
`check_sufficient_condition`, `check_run_aware`, the `check_delta_bound` Jensen
bound of §9.0 and the `check_run_collapse_bound` bound of §9.1).

> **The run machinery turned out to be unnecessary in production.**  On the
> real corpus, forbidding self-merges outright (no `(uu)`, no `(uᵏ)`) leaves the
> held-out numbers unchanged at the vocabularies used — mean bits identical to
> two decimals and the 64-bit fit within 3 identifiers of 229,534 at `V = 2,104`
> and `4,478` — and *improves* them at `V = 576`.  (Pre-expansion corpus and
> legacy vocabularies: the canonical grid is `V = 4,096`–`8,192` and runs the
> no-run rule only, so this is a record rather than a live comparison.)  So the dictionary is now plain
> pair-merge with self-merges forbidden, and the k-ary run node of §9.1 survives
> only as the theory that justified checking it.  Measurement:
> [`DICTIONARY_RULES.md`](DICTIONARY_RULES.md).

## 10. Why the cycle, and why `CS = S1 − S2`

Per string,

    −log₂ P(u₀ … u_n) = −Σ_i log₂ P(u_{i+1} | u_i) = Σ_i log₂ [ N(u_i) / N(u_i, u_{i+1}) ] .

Summing over the corpus, each bigram `(u,v)` appears `N(u,v)` times,

    CS = Σ_{u,v} N(u,v) log₂ [ N(u)/N(u,v) ]
       = Σ_{u,v} N(u,v) log₂ N(u) − Σ_{u,v} N(u,v) log₂ N(u,v) .

The first term collapses because `Σ_v N(u,v) = N(u)` for every `u`, giving
`CS = Σ_u N(u) log₂ N(u) − Σ_{u,v} N(u,v) log₂ N(u,v) = S1 − S2`.

The collapse needs `Σ_v N(u,v) = N(u)` for **every** `u`, including `\n` — which
holds only because each token has exactly one successor in a cycle.  With linear
strings `\n` would have no successor, `Σ_v N(\n,v) = 0`, and the identity would
fail.  So "bend into a cycle" is load-bearing.

The closed form assumes the **MLE** model `P(v|u) = N(u,v)/N(u)`.  Once a prior
/ pseudo-count correction is added, `P` is no longer the empirical ratio and
`CS` becomes a genuine cross-entropy; under the "enormous corpus" assumption
this is moot.

## 11. Remarks

* **The "no `uuu`" assumption protects the counts, not the code.**  It exists so
  that "replace *every* occurrence of `uv`" is well-defined — two occurrences of
  `uv` can overlap only if `u = v`, and then only via `uuu`.  It is preserved by
  the merge step.  But tokenisation is *trivially decodable* regardless: a word
  sequence decodes by deleting the brackets, and even an "ambiguous" tokenisation
  such as `(aa)a` versus `a(aa)` decodes to `aaa` either way.  §9.1 removes the
  need for the assumption altogether.
* **The gain is not a pointwise-mutual-information term.**  Merging a
  deterministic alternation `ab ab` changes `CS` by nothing, though its PMI is
  positive — the effect is already in the pair counts, and `CS` is an entropy,
  not a likelihood ratio.
* **No MDL for the dictionary.**  `CS` deliberately excludes the cost of the
  dictionary and the code table, so on its own it is gameable.  Following
  `SUCCESSOR_MODEL.md`, the model is built once and reused, its size is a
  resource to spend, and the question is the Pareto one — smallest score at a
  given model size.  The size knob here is `NUM_PAIRS`, and the score should be
  the **held-out** code length (bits/string).  See `docs/WORD_COMPRESSIBILITY.md`.
* **Greedy by frequency vs greedy by `Δ`.**  The rule of §2 merges the largest
  `N(u,v)`, a proxy for the smallest `Δ`; `Δ` also depends on the embedding
  (`A`, `B`, `Q`).  Measured in `docs/DICTIONARY_RULES.md`: the `Δ` rule wins on
  structured synthetic data but barely on real identifiers, so the frequency
  proxy is kept.
* **Implementation: rescan, not a position index.**  Nothing in §2 requires
  knowing *where* the occurrences are between merges — only the step they are
  merged at.  So the production builder (`scripts/tree_words.py`,
  `build_dictionary_arr`) keeps the corpus as one packed `int32` array with a
  `-1` separator between identifiers and, at each merge, finds the occurrences
  with a single numpy scan `(arr[:-1]==u) & (arr[1:]==v)`, rewrites them, and
  compacts.  The alternative — a `{(u,v): {(seq, pos), …}}` index plus a list of
  lists of ids — is 10–100x the size of the packed array and is what made the
  full-corpus (stride 0) build need gigabytes; the scan is O(N) per merge but
  vectorised, so the whole `NUM_PAIRS` sweep is linear in the corpus with a small
  constant.  The bigram matrix is counted the same way
  (`count_adjacency_stream`): stream the corpus in chunks, tokenise, encode each
  adjacent pair as `a·V + b`, and merge per-chunk `np.unique` results.  The two
  paths are checked against the old implementation by
  `scripts/word_build_rescan.py`; the word list and the matrix are identical,
  including the cyclic row-sum invariant `sum_v N(u,v) = N(u)`.
* **Tie-breaking.**  "Most common length-2 substring" needs a deterministic rule
  on ties (a canonical order over the words, or "lowest pair in creation
  order"); the regression scripts use smallest `(u,v)`.
