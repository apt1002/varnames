# Corpus

Corpus is a multiset of strings of characters (e.g. programming language identifiers).

Suppose, as a warm-up exercise, that the corpus does not contain three consecutive repeats of any substring. We can relax this condition later.

Suppose the characters `(`, `)` and `\n` do not appear in the corpus.

Append to each word a stop character (I will use `\n`) and bend it into a cycle.


# Build a dictionary

Initialise the set of *words* to be the set of characters plus `\n`. The corpus will hereafter be treated as a multiset of cyclic strings of words.

Initialise the *wordlist* to be an empty list of pairs of words.

Repeat N times:

- Find in the corpus the most common length-2 substring `uv` where `u` and `v` are words.

- Add `(uv)` to the set of words.

- Append `(uv)` to the wordlist.

- Replace in the corpus every occurrence of `uv` with `(uv)`. Note that other occurrences of `u` and `v` are unaffected.


# Tokenise an unseen string.

Given an unseen string `s` of characters, append `\n`, bend it into a cycle, and reinterpret it as a string of words.

For each `uv` in the wordlist:

- Replace in `s` every occurrence of `uv` with `(uv)`.


# Estimate the probability of a string.

We construct a model of the probability of a tokenised string (i.e. a cyclic string of words) in terms of the probabilities of its length-2 substrings.

