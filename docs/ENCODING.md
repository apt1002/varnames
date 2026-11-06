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

| `V` | `k` | CF | CQF (`q = 2`) | CQF (`q = 4`) | W |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 32 | 8,048 | 9,192 | 11,736 | 229,368 |
| 4,096 | 64 | 11,232 | 16,336 | 27,568 | 458,736 |
| 8,192 | 32 | 16,240 | 17,384 | 19,928 | 491,512 |
| 8,192 | 64 | 19,424 | 24,528 | 35,760 | 983,024 |

(bytes, exact; the earlier draft of this table quoted rounded kB and was off
by up to 0.8 kB in the CQF columns)

So the honest description is "`O(k² log k)` larger than CF", and at `k = 64`
that is a doubling of the model — not "barely bigger".  The comparison that
matters is therefore **bytes versus fit**, not bytes versus bytes: CQF has to
out-perform re-spending the same 8–16 kB on a longer word list or a finer `k`,
which is the frontier measured in `WORDLIST_BUDGET.md` / `MODEL_BUDGET.md`.

### The accounting check, run

`scripts/quarter_accounting.py` computes the three layouts exactly from the
counts — no sampling, no held-out set — as Huffman costs (so the rounding is
real, not modelled).  `V = 512`, `k = 16`, `kappa = 300`, 3.82M identifiers,
35.1M transitions (9.20 per identifier):

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **65.371** | — | 11,260 |
| CF | 69.250 | +3.878 | 888 |
| CQF `q = 2` | 68.548 | +3.177 | 1,140 |
| CQF `q = 4` | 68.072 | +2.701 | 1,708 |

and the mechanism, checked to three decimals against the identity above:

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 32.689 | 24.207 | +8.482 | 9.184 | **+0.702** | +252 |
| 4 | 40.470 | 24.207 | +16.263 | 17.440 | **+1.177** | +820 |

The Huffman rounding on the flat trees is 0.034 bits/token (0.31 per
identifier), so these are essentially rounding-free numbers: the `kappa` prior
makes every cell non-zero, which is why Huffman is so efficient here.

**Two conclusions.** The mechanism is real — CQF recovers 18% (`q = 2`) and 30%
(`q = 4`) of the flat → CF penalty, and the amounts are exactly the expensive
in-cell merges.  But the *fraction* is measured where the penalty is large: at
`V = 512, k = 16` the penalty is 3.878 bits/identifier because 16 clusters is
coarse.  An earlier draft guessed that the canonical-grid penalty would be
~1.2 bits/identifier, so that the same fractions would recover only ~0.22
(`q = 2`) and ~0.36 (`q = 4`) bits.  **That guess was wrong in both terms**, and
it was wrong in a way that matters: at the canonical grid the penalty is
*larger* (2.3 bits at `k = 32`, 3.0 at `k = 64`) and the recovered fraction is
*larger* too (35–43%), because the in-cell merge mass is nearly independent of
`k` while CF's cluster step is not.

The same check at the canonical grid (`V = 4096`, `k = 32`, 4.02M identifiers,
22.9M transitions) is **better**, not worse:

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **50.122** | — | 229,368 |
| CF | 52.426 | +2.304 | 8,048 |
| CQF `q = 2` | 51.615 | +1.493 | 9,192 |
| CQF `q = 4` | 51.480 | +1.358 | 11,736 |

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 22.948 | 18.055 | +4.893 | 5.704 | **+0.811** | +1,144 |
| 4 | 27.563 | 18.055 | +9.508 | 10.454 | **+0.946** | +3,688 |

So CQF recovers **35% (`q = 2`) and 41% (`q = 4`)** of the flat → CF penalty
here, against 18% and 30% at `V = 512, k = 16`.  The extrapolation in the earlier
draft (which assumed the smaller fractions) is therefore too pessimistic: the
word step is 66% of CF's cost (34.371 of 52.426) and the expensive in-cell merges
are a larger share of it at the canonical grid.

The `k = 64` cell (`V = 4096`, 4.02M identifiers) completes the picture:

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **49.328** | — | 458,736 |
| CF | 52.306 | +2.979 | 11,232 |
| CQF `q = 2` | 51.035 | +1.707 | 16,336 |
| CQF `q = 4` | 50.806 | +1.478 | 27,568 |

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 25.851 | 21.421 | +4.430 | 5.702 | **+1.272** | +5,104 |
| 4 | 30.171 | 21.421 | +8.751 | 10.251 | **+1.500** | +16,336 |

Two things to note, both against the earlier expectation:

