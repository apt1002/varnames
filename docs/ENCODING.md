# The encoding

Status: **design note; the decisions are settled, the binary layout is
specified but not yet measured.**  This collects what the encoding has to do,
the argument for publishing a *code* rather than a *table of probabilities*, and
the extensions that leave the encoding alone.  The three questions it used to
leave open are closed: the standard ships one model, fixing `V`, `k` and `q`,
and the file is specified in [`MODEL_FORMAT.md`](MODEL_FORMAT.md) §7; the
reserved stop clusters are rejected (`NEWLINE_CLUSTER.md`); and the canonical
integer is a requirement on the encoder (§1), not something the decoder checks.
Measurements that bear on it live in `CODING_OVERHEAD.md` (Huffman vs
arithmetic), `CLUSTER_WORDS.md` (the factorised block model) and
`MODEL_BUDGET.md` (what a table costs in bytes).

## 1. What the encoding has to do

An identifier is a word-token sequence `t₁ … tₙ` under the model
`P(tᵢ | tᵢ₋₁)`, wrapped in the stop token: the identifier is the cycle
`\n t₁ … tₙ \n`.  The encoding maps identifiers into 64-bit (or 128-bit)
integers, and decoding recovers the identifier from the integer.

Working into a *fixed budget* changes what "bijection" means:

* **Encode is injective, decode is total.**  Every integer decodes to some
  identifier; each identifier is represented by exactly one *canonical*
  integer (its code, padded with zeros).  The other integers that decode to the
  same identifier are wasted words, not alternative encodings.  So the object
  the standard defines is a bijection between identifiers and a *subset* of the
  integers, not the whole range.
* **Canonical means "high bits zero".**  The decoder ignores every bit above the
  last symbol it read — they carry no information, and a decoder that rejected
  non-zero ones would be rejecting valid words.  But the *encoder* is required
  to write zeros there, and that requirement is what makes the map from
  identifiers to integers injective.  It belongs in the standard as a rule about
  the encoder, not as a property the decoder checks.
* **"No more bits" is a legal signal.**  The 64-bit budget is information in
  its own right, and §2 is exactly a use of it.

## 2. The stop token and the zero padding

### The Huffman case: why it works

Every binary tree has exactly one leaf whose codeword is all zeros — follow the
`0` branch from the root until a leaf is reached.  So the trick costs nothing to
arrange: after building the tree, orient each node's children so that the stop
token lands on that leaf.  Then:

1. **Termination is unambiguous.**  No other codeword starts with the stop's
   codeword `0^l` (the code is prefix-free), so `l` zeros can only mean "stop".
2. **The padding *is* the stop.**  Write the code into the low bits of the word
   and leave the high bits zero.  The decoder reads symbols until it has read
   `0^l`, which it finds in the padding; a word whose code ends exactly at bit
   63 reads zeros "beyond the budget", which is the same thing.
3. **The stop's bits are never spent.**  The identifier's length is
   `Σᵢ len(tᵢ)`: the terminator is free.  The stop must still be *in* the tree
   — it is what makes the padding decode to a terminator instead of to more
   tokens — but its own code length is not paid per identifier.

Point 3 is worth stating carefully because it affects how the numbers compare.
`CODING_OVERHEAD.md` measures Huffman and arithmetic lengths *including* the
stop transition; with the zero-padding terminator the Huffman numbers should
lose it (a bit or two per identifier).  An arithmetic coder cannot do the same
(§2.2), so the fair comparison for the fixed-budget question is "what fits in
64 bits", where Huffman keeps the advantage.

There is a price in *accounting*, not in correctness.  Because the terminator
is never written, the code is not prefix-free over identifiers: the code for `ab`
is a prefix of the code for `abc`.  Kraft's inequality therefore does not hold,
and "mean bits" is no longer an entropy — it is a *capacity* statement ("how many
identifiers fit in 64 bits").  That is legal — encode is still injective, and
decode is still total — but it means the arithmetic bound in
`CODING_OVERHEAD.md` is not the right yardstick for the finished product: the
flat Huffman code can legitimately beat it by the stop's code length (1–3 bits
per identifier, since the stop is roughly one token in seven).  The yardstick
that matters is the 64/128-bit **fit rate**, and the factorisation comparison
(flat vs two trees) is unaffected, because both sides of it omit the stop.

### Give the stop a zero weight in the tree

Since the stop's bits are never spent, its *probability* should not be allowed
to shape the other codes either.  Build the tree with the stop's weight set to
zero (or just below the smallest real weight), keeping it as a leaf so the
all-zeros path still exists.  Huffman then gives every other symbol the lengths
optimal for the **renormalised** distribution:

    len(b) ≈ log₂(1/p̂_b) = log₂(1/p_b) − log₂(1/(1 − p))

