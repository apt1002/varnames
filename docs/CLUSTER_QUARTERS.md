# Cluster quarters

**`q = 1` ships.  This note is the refutation of `q > 1`.**  A quarter is *any*
finer right cluster: splitting a left cluster's word tree into `q` right
clusters.  The name is historical — `q = 2` gives halves.  The idea changes the
top stage from `k` leaves to `q·k` and leaves the encoder untouched
([`ENCODING.md`](ENCODING.md) §§2–4).  It works, it is cheap to implement, and
`MODEL_FORMAT.md` keeps `q` for that reason.  It does not pay: measured in the
packed file, `q = 2` buys 0.12 bits per identifier for 1,536 B at the operating
point — 13 kB per bit, against a frontier that sells bits for 3–5
([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6).  The arithmetic accounting that
used to be quoted here credited it 1.10 bits for about 1.2 kB; the bits were
overstated by a factor of nine, and this note records why.

## The idea

The factorised model needs `P(right cluster | left cluster)` before
`P(word | right cluster)`.  The flat model needs a tree per left cluster over
all `V` words — `k·V` code lengths, 98 kB at `V = 8,192, k = 16`, which is out
of the question.

The idea: **stop each word tree early.**  Build the tree for
`P(word | right cluster)` and halt the merge when `q` survivors remain.  Then
encode `P(right cluster | left cluster)` with a tree of `q·k` leaves.  Each of
the `k` left clusters gets its own top tree, so right clusters from *different*
left clusters can be paired when their probabilities are similar — which is
exactly the pairing the two-level factorisation cannot do.

## Why it was expected to pay

The mechanism is the classical Huffman redundancy bound: a tree's expected
redundancy is at most about its largest leaf probability, plus a small constant.
Splitting a right cluster into `q` pieces divides its largest leaf probability
by up to `q`, so the word-step penalty should shrink, while the cluster-step
penalty hardly moves.

The effect is real and measurable.  Truncating a tree at `q` leaves does not
make it incomplete: the words inside a survivor all take the survivor's depth,
so the tree stays exact and its Kraft sum is 1 — checked on every one of the 32
trees of the `q = 2` build at 8192/16.  What changes is where the resolution
sits.  Inside a survivor the words are coded *uniformly* at the cut depth, so
the word step gets coarser; the cluster step gets finer, because the top stage
now predicts which quarter rather than which right cluster.  The quarters
therefore **move** resolution from the word stage to the cluster stage, and the
question is only whether the move is worth its bytes.

## What the format pays: two objects, exactly

The cost is not a formula, it is two tables:

* **The map widens.**  One label per word at `⌈log₂ k·q⌉` bits instead of
  `⌈log₂ k⌉`: +1,024 B at `V = 8,191` at both `k` (4 → 5 bits at `k = 16`,
  and 5 → 6 bits at `k = 32`).
* **The top stage grows as `k·(k·q + 1)`.**  From `k(k+1)` depths to `k(kq+1)`:
  +128 B at `k = 16` (272 → 528 depths) and +512 B at `k = 32` (1,056 → 2,080),
  both at the 4-bit field the format uses.

Nothing else moves: the rules are the same word list, the bottom depths are the
same `V` rows, the alphabet is the same.  So the price of `q = 2` is 1,152 B at
`k = 16` and 1,536 B at `k = 32`, and it is exact — these are byte counts from
packed files.

## What it buys: measured

`scripts/model_size.py --q 2`, stride 10 (42,268 held-out identifiers), seed 1,
the same dictionary directory as the shipped point:

| point | `q` | model file | rules | map | top depths | bits/id | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 8192/16 | 1 | 29,329 B | 20,926 | 4,096 | 136 | 45.677 | 84.5 % | 98.9 % |
| 8192/16 | 2 | 30,481 B | 20,926 | 5,120 | 264 | 45.559 | 84.8 % | 99.0 % |
| 8192/32 | 1 | **30,745 B** | 20,926 | 5,120 | 528 | **45.218** | **85.0 %** | **99.0 %** |
| 8192/32 | 2 | 32,281 B | 20,926 | 6,144 | 1,040 | 45.100 | 85.1 % | 99.0 % |

Priced the way every other decision in this project is priced — against the
frontier's own slope at the same size (`MODEL_BUDGET.md` §6, which is 3–5 kB per
bit and 2.9–3.0 kB per fit point at these points):

| point | `q = 2` costs | buys | per bit | buys | per point |
|---|---:|---:|---:|---:|---:|
| 8192/16 | +1,152 B | 0.118 bits | 9.8 kB | +0.3 pt | 3.8 kB |
| 8192/32 | +1,536 B | 0.118 bits | **13.0 kB** | +0.1 pt | **15.4 kB** |

Three readings:

* **It buys the bits it promised, and they are not worth the bytes.**  The gain
  per identifier is 0.12 bits at both `k`, which is a third of what the earlier
  accounting claimed (1.10) and half of what the arithmetic-coded estimate of
  the same tables gave.  At 14 kB per bit the quarters are 3–5× too dear.
* **The operating point is not the place to argue about it.**  At `k = 32` the
  gain is 0.1 fit point for 1,536 B; the frontier buys 0.5 points for 1,474 B
  (8192/16 → 8192/32), and every point of the measured curve is cheaper than
  that.  `q = 2` is dominated at the point that ships.
* **At `k = 16` it is close on fit rate and not on bits** (3.9 kB/pt against the
  frontier's 3.0, but 10 kB/bit against 3.3).  A model that was priced on fit
  rate alone and stopped at `k = 16` would have had to look twice.  The reason
  it still loses is the same one that makes the quarters attractive at all: the
  top stage is quadratic in `k`, so the fit gain per byte falls as `k` grows,
  and the model that ships is at `k = 32`.

## Why the refund disappeared

The arithmetic accounting adopted `q = 2` on the strength of 0.9 fit points for
about 1.2 kB, and the arithmetic-coded measurement of the same tables still gave
it 1.10 bits.  Almost
all of that was the terminator.  Both codes were paying for the end of an
identifier there: the old bottom trees carried a zero-weight stop leaf and the
old top stage carried the stop's right cluster, so the word step was priced with
a terminator inside it.  Refining the word tree also refined the terminator's
cost, and that was the bulk of the gain.

With the terminator on the top stage's zero-weight STOP leaf
([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §§1–3) both codes get the end of the
identifier for free, and what remains is the word-stage granularity the quarters
actually buy: 0.12 bits.  The lesson generalises past this note — an accounting
that charges a terminator to the word step will over-reward every scheme that
refines the word step.

## The claim that survives: it refines one side only

`q > 1` splits the *right* clusters, which is the word step's side.  The other
side of the factorisation has the same rounding loss and no analogous repair:
the left clusters are what the top stage conditions on, and making them finer is
just a larger `k`.  So the quarters are a partial answer to a question the
`k` sweep already answers better, which is the structural reason they lose to
the frontier rather than a defect in the implementation.

## Not done

* **`q = 4`.**  It costs three times what `q = 2` does (`k(kq+1)` depths) to buy
  a fraction of a bit more, and `q = 2` is already 3–5× too dear.  Priced at
  `q = 2` and rejected by extrapolation; not built.
* **Quarters on the left side** (finer top trees without a wider map) — there is
  no such object: the top stage's leaves are the right clusters, so refining it
  *is* splitting them.
* **A non-uniform code inside a survivor.**  That is the full word tree, i.e.
  `q = 1`.
