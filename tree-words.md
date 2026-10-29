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


# Success metric

Success (smaller better) is the sum over the corpus of the compressed size of its strings.

We believe this is equal to sum over u of N(u) log(N(u)) - sum over u, v of N(u, v) log(N(u, v))


# Effect of incrementing `NUM_PAIRS`

TODO!


# Notes

*Explanatory notes added 2026-10-29. The sections above are the specification;
this is commentary on why they work, what is assumed, and what is deliberately
left out.*

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

The belief is correct, and it is worth recording why, because the derivation
pins down what it depends on. Per string,

    -log2 P(u_0 ... u_n) = -sum_i log2 P(u_{i+1} | u_i)
                         = sum_i log2 [ N(u_i) / N(u_i, u_{i+1}) ] .

Summing over the corpus, each bigram `(u,v)` appearing `N(u,v)` times,

    CS = sum_{u,v} N(u,v) log2 [ N(u) / N(u,v) ]
       = sum_{u,v} N(u,v) log2 N(u)  -  sum_{u,v} N(u,v) log2 N(u,v) ,

and the first term collapses because `sum_v N(u,v) = N(u)` for every `u`,
giving

    CS = sum_u N(u) log2 N(u)  -  sum_{u,v} N(u,v) log2 N(u,v) .   ✓

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

## On incrementing `NUM_PAIRS` (the TODO)

A merge changes the tokenisation, hence both `N` (down: one token per merged
occurrence disappears) and `H(next | word)` (up or down), and `CS = N . H`.
For a single merge of `(p, q) -> w`, repeating `m = N(p,q)` times, the exact
change is a finite difference

    delta = N . H  -  N' . H'

in which the unigram counts shift (`N(p)` and `N(q)` each drop by `m`, while
`N(w) = m`) *and* the
context bigrams are rewired: each occurrence `(a, p, q, b)` loses `(a,p)`, `(p,q)`,
`(q,b)` and gains `(a,r)`, `(r,b)`. There is no clean closed form — the gain
depends on the joint of the surrounding contexts — and in particular it is *not*
simply a pointwise-mutual-information term (merging a deterministic alternation
`ab ab` gains nothing, though its PMI is positive). The greedy "most frequent
pair" rule is therefore a heuristic proxy for `delta`; the honest statement is
the frontier of held-out bits/string against `NUM_PAIRS`.
