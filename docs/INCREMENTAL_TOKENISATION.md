# Incremental tokenisation

Status: **work in progress.**  The setting is fixed and one proposition is
proved: every token of a tokenisation is itself a tokenisation (§3–§5).  §6
tests the state proposed for the left-to-right scan and finds that it does not
commute with the rules: the finish-off it was meant to support is wrong as
stated.  The left-to-right scan itself is still to be written.

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

## 6. The proposed state does not commute with the rules

### 6.1 The proposal

A left-to-right scan needs a state: a function of the prefix alone that is cheap
to update when one more character arrives, and from which the tokenisation of the
whole input can be recovered when the input ends.  The candidate is a word
sequence that has taken every merge it can take *except* at the right end, where
the next character may still undo one.  For `n = 0 … K`, on word sequences:

    P_K(s)                =  s,
    P_n(s)                =  P_{n+1}(R_n(s))                    if s does not end with u_n v_n,
    P_n(s' u_n v_n)       =  P_{n+1}(R_n(s' u_n)) v_n            otherwise.

The third line withholds the last word `v_n` from every remaining rule, on the
grounds that the last word is the only one a merge with input still to come can
swallow.  Then

    S_n(s) = P_n(T_n(s)),

so `S_0(s) = P_0(s)` is the state after reading the prefix `s`, and `S_K(s) =
T_K(s)` is the answer.  The hope was that the finish-off is one rule per stage,

    S_{n+1}(s) = R_n(S_n(s)),                                       (*)

which would make `step` and the finish-off the same operation: apply the rules
in order to the state.  (*) is false.

### 6.2 A counterexample

`T_0` is the identity, so (*) at `n = 0` reads `R_0 ∘ P_0 = P_1 ∘ R_0`, and a
counterexample to that is a counterexample to (*).  Two characters and three
rules suffice:

    (0,1) → 2,      (0,2) → 3,      (1,0) → 4,      s = 1 0 0 1.

The run and the two states:

    T_0(s) = 1 0 0 1     T_1(s) = 1 0 2     T_2(s) = T_3(s) = 1 3
    S_0(s) = 4 0 1       S_1(s) = 1 0 2

so `R_0(S_0(s)) = R_0(4 0 1) = 4 2`, whereas `S_1(s) = 1 0 2`.  ∎

The steps.  For `S_0`: `s` ends with `(0,1) = (u_0, v_0)`, so `P_0` withholds
the final `1` and runs rules `0 … 2` on `1 0 0`.  Nothing there matches
`u_1 v_1 = (0,2)`, and rule `2` merges the `1 0` into `4`, leaving `4 0`; the
withheld `1` goes back on the end, giving `4 0 1`.  For `S_1`: `T_1(s) = 1 0 2`
ends with `(0,2) = (u_1,v_1)`, so `P_1` withholds the `2` and runs rules `1 … 2`
on `1 0`; that ends with `(1,0) = (u_2,v_2)`, so `P_2` withholds the `0` and
rule `2` never sees the pair — giving `1 0 2`.

The two states have merged *different, overlapping* pairs.  In `S_0` the pair
`1 0` is merged (as `4`) and the pair `0 1` is withheld; in `S_1` the pair `0 1`
is merged (as `2`) and the pair `1 0` is withheld.  The two pairs share a
character, so no run can merge both, which is exactly what (*) demands of
`R_0(S_0(s)) = 4 2`.

An exhaustive check over the two-character alphabet finds no failure with one or
two rules on strings up to length six; with three rules exactly two of the 144
lists fail, both first at length four, and the list above is one of them.

### 6.3 The state is not a coarsening of the run

Two things go wrong when `P_n` withholds a trailing `v_n`.

* **The merge is skipped, and the run makes it.**  `T_n(s)` ends with
  `u_n v_n`, rule `n` runs before every later rule, and nothing to the right of
  `v_n` can take it away.  So the run merges that pair and `P_n` does not: `S_n`
  is not a stage of the run of `s`.
* **The neighbours are freed to merge differently.**  The rules after `n` are
  run on `s' u_n`, in which `u_n` is the last word and can be withheld in turn;
  and the words around the withheld one no longer see it, so a rule that would
  have merged with it merges with a neighbour instead.  The pair it merges may
  *overlap* the pair the run merges, and then the state contains a token that
  the answer does not contain at all.  In §6.2, `4 = (1,0)` is such a token:
  `T_3(s) = 1 3` contains no such merge.