with `p` the stop's conditional probability in that context.  At `p ≈ 0.15`
(one token in seven is the stop) that is **0.23 bits per token, ~1.4 bits per
identifier** — an order of magnitude more than the whole Huffman penalty
`CODING_OVERHEAD.md` measured.  Without the zero weight, the tree is optimal for
a quantity we never charge.

The cost is one bit on the least probable symbol (the zero-weight leaf has to
pair with something at the bottom of the tree), so the trade is overwhelmingly
favourable.  Two things to check in measurement: Huffman's tie-breaking must not
strand the zero-weight leaf at a shallow depth (force `depth ≥ 1`), and the
all-zeros codeword is then the *deepest* leaf, so the decoder may need up to
`max depth` zeros of padding to see the terminator — free, but it must be
specified.

A zero-weight leaf is exactly the classic "escape" symbol, and this is the
cleanest way to describe the design: **the stop is an escape to end-of-budget,
coded for free, and the other symbols are coded as if the identifier continued.**
Measured at `V = 2104, k = 52` this is worth 1.74 bits/identifier, and it is
enough to make the flat Huffman code cheaper than the arithmetic reference
(1.04 bits/identifier) — see `CODING_OVERHEAD.md`.  The all-zeros codeword
landed at depth 26, which is the padding bound.

One small inefficiency remains: the trees are built on the full distribution
(including the stop), but the stop's mass is never converted into bits.  The
alternative — build over the renormalised non-stop distribution and graft the
stop onto an edge — costs at least as much (grafting one extra edge onto the
path of every leaf below it).  Including the stop and not spending it is
therefore the practical optimum — provided its weight is driven to zero as
above.

### The trailing zeros are free

The code sits in the low bits of the integer and the terminator is the run of
zeros above it, so a zero at the **top** of the written code is indistinguishable
from padding and need not be stored.  The top bits of the code are the last bits
of the final codeword, so whenever that codeword ends in zero the identifier is
one bit shorter.  For a code whose last bits are about balanced that happens half
the time, then a quarter of the time for two zeros, and so on:

    E[trailing zeros] ≈ ½ + ¼ + … = 1 bit per identifier, purely by luck.

Nothing has to be stripped to get it: the canonical form is simply *the
integer*, and an integer's binary length already stops at its highest set bit.
Two consequences:

* It is another **~1 bit/identifier that arithmetic coding cannot match** — the
  shortest fraction in the arithmetic interval is already optimal, and has no
  such structural slack.  Together with the zero-weight stop this is ~2 bits per
  identifier in Huffman's favour (against ~0.7 bits of rounding).
* It is a further reason the **fit rate** is the yardstick and "mean bits" is
  only a capacity statement: a code with fewer trailing zeros produces *smaller*
  integers, which the fit rate counts and a summed codeword length does not.
  Any measurement that sums codeword lengths is therefore ~1 bit conservative.

### The arithmetic case: why it does not transfer

Arithmetic coding replaces the per-symbol code by one number: a point in the
message's interval.  After encoding `t₁ … tₙ`, the encoder's interval is
`[L, L+P)`, and the stop occupies the sub-interval

    [L, L + P·pₙ),        pₙ = P(\n | tₙ)

For "all zeros works" we would need the value `0` (the all-zeros fraction) to
lie in that sub-interval — i.e. `L = 0`, which is true only for the first symbol
of the first identifier.  So the terminator must be **encoded**, at a cost of
`−log₂ pₙ` bits per identifier, and the zero padding carries no information: it
is precision, not a symbol.

Equivalently: with a prefix code, "0^l means stop" is a statement about the
*code tree*, which is fixed and context-local; with an arithmetic code there is
no tree, only the surviving interval, and where that interval sits depends on
the whole history.

**Can it be rescued?**  Two variants are worth recording as dead ends:

* *Renormalise away the stop and stop decoding when the bits run out.*  The
  decoder cannot tell "the encoder finished" from "the encoder happened to emit
  zeros", so it keeps decoding the padding.  It produces a finite sequence (no
  real codeword starts with the stop's zeros, so it terminates), but that
  sequence is not the encoded one.
* *Disk the stop at the top of every interval.*  That is just encoding it
  normally, since the top of the interval has a well-defined width `P·pₙ`.

**Conclusion.**  The zero-padding terminator is a property of per-symbol prefix
codes.  The arithmetic coder pays `−log₂ pₙ` (typically 1–3 bits) for a
terminator that Huffman gets for free.  This is a second argument for a Huffman
standard (§3), independent of portability, and it should be measured: the
residual gap between the arithmetic bound and a Huffman code may be smaller than
`CODING_OVERHEAD.md` reports, once the terminator is accounted for on both sides.

## 3. Publish the code, not the probabilities

Two ways to ship the model:

1. **Publish the code.**  The standard contains, per tree, the code lengths (or
   the codewords themselves) plus the *word list*, the *cluster assignment* and
   the *block* `D`.  Start-up is a table read.