* **The in-cell merges are `k`-independent** — 5.704 / 10.454 at `k = 32`,
  5.702 / 10.251 at `k = 64`.  They are a property of the tail of each cell's
  word distribution, not of how many cells there are.  So the recovery
  *fraction* rises with `k` (35% → 43% for `q = 2`), because the penalty it is a
  fraction of grows (CF's cluster step 18.055 → 21.421 while the word step only
  falls 34.371 → 30.886).
* **The top stage increase is `k`-*sub*linear**: 4.893 → 4.430 for `q = 2` even
  though the top tree grows from 32 to 64 leaves.  It is charged as
  `H(quarter | L) − H(cluster | L)`, and the extra quarter distinction bites
  less once the cells are already fine.

Against bytes, though, the story is unchanged: the top stage is `k x kq`, so the
byte cost of the same 1.27 bits is 4.5x what it was at `k = 32`.

**Priced against the frontier**, using the slope measured two independent ways on
the canonical grid — `k`: 32 → 64 at `V = 4096` costs 4,088 B and buys 0.733
bits; `V`: 4,096 → 8,192 at `k = 64` costs 18,432 B and buys 3.34 bits — both
give **≈5.5 kB per bit**:

| config | CQF bytes over CF | bits it buys | bits the same bytes buy elsewhere | net |
|---|---:|---:|---:|---:|
| 4096, k=32, q=2 | +1.1 kB | **0.81** | 0.21 | **+0.60** |
| 4096, k=32, q=4 | +3.6 kB | **0.95** | 0.67 | +0.28 |
| 4096, k=64, q=2 | +5.0 kB | **1.27** | 0.91 | **+0.36** |
| 4096, k=64, q=4 | +16.0 kB | **1.50** | 2.89 | −1.39 |

So **CQF pays at `k = 32`**: `q = 2` comfortably (+0.60 bits equivalent), `q = 4`
marginally (+0.28).  At `k = 64` both `q = 2` (+0.36) and `q = 4` (−1.39) get
worse, but not for the reason guessed earlier: the bits it buys *grow* (1.27,
1.50) and the bytes grow faster.  Per kilobyte the buy is 0.71 bits/kB at
`k = 32, q = 2`, 0.25 at `k = 64, q = 2`, 0.09 at `k = 64, q = 4`, against a
frontier of ~0.18.  So `q = 2` is above the frontier at both `k`, by 4x and by
1.4x; `q = 4` is above it only at `k = 32`, by 1.5x.

These are Huffman costs on the *training* counts, so they are optimistic and
they carry no fit rate.  The decision rule is stated in fit rates, so the codes
were built and scored on held-out identifiers — that is the next section.

### The measured codes, held-out

`scripts/quarter_codes.py` constructs the three codes from the training counts
and scores them on `merged_validation.txt` (4,227 identifiers at stride 100,
mean 4.70 tokens against 5.70 in the corpus — held-out identifiers are shorter,
so bits/identifier are not comparable *across* corpora, but every comparison
inside a cell is paired on the same identifiers).

`V = 4096, k = 32`:

| scheme | bits/id | vs flat | fit<=64 | fit<=128 | model bytes |
|---|---:|---:|---:|---:|---:|
| flat (yardstick) | **49.489** | — | 81.3% | 98.4% | 229,368 |
| CF | 51.936 | +2.448 | 78.2% | 98.1% | 8,048 |
| CF, decoded arithmetically | 51.070 | +1.581 | 78.6% | 98.0% | 8,048 |
| CQF `q = 2` | 51.069 | +1.580 | **79.5%** | 98.2% | 9,192 |
| CQF `q = 4` | 50.962 | +1.473 | 79.3% | 98.2% | 11,736 |
| `ref` (exact `P(v\|u)`) | 42.135 | −7.354 | 90.5% | 99.5% | 2,102,784 |

`V = 4096, k = 64`:

| scheme | bits/identifier | vs flat | fit<=64 | fit<=128 | model bytes |
|---|---:|---:|---:|---:|---:|
| flat | 48.624 | — | 82.7% | 98.6% | 458,736 |
| CF | 51.749 | +3.125 | 78.9% | 98.0% | 11,232 |
| CF, decoded arithmetically | 50.337 | +1.713 | 79.8% | 98.1% | 11,232 |
| CQF `q = 2` | 50.432 | +1.808 | 80.0% | 98.3% | 16,336 |
| CQF `q = 4` | 50.196 | +1.573 | **80.5%** | 98.2% | 27,568 |
| `ref` | 42.135 | −6.489 | 90.5% | 99.5% | 2,102,784 |