Because a merge never splits a token, every token of the state is a node of the
forest of every later sequence built from it.  A state that can be completed into
`T_K(s)` must therefore have all of its tokens as nodes of the forest of
`T_K(s)`: its merges must be a subset of the run's merges.  The second point says
that `P_0(s)` fails even this.  In §6.2 the forest of `T_3(s) = 1 3` has the
nodes `3`, the `0` at position 1, and `2 = (0,1)` over positions 2 and 3, so the
state's token `4 = (1,0)` over positions 1 and 2 is not among them.  No
completion of the state by further merges can therefore produce `T_K(s)`: the
finish-off is impossible in principle, not merely hard.

### 6.4 The finish-off, on the standard model

`T_K(P_0(s)) = T_K(s)` is exactly the property the finish-off needs, and it
fails.  Over 300 randomly sampled identifiers of
`corpus/identifiers.multilang.txt`, 24 are tokenised differently by the
finish-off.  One of them, with `w_n` written for the word of rule `n`:

    s            = 'r' 'x' '_' 'a' 'c' 't' 'i' 'o' 'n'          (`rx_action`)
    P_0(s)       = 'r' w5778 w205 'i' 'o' 'n'
    T_K(P_0(s))   = 'r' w5778 w205 w9
    T_K(s)       = 'r' w5778 w707

with

    w5778 = ('x','_')   w205 = ('a', w17)   w17 = ('c','t')
    w9    = ('i', w1)   w1   = ('o','n')    w108 = (w17, w9)
    w707  = ('a', w108)

The state withholds `'n'` at rule `1 = (o,n)` and then `'o'` at rule
`404 = (i,o)`, leaving `'i' 'o' 'n'` raw and `w205 = act` merged.  Rule 108
comes before rule 205, so in the run `w17 = ct` merges with `w9 = ion` and the
`'a'` then merges with the result; in the state's run there is no `w9` at rank
108, so `w17` survives to rank 205 and takes the `'a'`.  `w205` is a token the
answer does not have, and the finish-off leaves it alone:
`'act' 'ion'` where the answer has `'action'` as `w707`.

### 6.5 What a state would have to be

By §6.3 the state must be a **sub-run**: the merges it has performed must be a
subset of the merges of the run of `s`, performed in the same order.  A prefix
of tokens may be committed only if no merge can cross the cut.  Adjacent tokens
never form a rule pair — by §4.2 the two are adjacent at every stage, so the
rule would have merged them — so a merge that crosses a cut must take the word
*ending* at the cut as its `u`, never the word starting there as its `v`.  The
words ending at a cut are the token there and the chain of its right children;
each is the word ending at the cut over a known interval of ranks; so the cut can
be crossed iff one of them is the `u` of a rule whose rank lies in that
interval.  This test is decidable from the token and the model, and it is nearly
always positive: in the standard model every one of the 63 characters is the `u`
of some rule, and on 2,000 sampled identifiers 1,939 can commit nothing at all
while the other 61 can commit exactly one token.

So a state that is a function of the prefix and correct for every continuation
keeps essentially the whole prefix, and the reason is the one in §5.2:
tokenisation does not distribute over concatenation.  What the state cannot know
is whether the characters after a cut will complete a `v` for some `u` that ends
there, so the *decision* to stop merging at a boundary is a lookahead decision,
not a property of the prefix.  A scan either keeps the whole string live, as
`codec.rs` and `codec.py` do, or decides with the characters already seen rather
than with the prefix alone — which is the subject of §7.

## 7. To come

The left-to-right scan.  *(The author continues here.)*

*Check to date:* the proposition was tested on 500 sampled corpus identifiers
through `python/varnames/codec.py`: every token of every tokenisation spells
back to its interval and re-tokenises to itself under all rules (`T_K`).

§6.2's counterexample was found, and then verified, by enumerating every rule
list over two characters with one to three rules and every string up to length
six: no failure with one or two rules, two failures with three, none sooner than
length four.  The standard-model numbers come from
`corpus/identifiers.multilang.txt` sampled at random with a fixed seed: 300
identifiers for §6.4, 2,000 for §6.5, and 3,000 to confirm that no two adjacent
tokens of a tokenisation ever form a rule pair.
