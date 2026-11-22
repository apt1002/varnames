# Incremental tokenisation

Status: **work in progress.**  The setting is fixed and one proposition is
proved: every token of a tokenisation is itself a tokenisation.  The
left-to-right scan this is meant to support is still to be written.

## 1. The rules are fixed

Let `Σ` be the alphabet of characters, and let the model supply a list of `K`
rules, indexed `0 … K-1`.  Rule `n` names two words `u_n`, `v_n` and the word
it creates, `w_n = (u_n v_n)`.  The list is built once from a training corpus
by the procedure of [`TREE_WORDS.md`](TREE_WORDS.md) and is then **fixed**:
nothing below depends on how it was built.

Two properties of the list matter.

* **Children are older than parents.**  `u_n` and `v_n` are characters or words
  created by rules `m < n`.  So `w_n` is *fresh*: no string of the words that
  exist when rule `n` is made contains it.
* **`u_n ≠ v_n`.**  Two occurrences of the pattern `u_n v_n` cannot overlap —
  an overlap would make the `v` of one occurrence the `u` of the next — so
  "replace every occurrence of `u_n v_n`" selects a set of disjoint positions.

Every character is a word.  **Spelling** turns a word back into characters:

    spell(c)   = c                        for a character c
    spell(w_n) = spell(u_n) spell(v_n)

and a sequence of words spells to the concatenation of its words' spellings.

## 2. The two operations

`R_n` is the **rule on word sequences**: replace every occurrence of the
adjacent pair `(u_n, v_n)` by the single word `w_n`.  The occurrences do not
overlap, so `R_n` is a function of its argument.  `T_n` is **tokenisation by
the first `n` rules**:

    T_0(s) = s,        T_{n+1}(s) = R_n(T_n(s)).

Here `s` is a string of characters, each a one-character word, so `T_0` is the
identity.  No rule introduces a word outside the rule list, so `T_n(s)` is a
sequence of words built from characters by rules `0 … n-1`.

## 3. Proposition

**Decomposition.**  Let `s` be a string of characters and let
`T_n(s) = A_1 … A_l`.  Then

    spell(A_1) … spell(A_l) = s,

and for each `i`, with `a_i = spell(A_i)`,

    T_n(a_i) = A_i            (the one-word sequence),

so `a_1 … a_l = s` and the `a_i` tokenise to `A_1, …, A_l`.

The number of pieces is `l`, the number of tokens; `n` counts rules.

## 4. Proof

### 4.1 Spelling is invariant

*Claim.*  `spell(T_n(s)) = s` for every `n`.

Base: `T_0(s) = s`, whose words are characters spelling to themselves.

Step: `R_n` replaces the pair `u_n v_n` by `w_n`, and
`spell(w_n) = spell(u_n) spell(v_n)`, so the spelling of the whole sequence is
unchanged: `spell(T_{n+1}(s)) = spell(T_n(s))`.  ∎

This is the first line of the proposition, and it is what lets us speak of the
**span** of a token: the interval of character positions of `s` that it
spells.

### 4.2 No token of a later stage crosses a token of `T_n(s)`

Write the intermediate stages of the run as

    S_0 = s,   S_1 = R_0(S_0),   …   S_n = R_{n-1}(S_{n-1}) = T_n(s).

A merge replaces two adjacent tokens by the single token whose spelling is
their concatenation, and no operation ever splits a token.  Hence a token of
`S_r` is contained in a token of `S_{r+1}`, and by induction in a token of
`S_n`.  That is:

* the tokens of every `S_r` are intervals of `s` that tile `s`, and each one
  spells to its interval (4.1);
* every token of every `S_r` lies inside the span of some `A_i`.

In particular, no merge at any stage joins tokens from the spans of two
different `A_i`: the resulting token would have to lie inside the span of a
single `A_i` and would contain positions from two of them.

### 4.3 The run restricted to one span

Fix `i`, and at each stage `S_r` keep only the tokens inside the span of
`A_i`.  Call the result `S_r^{(i)}`.

* At `r = 0` this is `spell(A_i)` read character by character, because the
  characters inside the span are exactly `spell(A_i)` in order (4.1).
* Passing from `S_r^{(i)}` to `S_{r+1}^{(i)}` is applying `R_r`.  A pair of
  adjacent tokens inside the span is a pair of adjacent tokens of `S_r`, and
  `R_r` replaces it iff it is `(u_r, v_r)`; pairs that straddle the boundary
  are never merged (4.2), and they are the only pairs of `S_r` that the
  restriction drops.  So the kept tokens of `S_{r+1}` are exactly what `R_r`
  makes of the kept tokens of `S_r`.
* At `r = n` the tokens inside the span are exactly the token `A_i`, since
  `S_n = A_1 … A_l` has a token boundary at each end of the span.

So `S_0^{(i)}, …, S_n^{(i)}` is the run of `T_n` on the input `spell(A_i)`,
and it ends at the one-word sequence `A_i`:

    T_n(spell(A_i)) = A_i.  ∎

## 5. Consequences and remarks

### 5.1 Blocks, not just single tokens

The same argument applies to any union of consecutive spans: if
`1 ≤ i ≤ j ≤ l` then

    T_n(spell(A_i) … spell(A_j)) = A_i … A_j,

and in particular a prefix ending at a token boundary tokenises to the prefix's
tokens.  What the argument needs is a **cut at a token boundary**; inside a
token it has nothing to say.

### 5.2 The converse is false

The proposition does not say that an arbitrary decomposition of `s` behaves
this way.  With one rule merging `(a, b)` into `ab`, take `s = ab`, cut as
`a_1 = a`, `a_2 = b`.  Then `T_1(a) = a` and `T_1(b) = b`, but

    T_1(s) = ab,   not   a b.

So tokenisation does not distribute over concatenation: pieces may merge
across their join.  That is why the algorithms in `codec.rs` and
`python/varnames/codec.py` keep the whole string live in a heap rather than
tokenising fragments and joining them.  The proposition supplies the
decomposition that *does* work — the one cut at the boundaries the
tokenisation itself chooses.

### 5.3 Freshness and idempotence

The proof of §4 uses only `u_n ≠ v_n` (so that `R_n` is a function).  Freshness
is used for the two idempotences:

* `R_n(R_n(S)) = R_n(S)`, because `R_n(S)` has no occurrence of `(u_n, v_n)`:
  all the old ones are replaced, and the new word `w_n` is neither `u_n` nor
  `v_n`, so no occurrence can involve it;
* `T_n(T_n(s)) = T_n(s)`, because once rule `r` has run, a later rule can
  create neither `u_r` nor `v_r` (every later word is fresh with respect to
  all earlier ones), and a later merge cannot make the pair adjacent again:
  the only way to close a gap between two tokens is to merge a token inside the
  gap into one of them, which destroys that token's identity.

### 5.4 What is not claimed

* Nothing here says where the token boundaries are, or that a left-to-right
  scan can find them without looking ahead.  It says only that once the
  boundaries are known, each piece stands on its own.
* Nothing here is specific to a rule prefix: `n` may be any number of rules,
  including all of them.

## 6. To come

The left-to-right scan.  *(The author continues here.)*

*Check to date:* the proposition was tested on 500 sampled corpus identifiers
through `python/varnames/codec.py`: every token of every tokenisation spells
back to its interval and re-tokenises to itself under all rules (`T_K`).
