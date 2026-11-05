# The encoding

Status: **design note; nothing here is measured yet.**  This collects the
decisions the standard has to make, the argument for publishing a *code* rather
than a *table of probabilities*, and the experiments that would settle what is
still open.  Measurements that bear on it live in `CODING_OVERHEAD.md` (Huffman
vs arithmetic), `CLUSTER_WORDS.md` (the factorised block model) and
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

One small inefficiency remains: the trees are built on the full distribution
(including the stop), but the stop's mass is never converted into bits.  The
alternative — build over the renormalised non-stop distribution and graft the
stop onto an edge — costs at least as much (grafting one extra edge onto the
path of every leaf below it).  Including the stop and not spending it is
therefore the practical optimum.

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
* the bit order in the word, and that the unused high bits are zero;
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

Two conclusions carry into the design below: use **one** tree per left cluster
over the joint, and the remaining inefficiency is the word step — which is what
the quarter idea attacks.

## 5. Cluster quarters (a cheaper way to buy back the factorisation loss)

The factorised model needs `P(cluster | cluster)` before `P(word | cluster)`.
The flat model needs a tree per left cluster over all `V` words, i.e. `k` trees
of `V` leaves — `k·V` code lengths, about 450 kB at `V = 4,096, k = 64`, which
is out of the question.

The idea: **stop each right-cluster tree early.**  Build the tree for
`P(word | right cluster)` and halt when `q` trees remain (call them *quarters*;
they are simply finer clusters, with no special status in the shipped code).
Then encode `P(quarter | left cluster)` with a tree of `q·k` leaves.  Each of
the `k` left clusters gets its own top tree, so quarters from *different*
clusters can be paired when their probabilities are similar — which is exactly
the pairing that the two-level factorisation cannot do.

The mechanism is the classical Huffman redundancy bound: a tree's expected
redundancy is at most about its largest leaf probability, plus a small constant.
Splitting a cell into `q` pieces divides its largest leaf probability by up to
`q`, so the word-step penalty (measured at 0.173 bits/token) should shrink,
while the cluster-step penalty (0.036) hardly moves.

### The size accounting, checked

The formulas as stated:

```
CF  = k (2 (k - 1)   +  k log k)    + (2 (V - k)   + V log V)
CQF = k (2 (q k - 1) + q k log q k) + (2 (V - q k) + V log V)
W   = k (2 (V - 1)   +  V log V)
```

Three corrections, none of which change the conclusion:

* **The bottom stage does not grow.** `2(V − qk)` instead of `2(V − k)` *saves*
  `2(q−1)k` bits — a few hundred bytes.  All of CQF's cost is in the top stage.
* **`V log V` over-charges both.**  The leaf-labelling term is
  `Σ_j V_j log V_j`, which is about `V log(V/k)` for CF and `V log(V/qk)` for
  CQF, not `V log V`.  At `V = 4,096, k = 64` that is 3 kB of over-charge (and
  it over-charges CQF by 6 kB, so the *difference* between the schemes is
  slightly overstated).
* **The top stage is quadratic in `k` and linear in `q`**: `k·qk·log(qk)`.  So
  `q = 2` costs a quarter of `q = 4`, and doubling `k` quadruples it.

With the stated formulas (bytes, including the `V log V` over-charge):

| `V` | `k` | CF | CQF (`q=2`) | CQF (`q=4`) | W |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 32 | 7.9 kB | 9.0 kB | 11.5 kB | 224 kB |
| 4,096 | 64 | 11.0 kB | 16.0 kB | 26.9 kB | 448 kB |
| 8,192 | 32 | 15.9 kB | 17.0 kB | 19.5 kB | 480 kB |
| 8,192 | 64 | 19.0 kB | 24.0 kB | 34.9 kB | 960 kB |

So the honest description is "`O(k² log k)` larger than CF", and at `k = 64`
that is a doubling of the model — not "barely bigger".  The comparison that
matters is therefore **bytes versus fit**, not bytes versus bytes: CQF has to
out-perform re-spending the same 8–16 kB on a longer word list or a finer `k`,
which is the frontier measured in `WORDLIST_BUDGET.md` / `MODEL_BUDGET.md`.

### The experiment

1. Tokenise a held-out set with the canonical dictionaries (`V ∈ {512, 4096,
   8192}`), as `words_per_identifier.py` already does.
2. Cluster as now (`cluster_words.py`, Hellinger `k`-means, `k ∈ {32, 64}`),
   then **split each right cluster into `q` quarters** by running the same
   `k`-means inside the cluster (this is the "stop the tree early" step done
   geometrically, which is simpler than stopping Huffman and agrees with it up
   to the clustering metric).
3. Measure four lengths per identifier: arithmetic reference; flat Huffman
   (one tree per left cluster over `V` words — affordable for `V = 512`, and for
   `4,096` only as an upper-bound curiosity); CF (two trees); CQF for
   `q ∈ {2, 4}`.
4. Price each scheme with the size accounting above, then plot **total model
   bytes (word list + memberships + block + code lengths) against mean bits and
   against the 64/128-bit fit rates**, alongside the "spend the same bytes on
   more words / more clusters" frontier.
5. Decision rule: adopt CQF only if, at matched total bytes, it beats the best
   CF configuration on the *fit* rates — the quantity the product cares about —
   by more than the run-to-run noise of the frontier.  The measured upper bound
   on the gain is the CF penalty itself (1.4–1.6 bits/identifier), and CQF can
   only recover the word-step share of it.

## 6. Coding the assignment (a sketch)

The quarters are a fixed lattice imposed before the code is built; a better
design changes the clustering *and* the trees together.  The objective is

    minimise  Σ_b N(b) · len(code(b) | cluster(b))  +  λ · (model bytes)

over (assignment, per-cluster trees).  Given the trees, the assignment is a
facility-location problem; given the assignment, the trees are Huffman.  That is
coordinate descent, and it is cheap because the marginal cost of moving one word
between two clusters is computable exactly: the change in the two trees' Huffman
costs (from the two probability multisets) plus the (constant) membership bits.

Two structural notes for whoever implements it:

* Huffman is not a smooth function of the cell contents.  The assignment that
  minimises KL (what `k`-means does) is *not* the assignment that minimises code
  length: Huffman punishes a single large leaf in a cell (`p_max` is the
  redundancy bound), so a code-aware clustering will push the long tail into
  cells of its own and keep the heads together.  Expect the optimum to look
  "less Hellinger, more log-bucketed".
* Because the model bytes move in whole clusters (one more cluster costs
  `V·log₂((k+1)/k) ≈ V/k` bits of membership, about `2k` bits of block and `k`
  code lengths), the search is over a small integer grid (`k`, `q`); it is a
  frontier walk, not a gradient.

Walking before running: measure the *gap* between the current assignment's code
and the best code for that same assignment (that is the CF penalty, already
known), then the gap between that and the best code over all assignments of the
same number of cells (a local search from the `k`-means optimum).  The second
gap bounds what codesign can buy.

## 7. Open questions

* Which tables ship: word list, one or two cluster assignments, `D`, and the
  code lengths.  Does the standard fix `V`, `k` and the corpus, or publish a
  family?
* The reserved `\n` clusters (`NEWLINE_CLUSTER.md`) interact with this: a
  dedicated start/end cell makes the first and last trees tiny and exact, and
  removes the stop from the cells whose code lengths it currently distorts.
* If the code is published, the encoder must agree with the decoder on the
  *canonical* integer (the zero-padded code) — the standard should say so
  explicitly, because "any integer that decodes to the identifier" is not a
  bijection.
