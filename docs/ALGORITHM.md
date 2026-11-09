# The algorithm, end to end

Status: **a narrative of the shipped design.** It walks from a corpus of
identifiers to a 64-bit integer and back, in the order the pieces are built,
and gives the cost of each stage. The notes cited along the way carry the
proofs and the full measurements; this file is the one place that shows the
whole thing in sequence. The designs that lost, with the numbers that killed
them, are in [`ALTERNATIVES.md`](ALTERNATIVES.md).

The design is small: a word list built by pairwise merging, a word-bigram
matrix smoothed by a prior, a coarse block model of that matrix, Huffman trees
built from the blocks, and a packed binary file that stores depths rather than
probabilities. The model file is 30,745 bytes and puts 85.0 % of held-out
identifiers inside 64 bits.

## 1. What is being built

An identifier is a string such as `getUserName`. The product is a bijection
between identifiers and a *subset* of the 64-bit integers: encoding is
injective, every integer decodes to some identifier, and each identifier has
exactly one canonical integer — its code padded with zeros to the top. The
integers that decode to an identifier other than its canonical one are wasted
words, not alternative encodings ([`ENCODING.md`](ENCODING.md) §1).

That framing matters because the product is judged at a **budget**, not at a
mean. The two claims are the share of held-out identifiers inside 64 bits and
the share inside 128 bits, measured against the size of the model file. The
frontier that trades one for the other is in
[`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6; the sets themselves are in
[`BUDGET64_STUDY.md`](BUDGET64_STUDY.md).

## 2. The corpus

The corpus is the union of identifiers harvested from ten language ecosystems —
Ruby, Rust, OCaml, Haskell, Java, Python, Go, Lua, Perl and JavaScript — kept
sorted and unique: **4,441,974** distinct identifiers
([`CORPUS.md`](CORPUS.md)). Breadth matters because the word list and the
bigram statistics are estimated from it, and a list tuned to one language's
naming conventions does not generalise to the others.

The corpus is also the only thing a build needs. Everything downstream is
deterministic given it.

## 3. Case normalisation

Casing is a convention, not information: `foo_bar`, `FOO_BAR` and `fooBar` are
the same word. The corpus is split into three classes — lower_case,
UPPER_CASE and CamelCase — the first two are rewritten in CamelCase, and the
three lists are merged and de-duplicated: **4,226,707** identifiers, 215,267
collapsed ([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)).

The gain is measured on identifiers normalisation leaves *unchanged*: the same
CamelCase strings are **3.5 bits shorter** (41.83 against 45.37) under a model
trained on the normalised corpus, because each word's counts are now estimated
from all three conventions at once. Normalisation is reversible given the class
label; only the label is dropped. An encoder must normalise its input the same
way, or the model is being asked about strings it was not built for — the
mismatch costs 7.7 bits.

## 4. The word list

Tokenising into words is where the model gets its compression. The word list is
built by **pair merging**: start from the 63 characters the corpus uses plus the
stop, repeatedly merge the most frequent adjacent pair of existing words, and
record the merge as a rule. Every word is therefore two earlier words, and a
decoder can replay the rules ([`TREE_WORDS.md`](TREE_WORDS.md) §2,
[`DICTIONARY_RULES.md`](DICTIONARY_RULES.md)).

Two features of the adopted rule are deliberate. It **never merges a symbol
with itself**, so there are no run words and no `k`-ary nodes; and it is greedy
**by frequency**, not by the exact change in code length, because the exact
score's edge on real identifiers is a fraction of a percent for eight times the
work.

The list has **8,128 words**. With the 63 characters and the stop that is the
`V = 8,192` of the standard. The rules are stored as a ladder-coded list and
take **20,926 of the 30,745 bytes** — two thirds of the file. That ratio is why
[`WORDLIST_BUDGET.md`](WORDLIST_BUDGET.md) concludes that a larger word list is
always the better way to spend a byte.

## 5. Tokenisation

A word list applied to a string is a *replay*: apply the merges in creation
order, and at each step merge the lowest-ranked applicable adjacent pair, ties
leftmost. The result is deterministic. The decoder never re-tokenises: it reads
words out of the code, which is why the tokenisation has to be specified even
though only the encoder runs it ([`TREE_WORDS.md`](TREE_WORDS.md) §3).

The implementation is the hot loop of every pass. A naive operator-precedence
parser is faster but wrong on nested ranks; the production path is an
ascending-rank sweep with a linked list over positions and a heap over distinct
ranks, which is exactly equivalent to the reference replay and about 1.4×
faster ([`TOKENISATION.md`](TOKENISATION.md)).

At the operating point an identifier is **4.06 words** on average. That number
is the multiplier on every per-token cost, including the rounding a Huffman
code pays per symbol ([`CODING_OVERHEAD.md`](CODING_OVERHEAD.md)).

## 6. The matrix

The model is first-order over words. The corpus is bent into a cycle — the
identifier is `\n t₁ … tₙ \n` — and the counts of each adjacent pair form
the **word × word adjacency matrix** `M`
([`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md)).
At the operating corpus that is 19.2 million token transitions and 2.5 million
distinct pairs.