`V = 8192, k = 64`:

| scheme | bits/identifier | vs flat | fit<=64 | fit<=128 | bytes |
|---|---:|---:|---:|---:|---:|
| flat | 45.949 | — | 85.8% | 98.9% | 983,024 |
| CF | 48.370 | +2.420 | 83.6% | 98.6% | 19,424 |
| CQF `q = 2` | 47.255 | +1.306 | 84.1% | 98.7% | 24,528 |
| CQF `q = 4` | 47.137 | +1.188 | **84.4%** | 98.7% | 35,760 |
| `ref` | 39.986 | −5.963 | 92.6% | 99.6% | 8,400,896 |

(the arithmetic row was not measured at `V = 8192`; the 4096 cells are enough to
settle what it is for)

Four readings:

* **The codes generalise and the accounting was honest.** Held-out is within
  ~0.5 bits of the training-count Huffman cost in every cell (CF 51.936 vs
  52.426 at `k = 32`), and the recovered fraction is the predicted one: 35% and
  40% at `k = 32` against the accounting's 35% / 41%; 42% / 50% at `k = 64`
  against 43% / 50%.  Nothing here is a training artefact.
* **The code is worth a point on the threshold, not on the mean.** At
  `4096, k = 32` CQF `q = 2` and *arithmetic* decoding of the same tables have
  the same mean (51.069 vs 51.070, paired `−0.868 ± 0.023` against CF's
  `−0.866 ± 0.022` for arithmetic), but their fit rates are not the same:
  **79.5% against 78.6%**, i.e. `+1.3 ± 0.2` against `+0.4 ± 0.2` points.  So
  CQF is *not* "the two-stage Huffman code catching up to its own entropy" — an
  arithmetic decoder already does that, and it costs nothing in bytes.  CQF
  reshapes the cost distribution: Huffman lengths are not `−log₂ P`, they are
  short for the heavy symbols of a quarter and long for the rare ones, which
  pulls identifiers toward the threshold even at the same mean.  At `k = 64` the
  effect reverses (`+1.0` for CQF against `+0.9` for arithmetic, at 5.1 kB), so
  the threshold gain is a `k = 32` phenomenon.
* **Mean bits and fit rates disagree in general.** At `4096, k = 32` `q = 4` has
  *fewer* mean bits than `q = 2` (50.962 vs 51.069) but *worse* fit (79.3% vs
  79.5%) at 3.2x the bytes; at 8192 the ordering is the other way (84.4% vs
  84.1%).  The differences are small, which is the point: a 0.1-bit mean gain
  does not reliably move a threshold count, so the choice between `q = 2` and
  `q = 4` should be made on fit rates per byte and then defaulted to the cheaper
  code.
* **The arithmetic bound is far away.** `ref` is 7.35 bits below flat at
  `V = 4096`, for a `V x V` table of 2.1 MB.  The flat → CF penalty CQF attacks
  (2.4–3.1 bits) is therefore only a fraction of what the factorisation loses
  overall; the rest is within-cluster resolution on both sides, which is a `k`
  question and not a quarters question.  CQF recovers most of *the CF penalty*,
  not most of the gap to optimal.

**Priced in fit rates** (CQF's byte delta over CF is the code-only accounting of
the tables above; the local frontier slope is the best measured neighbour in the
same accounting):

| config | fit<=64 | vs CF | bytes over CF | kB per point | local frontier |
|---|---:|---:|---:|---:|---:|
| 4096, k=32, q=2 | 79.5% | **+1.3** | +1,144 | **0.9** | 5.8 (k), 3.9 (V) |
| 4096, k=32, q=4 | 79.3% | +1.1 | +3,688 | 3.4 | |
| 4096, k=64, q=2 | 80.0% | +1.1 | +5,104 | 4.6 | 14.8 (k 64→128) |
| 4096, k=64, q=4 | 80.5% | +1.6 | +16,336 | 10.2 | |
| 8192, k=64, q=2 | 84.1% | +0.5 | +5,104 | 10.2 | 14.8 (k 64→128) |
| 8192, k=64, q=4 | 84.4% | +0.8 | +16,336 | 20.4 | |

The decision rule of step 6 is "adopt only if, at matched total bytes, it beats
the best CF configuration on the fit rates by more than the frontier's noise".
Stated as domination, which avoids the interpolation entirely:

