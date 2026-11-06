# The testing vocabulary (`V = 512`): what it can and cannot show

> **Nothing is decided at the testing vocabulary.**  `V = 512` (`NUM_PAIRS`
> 448) exists to **exercise scripts** — to run a new measurement end to end on a
> model that builds in seconds and fits in memory.  It is not a smaller version
> of the product.  No accept/reject decision, no byte budget, no price and no
> frontier shape may be taken from it.  Every such claim in this repository is
> made at the **canonical grid** — `V ∈ {4096, 6144, 8192}` — and this file is
> where the `V = 512` numbers live so that they cannot be mistaken for them.

## Why `V = 512` misleads, in one number

The frontier is priced in **kB per point of fit<=64**, and the testing point and
the grid sit at very different prices:

| point | frontier price | a 256 B saving is worth |
|---|---:|---:|
| `V = 512`, `k = 16` | 0.47 kB/pt | 0.54 pt |
| `V = 4096`–`8192` | 4.3–4.6 kB/pt | 0.06 pt |

Per byte, the grid values a save *less*, by an order of magnitude — so the same
percentage saving is worth more at 512 if it is worth anything at all.  What
changes the verdict is the size of the model the percentage applies to: the
memberships are `2V·log₂k` bits, so dropping one of the two assignments frees
256 B at 512 (13% of a 1,980-byte model, 0.54 pt) and 2.5–6.1 kB at the grid
(15–17% of a 14–40 kB model, 0.6–1.4 pt), while the constraint that buys it
costs 1.2 pt of fit at 512 and only 0.1–0.6 pt once the clustering is fine
enough.  A small model therefore shows a *loss* on a
trade that is a *gain* at every canonical point — which is why a decision taken
here cannot be scaled up by argument, only re-measured.

Both experiments first run at this vocabulary were decided wrongly, in opposite
directions: the shared assignment was **rejected** here and is **above** the
frontier at the grid; the reserved stop was **accepted** here and is **rejected**
at the grid.  A reader who takes either `V = 512` verdict seriously gets the
product decision wrong.

**Temptation warning.**  The `V = 512` numbers are fast, pretty and complete, and
they form tidy tables that look like answers.  They are not answers.  If a
question can only be settled at 512, it is not settled.  Build the dictionary
(5–8 minutes) and measure at the grid.

## What the testing point *is* good for

* **Exercising a new script.**  Every harness in `scripts/` was smoke-tested
  here first: `shared_clusters.py`, `newline_cluster.py`, `quarter_accounting.py`,
  `quarter_codes.py`.  Bugs of the kind that produce absurd numbers at any size —
  a duplicated stop, a transposed index, a wrong byte formula — show up
  immediately, and the byte formulas can be checked against a hand-computable
  table (`V = 512, k = 16`: flat code 11,260 B, CF 888 B, CQF `q = 2` 1,140 B).
* **Checking a mechanism identity.**  CQF's claim that it recovers exactly the
  `q − 1` most expensive in-cell merges is an identity, so it can be verified at
  512 and used at the grid.  What does *not* transfer is the *fraction*.
* **Ground truth for a cheap model.**  The full `V × V` table is ~2 MB here, so
  the flat Huffman code is affordable and can serve as a yardstick that is not
  affordable at `V = 8192` (960 kB of code lengths).
* **A sample-0 twin.**  `work/tw512ns` pairs with `work/s0`-style builds, which
  is how the `--sample`/`--stride` split was validated without a 5-minute build.

## What it cannot support

Anything with the word "therefore": a byte budget, a frontier position, a
ranking of two schemes that differ by less than ~1 kB, an extrapolation of a
*fraction* or a *slope*, or a generative claim whose baseline moves with `V`
(mid-word chance is `1 − startable/V` = 5.9% at 512 and 8.6% at 8192).

---

# Measurements kept here

These are the `V = 512` results, moved out of the experiment reports.  The
reports now state only the canonical-grid result; the path back is a
cross-reference to this file.

## Shared cluster assignment (`work/tw512ns`, `k = 16`)

4,227 held-out identifiers (stride 100), `kappa = 300`, seed 1;
`scripts/shared_clusters.py --dir work/tw512ns --ks 16 --stride 100`.  One
label per word used as both `lcl` and `rcl`; `w` weights the successor side in
the concatenated Hellinger profile.

| model | k | bits | fit<=64 | fit<=128 | bytes | `D` asymmetry |
|---|---|---|---|---|---|---|
| full table | — | 53.134 | 77.0% | 97.8% | — | — |
| `asymmetric` | 16 | 68.105 | 57.1% | 93.7% | 1,980 | 1.33 |
| `shared`, `w = 1/√2` | 16 | 69.071 | 54.8% | 93.4% | 1,724 | 0.92 |
| `shared`, `w = 1` | 16 | **68.784** | 55.9% | 93.5% | 1,724 | 1.20 |
| `shared`, `w = √2` | 16 | 69.140 | 55.0% | 93.5% | 1,724 | 1.09 |
| `asymmetric` | 32 | 66.480 | 59.0% | 94.2% | 2,872 | 1.37 |