Unobserved pairs are not zero: they are smoothed by a **prior of strength
`κ = 300`**, which mixes the row and column marginals into every cell. `κ` was
chosen by held-out likelihood, and the shape of that prior — an independence
prior rather than one that recurses down the merge tree — is what survived
measurement ([`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md)).

The stop's **row** of the matrix is kept: it is the distribution of first
tokens, the start state. Its column is not, because nothing is coded after the
end of an identifier.

## 7. The block model

`M` has 67 million cells and cannot be stored. It is replaced by a
**co-clustered block model**: each word is assigned a left cluster and a right
cluster, the matrix is summed into a `k × k` block table, and the words within
a cluster are covered by Huffman trees. At `k = 32` the model stores
**17,408 numbers — 0.026 % of the table — for a loss of about 1.15 bits per
identifier** ([`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)).

Clustering is `k`-means in the **Hellinger** embedding of the row and column
profiles, where distances between conditional distributions are Euclidean
([`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md)). One assignment is
shared by both sides (`q = 1`): over five seeds it costs 0.34 points at matched
bytes for `k = 32`, and it halves the map the file must store — 5,120 bytes
([`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md),
[`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)).

The residual loss is real and is where the design pays for its size; plotting
it against `k` is the subject of [`CLUSTER_LOSS.md`](CLUSTER_LOSS.md).

## 8. The code

The block model describes a two-stage code, and the encoder follows it exactly.
Start in left cluster 0. For each token:

1. code its **right cluster**, given the current left cluster, in that left
   cluster's *top* tree;
2. code the **symbol** within its right cluster, in that right cluster's
   *bottom* tree;
3. the symbol's left cluster becomes the current left cluster.

The top tree of each left cluster has `k + 1` leaves: the `k` right clusters
and a **zero-weight STOP leaf**. Finishing means writing the stop; because the
stop has zero weight it is the deepest leaf and its codeword is all zeros, so
the padding writes it for free and its length is never charged. The bottom
trees have no terminator ([`ENCODING.md`](ENCODING.md) §2,
[`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md) §1).

Each tree is a Huffman tree built from the block masses, with a **bias** added
to the leaf weights. The bias exists to keep every tree's depth span inside
**four bits**; it is found by search rather than computed, because no closed
form bounds a Huffman span, and it costs nothing measurable at the grid
([`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md) §3.1). Depths alone determine
the codewords: the all-zeros codeword is the first leaf at maximum depth and
the rest follow in order, so the file stores no orientation and no code table.

Finally the code is placed in the low bits of the integer and the high bits are
left zero. The trailing zeros of the last codeword are not stored either, which
returns about a bit per identifier ([`ENCODING.md`](ENCODING.md) §2.3).

## 9. The decoder

Decoding is the same loop read back. Start in left cluster 0 and walk a top
tree. If the walk lands on the STOP leaf, the identifier ends — and since the
padding is zeros, a decoder that runs out of bits reads the terminator and
stops. Otherwise the leaf names a right cluster; walk its bottom tree for the
symbol; append it; the symbol's left cluster becomes the current one; repeat.

There is nothing to check and nothing to back-track: the code is prefix-free
within each tree, and the canonical form makes the map injective. A decoder
that ignores bits above the last symbol it read is correct, which is why the
standard puts the "write zeros" rule on the encoder
([`STANDARD.md`](../standard/STANDARD.md) §4).

## 10. The file

The model is one binary file with eight sections, all little-endian and
byte-packed with no padding: magic, header, the length of the rule list, the
rules, the character alphabet, one membership per word, one depth per bottom
leaf, and the top-stage depths. At the operating point that is **30,745
bytes**, SHA-256 `976670d7…` ([`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md)
§3, [`STANDARD.md`](../standard/STANDARD.md) §9).

It stores no probabilities, no floating point and no code table: depths and
rules are enough for every port to rebuild the same codes. A YAML rendering
travels beside it for reading and diffing (182,507 bytes), but the binary is the
deliverable.

## 11. What it achieves

| | |
|---|---|
| model file | 30,745 B |
| held-out mean | 45.218 bits per identifier |
| inside 64 bits | **85.0 %** |
| inside 128 bits | 99.0 % |
| longest code in the sample | 622 bits |

Measured on 42,268 held-out identifiers that no part of the build had seen
([`BUDGET64_STUDY.md`](BUDGET64_STUDY.md)). The width of the 64-bit set is
where the boundary falls, and it is not a length rule: the longest identifier
that fits is 59 characters, the Ads/360 client-link operation being coded in
60 bits, while the shortest that fails is 9 (`aaaaaaaaa`, 71 bits). Of the
34,919 identifiers inside that band, 6,207 (17.8 %) miss the budget, and what
marks them is shape — underscores, capital runs and digits — not length.

The price of the factorisation is visible here too. Against the flat Huffman
code at the matched `k = 16` — 123,401 B, 43.333 bits, 86.9 % — the
factorisation costs **2.4 points and 2.3 bits**; the shipped `k = 32` model
buys back half a point of that, leaving **1.9 points and 1.9 bits**, while the
flat file is 94 kB larger. That is the trade: 31 kB instead of 123 kB, for two
points.

## 12. The implementer's checklist

1. **Normalise** the input the same way the corpus was normalised.
2. **Tokenise** by replaying the rules in creation order — lowest rank first.
3. **Encode** from left cluster 0, alternating top tree and bottom tree, and
   write nothing for the stop.
4. **Canonicalise**: pack the bits low, leave the high bits zero.
5. **Decode** by the same walk, treating padding zeros as the terminator.
6. **Check** the model's digest before use, and treat a different digest as a
   different model ([`STANDARD.md`](../standard/STANDARD.md) §9).

A build that follows those steps and writes the eight sections is a conforming
implementation; a corpus of your own can be turned into such a file with one
command ([`BUILDING.md`](BUILDING.md)).
