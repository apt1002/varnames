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

Two conclusions carry into the design below: the remaining inefficiency is the
word step, which is what the quarter idea attacks — and, on *bits*, one tree per
left cluster over the joint is what to compare against.

**But the flat code cannot be published.**  Its table is `k` trees of `V` leaves:
224 kB at `(4,096, 32)`, 448 kB at `(4,096, 64)`, 960 kB at `(8,192, 64)`,
against 7.9–19 kB for the factorised project.  Publishing probabilities instead
of lengths does not rescue it (that is `k·V` bytes, 131 kB at `(4,096, 32)`).
So the choice splits on §3: if the standard ships the code, the flat code is out
and the design is **CF or CQF**; if the library derives codes at load time, the
flat code is free and CQF is buying back a loss that need not exist.  Since
publishing is the interoperable option, the honest reading is: **flat is the
yardstick, CF or CQF is the product.**  At `V = 512, k = 16` the flat table is
11 kB, so the shipped scheme can still be measured against the real thing at the
testing point.

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

Two notes on the accounting:

* **The bottom stage does not grow.** `2(V − qk)` instead of `2(V − k)` *saves*
  `2(q−1)k` bits — a few hundred bytes.  All of CQF's cost is in the top stage,
  which is `k·qk·log(qk)` — quadratic in `k`, and in `q` linear only up to the
  logarithm.  The increments over CF are 1.1 kB (`q = 2`) and 3.6 kB (`q = 4`)
  at `k = 32`, and 5.0 / 15.9 kB at `k = 64`: **`q = 4` costs about three times
  what `q = 2` costs**, and doubling `k` roughly quadruples both.  (An earlier
  draft said "a quarter"; that was wrong — `q = 2`'s top stage is 44 % of
  `q = 4`'s.)
* **`V log V` is right, and it is what makes the scheme work.**  An earlier draft
  of this note tried to charge `Σ_j V_j log V_j ≈ V log(V/qk)` instead and to add
  a separate word→cluster map.  That double-charges: with every leaf annotated by
  its word index, the *map is implied* — which tree a word's leaf sits in is its
  right cluster, and its position in that tree is its rank.  The decomposition is
  exact when the groups are equal-sized: `Σ_j V_j log V_j + V log q ≈ V log V`.
  The same reading applies to CF (`V log V` implies the word→right-cluster map),
  which is why the two schemes differ *only* through the top stage.

With the stated formulas:

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
2. Cluster as now (`cluster_words.py`, Hellinger `k`-means, `k ∈ {32, 64}`, and
   `k = 16` at `V = 512`), then form the quarters **only by truncating the
   build**: halt each right cluster's tree when `q` subtrees remain, and take
   those survivors as the quarters.  There is no freedom here, and that is the
   point (see "How the gain arises" below): an imposed partition — equal-mass
   quantiles, or `k`-means inside the cluster — forces the unequal merge *inside*
   a quarter, which is precisely the loss the truncation avoids.  Measure one
   imposed partition anyway, as a control that should lose; `k`-means inside the
   cluster is the natural one, since it also shows that a context-similarity
   criterion is not a code criterion.
3. **How the gain arises — and why the grouping is not a design choice.**
   Huffman's cost is the sum over merges of the merged mass, so the `q − 1`
   merges *above* the stop point are exactly what CQF replaces:

       in-cell loss avoided = Σ over the last q − 1 merges of the merged mass

   CQF replaces them with a top symbol shared across cells, costing
   `H(quarter | left cluster) + r_top`.  The trade works because a cell whose
   final merges are expensive is a cell with one heavy survivor and small
   siblings: the shared top tree lets that survivor pair with *other cells'*
   heavy survivors instead of with its own tail.

   Three consequences, all of which rule out imposing a partition:

   * If the survivors were equal in mass, finishing the build would cost exactly
     `log₂ q` bits per symbol — the cheapest a `q`-way split can be.  There would
     be nothing left for the shared tree to recover, and the extra stage would
     only add its own rounding.  Equal quarters are the one case where CQF
     *cannot* win, so "balance the quarters" is the wrong prescription.
   * Any imposed partition must merge unequal masses *inside* a quarter (a heavy
     word sharing a bottom tree with small ones), which reintroduces the loss in
     every quarter — the bottom trees are individually optimal for their groups,
     but the grouping is what costs.
   * The only design freedom is therefore `q` (and whether to ship quarters at
     all).  Where to stop is chosen by the build.

4. Measure four lengths per identifier: arithmetic reference; flat Huffman
   (one tree per left cluster over `V` words — affordable for `V = 512`, and for
   `4,096` only as an upper-bound curiosity); CF (two trees); CQF for
   `q ∈ {2, 4}`.
5. Price each scheme with the size accounting above, then plot **total model
   bytes (word list + memberships + block + code lengths) against mean bits and
   against the 64/128-bit fit rates**, alongside the "spend the same bytes on
   more words / more clusters" frontier.
6. Decision rule: adopt CQF only if, at matched total bytes, it beats the best
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

### A single-phase build: what actually gets modified

The question is whether the separation (cluster, then pair inside the cluster)
can be collapsed into one phase that chooses pairs partly on Hellinger distance.
It can, but it has to be at the level of **cells**, not codewords — and the two
levels need separating, because only one of them pays.

**Inside a tree the merge key is already optimal, and the geometry is absent.**
A per-cell tree's leaves are words and their weights are `p(b | cell) ∝ p(b)`,
the word's global frequency renormalised to the cell.  Huffman's "merge the two
least probable subtrees" is a theorem about that objective, so any other pairing
— including one that prefers contextually similar words as siblings — costs bits
and buys nothing: the block model `D` is where similarity is spent, and the tree
never sees context.  Two Hellinger-close words can have wildly different
frequencies, which is exactly the case Huffman wants to separate.

**One level up, the two greedy algorithms are the same shape.**  Both are
repeated "merge the cheapest pair" loops:

* Huffman's key is the merged mass; summed over merges it *is* the expected code
  length.  This is Huffman with `k = 1`.
* Hellinger/Ward `k`-means' key is the increase in within-cell distortion,
  which for centroids is `w_A w_B / (w_A + w_B) · H²(θ_A, θ_B)`.  This is the
  same loop with the code term switched off and `k` fixed.

So the codesign is a single merge loop that starts at `k = V` (each word its own
cell) and merges until it stops, with one compound key:

    Δ(A,B) =  λ_fit · [ w_A w_B / (w_A + w_B) ] · H²(θ_A, θ_B)     (block fit worsens)
            + λ_code · [ code length of A∪B  −  A  −  B ]           (one tree, not two)
            − [ model bits freed by one fewer cell ]                (≈ V log₂(k/(k−1)) + 3k)

Two consequences worth noting:

* **`k` stops being a sweep parameter.**  It is where merges stop paying.  Plain
  Hellinger clustering and plain Huffman are the two degenerate settings of λ.
* **The merge key can be evaluated exactly and cheaply.**  The entropy part of
  the code term is additive (`Σ p log p` is kept per cell), the Huffman
  redundancy is bounded by `p_max`, which is also kept per cell, so
  `Δcode ≈ [H(A∪B) + p_max(A∪B)] − [H(A) + p_max(A)] − [H(B) + p_max(B)]`,
  scaled by the token counts of the words involved.  The fit term's exact
  version (`Σ_a w_a D(p(·|a) ‖ pooled)`) is `O(|A|+|B|)` from cached row sums,
  and the Ward form above is its `O(1)` surrogate — use Ward in the heap, exact
  KL for the final acceptance test.  The heap-with-lazy-invalidation machinery
  is the one `tree_words.py` already uses for the most-frequent-pair merge.

The point of the compound key is *not* to let similarity override probability
inside a tree; it is to decide **which words share a tree**, which is the only
place the two objectives genuinely conflict.

**Why the tree build should *not* be modified.**  An earlier draft proposed
constraining the final merges so the `q` survivors come out near-equal in mass.
That is backwards: equal survivors are the case where finishing the build costs
only `log₂ q` bits, so there is no loss for the shared top stage to recover, and
forcing them perturbs the greedy grouping inside every quarter.  The surviving
subtrees must be whatever the greedy build produced — the inequality at the top
*is* the thing being sold.  What a codesign can legitimately change is which
words are in the same **cell** (§6 above), not how the tree inside a cell is
shaped.

**Walking (`scripts/codesign.py`, ~150 lines, reuses `cluster_words.py`):**

1. For an existing `k`-means assignment at `(V, k)`, build the real Huffman
   trees and record `Σ N(b)·len(b)` — the current code's cost.
2. Run the merge loop with `λ_fit = 0` (code + model only) down to the same `k`.
   If it does not beat the `k`-means cells on bits at matched `k`, codesigning
   has nothing to win and only the model side matters — a one-afternoon answer.
3. If it does, sweep `λ_fit` and let `k` fall out; compare the frontier with the
   `k`-means frontier at matched model bytes (the shape used in `SHARED_CLUSTERS.md`).
4. Independently of the loop, run the quarters accounting of §5 step 3: over
   every cell, sum the masses of the last `q − 1` merges (the in-cell loss that
   truncation avoids) and compare it with the top stage's charge for the same
   tokens (`H(quarter | left cluster)` plus a redundancy bound).  This needs no
   new code — only the merge masses, which the build already knows — and it
   says whether any `q` can pay before anything is built.  Do it first.

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