**The weight sweep vindicates the 1:1 default** — `w = 1` is the best of the
three, so the concatenation's equal weighting is not a handicap.  (At the
canonical grid the sweep has no consistent winner, but the default survives
there too.)

**The constraint costs 0.68 bits/identifier and 1.2 points of fit<=64**, in
exchange for 256 B (13% of the model).  The frontier slope at this point is read
off the `k`-doubling control: 892 B buys 1.63 bits, so 256 B is worth ~0.47 bits
— the shared model loses 0.68 and saves 0.47.  **Dominated at matched bytes**,
the margin (1.2 pt) being four times the ±0.3 pt noise band.

That verdict is an artefact of the vocabulary and it is the one that was carried
wrongly into the design note: the membership saving is the *smallest* case here
(13%, against 12–17% at the grid), while the bytes are worth four to ten times
less.  See
[`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md#measurement-at-the-canonical-grid) for
the grid result, which is the opposite.

## Reserving clusters for the stop token (`work/tw512ns`, `k = 16`)

Held-out: 2,114 validation identifiers (stride 200), `kappa = 300`; generation:
2,000 samples.  `scripts/newline_cluster.py --dir work/tw512ns --k 16
--stride 200`.  `plain(k)` clusters all `V` words into `k` clusters;
`reserved(k)` clusters the `V − 1` non-stop words into `k − 1` clusters and
appends a singleton `\n` cell on each side.

| config | bits | fit<=64 | fit<=128 | starts mid | ends mid | first-tok KL | last-tok KL | len (chars) | "real" |
|---|---|---|---|---|---|---|---|---|---|
| `plain(k)` | 67.725 | 57.1% | 93.7% | 3.0% | 2.2% | 0.300 | 1.170 | 16.66 | 1.45% |
| `plain(k-1)` | 67.766 | 57.3% | 93.7% | 3.0% | 2.1% | 0.292 | 1.161 | 16.32 | 1.75% |
| `reserved(k)`, `profile=sub` | 67.617 | 57.7% | 93.9% | 2.9% | **0.1%** | 0.488 | 1.195 | 16.05 | 2.45% |
| `reserved(k)`, `profile=full` | 67.703 | 57.2% | 93.8% | **2.1%** | **0.0%** | 0.311 | **1.096** | 16.82 | 2.40% |

Corpus values for the same held-out set: 9.14 tokens / 16.26 characters, digit
first-token mass 0.00%, last-token digit mass 5.58%.  Chance mid-word for a
unigram draw is `1 − 482/512` = 5.9%.

`profile=full` was adopted **here**, at this vocabulary: it keeps the stop's own
row and column inside each word's clustering profile, and it recovers the *start*
boundary (first-token KL 0.488 → 0.311, mid-word starts 2.9% → 2.1%) at no cost
in bits.  That is a script-level configuration choice, not a product verdict, and
it was carried forward to the grid — where it then failed to buy anything (see
`NEWLINE_CLUSTER.md`).

**The cost of the defect, and the table that would fix it.**  The two boundary
transitions cost 15.742 bits/identifier under `reserved(k)` and 15.676 under
`plain(k)`, against **14.912** if the stop's own row and column were stored
exactly — so an exact `2V`-number boundary table would recover 0.76–0.83
bits/identifier.  At `V = 512` that table is 1,024 B, i.e. ~1.9 bits on the
frontier slope, so it is **not** worth its bytes here either.  At the grid the
recoverable amount falls to 0.21–0.42 bits for 8 kB, which is a much worse deal.

### The defect does not survive larger `k`

`reserved(k)`, `profile=full`, 2,114 held-out identifiers, 1,500 samples:

| k | bits | fit<=64 | starts mid | ends mid | first-tok KL | digit mass | boundary table would recover |
|---|---|---|---|---|---|---|---|
| 16 | 67.703 | 57.2% | 2.1% | 0.0% | 0.311 | 1.91% | 0.83 bits |
| 32 | 66.056 | 59.8% | 0.5% | 0.2% | 0.220 | 0.02% | 0.38 bits |
| 64 | 63.624 | 63.0% | 0.3% | 0.1% | 0.180 | 0.02% | 0.08 bits |

The start-boundary defect is a **resolution** artefact, not a structural flaw:
once the right clusters are fine enough, the words that never start an identifier
separate on their own ("preceded by the stop" is the first entry of a word's
column profile, and `profile=full` puts it in the clustering metric).  This
conclusion — resolution, not structure — is the one that transferred; the
numbers are here.

### `reserved` vs `plain` at `k = 64` (diagnostic `k`)

| config | bits | fit<=64 | fit<=128 | starts mid | ends mid | first-tok KL | last-tok KL | digit |
|---|---|---|---|---|---|---|---|---|
| `plain(k)` | **63.227** | **63.7%** | 94.9% | 2.5% | 0.4% | 0.204 | 1.102 | 1.7% |
| `plain(k-1)` | 63.325 | 63.4% | 94.9% | 2.4% | 0.3% | 0.210 | 1.104 | 1.8% |
| `reserved(k)` | 63.624 | 63.0% | **95.0%** | **0.3%** | **0.1%** | **0.180** | **1.039** | **0.0%** |

The reservation costs 0.40 bits (0.6%) and 0.7 points of fit<=64, where at
`k = 16` it was free, and it cuts mid-word starts 8x, mid-word ends 4x and the
digit leak to zero.  **That trade read as "adopt" here and was reversed at the
grid**, where the freeze in bits became near-zero and the generative gain
disappeared with it.  The lesson: at a coarse vocabulary the reservation has
*room* to buy a boundary effect because the cells are coarse; at the grid the
cells are already fine enough that the marginal restriction costs nothing and
buys nothing.

Also visible here and *not* a reservation effect: the sampled length is ~1.8x
too long in every configuration (16.7 vs 9.1 tokens) — the units bug below — and
the "real identifier" hit rate is 1.5–2.5% (memorisation, not success).

## Correction: the generated length was a units bug

An earlier revision of `NEWLINE_CLUSTER.md` reported the model as generating
identifiers "3x too long".  That was wrong: `newline_cluster.py` compared the
length of the generated *string* in characters against the corpus length in
*tokens*.  The mis-step is recorded here, with its numbers, rather than in the
report.  Matched units, `V = 512`, `k = 16`, 3,000 samples:

| config | tokens (corpus 9.14) | chars (corpus 16.26) |
|---|---|---|
| `plain(k)` | 8.37 | 16.61 |
| `plain(k-1)` | 8.14 | 16.23 |
| `reserved(k)`, `profile=full` | 8.38 | 16.67 |

The length distribution is in fact reproduced well — 2% long in characters, 8%
short in tokens, 95th percentile slightly heavy (24 vs 18 tokens).  The penalty
of the factorisation is 8% on the token mean, not a factor of three.

## CQF accounting (`V = 512`, `k = 16`)

`scripts/quarter_accounting.py` computes the three layouts exactly from the
counts — no sampling, no held-out set — as Huffman costs (so the rounding is
real, not modelled).  3.82M identifiers, 35.1M transitions (9.20 per
identifier), `kappa = 300`.

| scheme | bits/identifier | vs flat | model bytes |
|---|---:|---:|---:|
| flat (yardstick) | **65.371** | — | 11,260 |
| CF | 69.250 | +3.878 | 888 |
| CQF `q = 2` | 68.548 | +3.177 | 1,140 |
| CQF `q = 4` | 68.072 | +2.701 | 1,708 |

Mechanism, checked to three decimals against the identity:

| q | top stage | CF cluster step | increase | merges avoided | net | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 32.689 | 24.207 | +8.482 | 9.184 | **+0.702** | +252 |
| 4 | 40.470 | 24.207 | +16.263 | 17.440 | **+1.177** | +820 |

The Huffman rounding on the flat trees is 0.034 bits/token (0.31 per identifier),
so these are essentially rounding-free: the `kappa` prior makes every cell
non-zero, which is why Huffman is so efficient here.

CQF recovers **18% (`q = 2`) and 30% (`q = 4`)** of the flat → CF penalty *at
this vocabulary*.  Both the penalty (3.878 bits because 16 clusters is coarse)
and the fraction are properties of the coarse grid; at `V = 4096` the penalty is
2.3–3.0 bits and the recovered fraction is 35–43%.  The extrapolation from these
two fractions was wrong in both terms — see `ENCODING.md` §5, which now carries
the grid numbers only.

## The code comparison at the testing point

`scripts/quarter_codes.py` scored this point once, and the paired test is worth
keeping because it shows the two metrics disagreeing:

| comparison | bits vs CF (paired) | fit<=64 vs CF (paired) |
|---|---:|---:|
| CQF `q = 2` (or any CQF) | −0.677 ± 0.056 | +0.6 ± 0.5 pt |

A bits gain that does not show up as fit points, because the mean sits well
below the 64-bit threshold — a small-vocabulary property.  At `V = 4096/8192`
the mean sits nearer the threshold and the same comparison shows a clear fit
gain.  Do not read this row as "CQF does not pay".