| pair | CQF option | CF option | winner |
|---|---|---|---|
| `V = 4096` | `k = 32, q = 2`: **79.5%** at 18,544 B | `k = 64`: 78.9% at 21,488 B | CQF, by 0.6 pt and 2.9 kB |
| `V = 4096` | `k = 64, q = 2`: **80.0%** at 26,592 B | `k = 128`: 79.8% at 34,784 B | CQF, by 0.2 pt and 8.2 kB |
| `V = 8192` | `k = 64, q = 2`: **84.1%** at 45,024 B | `k = 128`: 83.6% at 54,240 B | CQF, by 0.5 pt and 9.2 kB |

The comparator here is the Huffman product.  Against *arithmetic* decoding at
`k = 64` (79.8% at 21,488 B) the `k = 32, q = 2` code (79.5% at 18,544 B) is
0.3 pt behind but 2.9 kB cheaper — 9.7 kB per point, worse than the frontier, so
those 0.3 points are not worth buying back.

So CQF `q = 2` is **adopted**: it buys a fit point more cheaply than doubling
`k`, at both canonical vocabularies, and at `k = 32` it is 3–6x cheaper than the
frontier.  `q = 4` is **rejected**: at `k = 32` it is dominated by `q = 2` (less
fit, 3.2x the bytes), and at `k = 64` it costs 10–20 kB/pt against a 15 kB/pt
frontier — inside the noise, at 3.2x the price.

**What it is worth against the free alternative.** Decoding the same
factorisation arithmetically costs *no* extra bytes and recovers the same mean
bits, so the honest comparison for CQF is not against CF but against arithmetic:

| | CQF `q = 2` fit | arithmetic fit | CQF's margin | bytes | kB per point |
|---|---:|---:|---:|---:|---:|
| 4096, k=32 | 79.5% | 78.6% | **+0.9 pt** | +1,144 | 1.3 |
| 4096, k=64 | 80.0% | 79.8% | +0.2 | +5,104 | 26 |

So CQF is a **`k = 32`, `q = 2`, Huffman-only** optimisation: worth ~0.9 fit
points there at 1,144 B — still 3x cheaper per point than the cheapest `k`
segment (2.8 kB/pt) — and worth nothing at `k = 64` once arithmetic decoding is
admitted.  Since `ENCODING.md` §1–3 chooses code lengths over probabilities for
the decoder's sake, this is a real and conditional gain: it exists *because* the
product is a Huffman product.

**The noise, measured.** These are proportions over 4,227 identifiers, so the
right yardstick is the *paired* per-identifier difference (same held-out
identifiers, same trees below the top stage).  At `V = 4096, k = 32`:

| comparison | bits | fit<=64 |
|---|---:|---:|
| flat − CF | −2.448 ± 0.047 | +3.1 ± 0.3 pt |
| arithmetic − CF | −0.866 ± 0.022 | +0.4 ± 0.2 pt |
| CQF `q = 2` − CF | −0.868 ± 0.023 | **+1.3 ± 0.2 pt** |
| CQF `q = 4` − CF | −0.974 ± 0.025 | +1.0 ± 0.2 pt |
| `ref` − CF | −9.801 ± 0.176 | +12.3 ± 0.5 pt |

and at `k = 64`: arithmetic `−1.412 ± 0.020` / `+0.9 ± 0.2`; CQF `q = 2`
`−1.317 ± 0.023` / `+1.0 ± 0.2`; CQF `q = 4` `−1.553 ± 0.026` / `+1.6 ± 0.2`.

So the `k = 32` claim is solid on both statistics: 6σ in fit rate, 38σ in bits.
The unpaired binomial standard error would have been 0.6 pt, which is why the
paired form matters — it is three times tighter, because almost all identifiers
sit far from the threshold and the ones that flip are a small correlated set.

Two honesty notes on the domination table, whose margins are 0.2–0.6 pt: those
are *cross-model* differences (a different code for a different `k`), so their
sampling error is the unpaired one, ~0.6 pt, and individually they are not
significant.  What is significant is the bits gap they are built from
(`−0.868 ± 0.023` here), and the fact that the fit ordering agrees with the bits
ordering in all three cells.  And at `V = 512, k = 16` the same test gives
`−0.677 ± 0.056` bits but only `+0.6 ± 0.5` fit points: a bits gain that does not
show up in a 64-bit threshold count, which is a good reminder that the two
metrics can disagree when the mean sits well below the threshold.

