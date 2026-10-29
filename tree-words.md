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