2. **Publish quantised probabilities.**  The library rebuilds the Huffman trees
   at start-up from a table of 1-byte probabilities.

The first is better on every axis that matters here.

* **It costs the same bytes.**  A Huffman code length is an integer ≤ 255, i.e.
  one byte per symbol — exactly what a 1-byte probability costs.  Publishing
  the code is not a bigger table; it is the same table with the redundancy
  removed.
* **It removes the arithmetic-coder specification entirely.**  Option 2 does
  not avoid a code: it only moves the tree construction into every ported
  library, where a rounding difference, a different tie-break, or a different
  `−log₂` implementation produces a *different* code.  Two implementations then
  disagree about the encoding, which is precisely the interoperability risk a
  standard exists to remove.
* **It makes the decoder trivial and exact.**  Canonical Huffman decoding is
  integer arithmetic: sort symbols by `(length, id)`, count codes per length,
  walk the prefix table.  It is thirty lines in any language, needs no floating
  point, and is already standard practice (DEFLATE, JPEG, Brotli).
* **It fixes what would otherwise be unspecified.**  Option 2 leaves open the
  tie-breaking when two subtrees have equal weight, the treatment of zero-
  probability symbols, the orientation that puts the stop on the all-zeros leaf,
  and the exact quantisation of `p`.  All four change the emitted bits.

What the standard must pin, in order of how easily it goes wrong:

* the canonical assignment (lengths → codewords) and the symbol numbering;
* the orientation rule that puts the stop on the all-zeros leaf;
* the bit order in the word, and the encoder's duty to leave every unused high
  bit zero (the decoder must ignore them, not test them);
* the byte order for the 64/128-bit word (little-endian) and the stop's role as
  "the code continues past the budget as zeros";
* for the clustered model: the word list, both cluster assignments and `D`, with
  the *decoder's* arithmetic (integer) spelled out — `P(b | a)` must be
  evaluated identically in every implementation, or the encoder and decoder
  disagree about the codewords of the next symbol.

That last point is the one place where floating point would otherwise creep into
a standard.  If the code is published, the decoder never computes `P(b | a)` at
all: it walks the tree that the code lengths define.  The probabilities are
model-building-time only.

## 4. One tree or two (recap)

`CODING_OVERHEAD.md` measured, at `k = 52` and `k = 105` on `V = 2,104`:

| code | bits/identifier | penalty |
|---|---:|---:|
| arithmetic (reference) | 56.368 | — |
| one tree per left cluster over the *joint* `P(b|a)` | 56.558 | +0.190 (0.34 %) |
| two trees: `P(cluster|cluster)` × `P(word|cluster)` | 57.770 | +1.402 (2.49 %) |

The factorised code loses ~7× the flat code because the flat code is the Huffman
code of the joint distribution, while a product of two prefix codes is not
optimal for it.  The split was 0.036 bits/token (cluster step) + 0.173
bits/token (word step): the word step, a long-tailed alphabet, dominates.

Two conclusions carry.  The remaining inefficiency is the word step, which is
what the quarter idea attacks ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)); and
on *bits*, one tree per left cluster over the joint is what to compare against,
though it is not what can be published — which is the rest of this section.

**But the flat code cannot be published.**  Its table is `k` trees of `V` leaves:
224 kB at `(4,096, 32)`, 448 kB at `(4,096, 64)`, 960 kB at `(8,192, 64)`,
against 7.9–19 kB for the factorised project.  Publishing probabilities instead
of lengths does not rescue it (that is `k·V` bytes, 131 kB at `(4,096, 32)`).
So the choice splits on §3: if the standard ships the code, the flat code is out
and the design is **CF or CQF**; if the library derives codes at load time, the
flat code is free and CQF is buying back a loss that need not exist.  Since
publishing is the interoperable option, the honest reading is: **flat is the
yardstick, CF or CQF is the product.**

## 5. Two extensions that leave the encoding alone

Neither idea changes how a codeword is written; both are written up separately.

* **Cluster quarters** ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)) split each
  left cluster's tree into `q` right clusters, so the top stage has `q·k` leaves
  instead of `k`.  The encoding is unchanged: this note with `q·k` in place of
  `k` in the top stage, and nothing else.  It is adopted at `q = 2`, and the label set
  is still one set: a word's label is its right cluster, and its left cluster is
  that label divided by `q` (`MODEL_FORMAT.md` §1).
* **Codesigning the assignment** ([`CODESIGN.md`](CODESIGN.md)) chooses the
  clustering and the trees together, so it changes which labels exist and, in
  general, how many (`k` may grow).  That is a generation question: a decoder
  cannot tell a codesigned model from any other model with the same `V` and `k`.

An implementation of §§2–4 decodes a model built either way: the first changes
only the label space, the second only which labels exist.