A larger held-out set (`--stride 10`, ~42k identifiers) would tighten all of
this by `sqrt(10)` at negligible cost, and is the right setting for the H6
re-measurement.

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

   CQF replaces them with a top symbol shared across cells.  Careful with the
   comparison: the top stage is not *new* — CF already pays a cluster step of
   `H(right cluster | left cluster)`.  What CQF pays is the **increase** from `k`
   to `kq` symbols, `H(quarter | left cluster) − H(right cluster | left
   cluster)` plus its rounding.  So the net is

       recovered − (top stage increase)

   and quoting `H(quarter | left cluster) + r_top` as the cost overstates it,
   because it charges the whole top stage rather than its increment.  The trade works because a cell whose
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
  which for centroids is `w_A w_B / (w_A + w_B) · ‖θ_A − θ_B‖²`, and
  `‖√p − √q‖² = 2H²`.  This is the same loop with the code term switched off
  and `k` fixed.

So the codesign is a single merge loop that starts at `k = V` (each word its own
cell) and merges until it stops, with one compound key:

    Δ(A,B) =  λ_fit · [ w_A w_B / (w_A + w_B) ] · 2H²(θ_A, θ_B)    (block fit worsens)
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

### A merge-loop formulation (proposal, under discussion)

An alternative to the coordinate descent above: make the clusters *be* Huffman
trees and alternate the usual two phases — recompute each cluster's centroid
(the **normalised mean of the `√p` vectors**, not `√` of the mean), then rebuild
the partition by merging.  Phase 2 repeatedly takes the globally least probable
remaining tree `t` and merges it into the cluster minimising

    [Hellinger cost of moving t there]  +  [Δ_CS of the merge]

Two results are worth keeping, whichever way the design goes:

* **The merge cost has a closed form.**  With `a`, `b` the two trees' masses,

      Δ_CS = (a + b)·(1 − h₂(a/(a+b))),      h₂ = binary entropy in bits

  and in any base `b`, `Δ_CS = (a+b)(log_b 2 − h_b(a/(a+b)))` — "one unit of
  log 2 minus the binary entropy" — so the identity is base-free; the numbers
  below are in bits because the code lengths and the fit rates are.

  i.e. zero exactly when the masses are equal, maximal when one is zero, and
  *increasing in the partner's mass*.  Consequences: with the Hellinger term
  switched off the rule is exactly Huffman; and at a fixed point, where the
  Hellinger term is the same for every partner inside the chosen cluster, the
  tree built inside each cluster is the Huffman tree for that cluster.  That is
  the necessary condition, and it holds.
* **The fit term can only override close mass ratios.**  As bits per occurrence
  of `t`, `Δ_CS/a = (1 − h₂(θ))/θ`.  The fit term as proposed is `N(t)·(2H)²`
  (the metric that approximates the KL, §"Calibration" below), which saturates
  at 4 — 5.8 bits — when the supports are disjoint.  Break-even mass ratios:
  1.4:1 for a 0.05-bit fit, 2:1 for 0.25 bits, 9.5:1 even for maximally
  dissimilar clusters.  So the fit decides only between partners of similar
  mass and the resulting clusters are **mass-stratified** — they overlap in
  Hellinger space by construction.

  That is not automatically fatal: a *quarter* is a code-only refinement (the
  block `D` stays `k × k`), so quarters may overlap almost perfectly and cost
  nothing, whereas a codesigned cluster *is* the block model's cell, so its
  overlap is charged through `D`.  The budget for the whole idea is therefore
  the factorisation penalty itself — the 1.2 bits/identifier between the flat
  and two-tree codes — and any fit damage larger than that is a net loss.

Calibration, which is where the factor of two lives: `(2H)² ≈ KL` **in nats**.
For `p ≈ q` the second-order expansion gives `KL(nats) ≈ ½Σ(p−q)²/q`,
`2H² = ‖√p − √q‖² ≈ ¼Σ(p−q)²/q` and `(2H)² ≈ ½Σ(p−q)²/q`, so `(2H)²` is the KL
in nats and `2H²` is exactly half of it.  In **bits**, `KL ≈ (2H)²/ln 2 =
1.4427·(2H)²`.  So a fit term written as `(2H)²` and a code term in bits are
not in the same units: multiply the fit by 1.4427, or — better — calibrate it
against measured block-model bits, since the proxy is only exact for nearby
distributions.  (The `2H²` used for the *geometry* — the Ward key and the
`k`-means centroid — is the squared embedding distance, a different quantity,
exactly half of `(2H)²`; the constant does not matter there because it does not
move an argmin.)

Open: no descent proof between passes (phase 2 assigns trees greedily in mass
order, so the previous partition is only reproducible at a fixed point), and a
cluster reduced to one tree has no stay-put option.  A fixed point is
self-consistent; monotonicity is empirical.

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
