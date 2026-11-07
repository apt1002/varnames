# One cluster assignment for both sides

Status: **adopted at `k = 32`; neutral at `k = 64`.**  Over five seeds on the
10x held-out set the shared model sits 0.34 pt above the asymmetric frontier at
matched total bytes when `k = 32`, and exactly on it when `k = 64`.  A first
measurement at the testing vocabulary (`V = 512`) rejected it; that measurement
is a statement about a cheap model, not about the constraint, and it now lives
in [`SMALL_DICT.md`](SMALL_DICT.md) with the rest of the testing-point numbers.
The decision rule that reads the result is spelled out below.  The shipped
build keeps the constraint at `q = 1`: the file stores one label per word, the
right cluster, and the left cluster is that label divided by `q` — the label
itself at `q = 1` (`CLUSTER_QUARTERS.md`, `MODEL_FORMAT.md` §1).  Measured in
the packed file the constraint is cheaper than the accounting thought: at
`k = 32` the omitted second map is worth 0.03 bits for 5,120 B.

## The question

The co-clustered model stores two assignments: every word gets a **left**
cluster (from its successor distribution, `p(·|a)`) and a **right** cluster
(from its predecessor distribution, `p(a|·)`).  Can one assignment serve both
sides, at `k` clusters for the whole vocabulary?

## Why it might pay

The membership table is the second-largest object in the model after the word
list.  Two memberships cost `2V·log₂k` bits; one costs `V·log₂k`, and nothing
else changes: the block `D` is `k × k` either way, and the unigram is untouched.

At the canonical grid:

| model | membership, two sides | one side | saving |
|---|---:|---:|---:|
| `V = 4,096`, `k = 32` | 5,120 B | 2,560 B | 2.5 kB |
| `V = 4,096`, `k = 64` | 6,144 B | 3,072 B | 3.0 kB |
| `V = 8,192`, `k = 64` | 12,288 B | 6,144 B | 6.0 kB |

Against a CF-sized model (word list + unigram + memberships + block ≈ 24 kB at
`V = 4,096, k = 64`) that is **11–14 %**, i.e. roughly **three quarters of the
cost of doubling `k`** (which is `V·log₂2 / 8 + 3k²/8` ≈ 4 kB at that size).  So
even a modest compression loss could be worth paying: this is a
bytes-for-bits trade on the same frontier as `WORDLIST_BUDGET.md`.

There is a reason to expect the loss to be small.  A word's successor and
predecessor distributions both reflect its *syntactic role* — `get` is followed
by property names and preceded by receivers, but it is "the same kind of token"
from either side.  Hellinger `k`-means on the two profiles separately finds
similar groupings; the question is how much of the extra resolution the split
buys is real.

## The design

1. Build `M` (word × word counts, cycle-wrapped) on the training corpus, as
   `cluster_words.py` does.
2. Row profile `u_a = √p(·|a)` and column profile `v_a = √p(a|·)`, each a unit
   vector in the Hellinger embedding.
3. Concatenate: `x_a = [u_a ; w · v_a]`, with `w = 1` by default.  The
   concatenation's squared distance is the sum of the two Hellinger distances, so
   `w` is the knob that says which side matters more; `w = 1/√2` normalises the
   vector to unit length, and `w → 0` degenerates to clustering on successors
   only.
4. Spherical `k`-means on `{x_a}` with occurrence weights
   (`cluster_substrings_lib.kmeans_sphere`), `k ∈ {32, 64}` — one label per
   word, used as both `lcl` and `rcl`.
5. Score exactly as `model_fit_rates.py` does: `assoc_numbers` for `c, D, Cc`,
   then held-out bits and the 64/128-bit fit rates.

## Controls

* **Asymmetric baseline** at the same `k` — the current two-sided clustering,
  same corpus, same stride, same seed.  The difference in held-out bits is the
  cost of the extra constraint.
* **Asymmetric at matched bytes.**  The shared model saves ~3 kB, so compare
  against the asymmetric model that spends those bytes: cluster doubling is the
  natural unit, so report `shared(k)` against `asymmetric(k)` and
  `asymmetric(2k)` — the shared model is only interesting if it lands between
  them, closer to the latter.
* **Weight sweep** at one `k` on each side (`w ∈ {1/√2, 1, √2}`) to confirm the
  1:1 default is not a handicap.
* **Sanity**: the shared assignment's `D` is not symmetric (`M` is not), so the
  block stays `k²`.  Do not "save" half the block by symmetrising: that changes
  the model, not just its storage.

## Metrics and decision rule

Report, per `k`: held-out mean bits, fit ≤64, fit ≤128, model bytes (word list +
unigram + membership + block), and the full-table reference bits.  The word list
is charged at the price the packed file pays for it, not at a formula
(`model_size.pack_rules`): at `V = 8,192` that is 21,145 B, and a `V log₂ V`
estimate misses it by 8 kB.  Adopt if at
**matched total bytes** the fit rate is no worse than the asymmetric model
(within ±0.3 pt, the run-to-run noise of the frontier), or if the matched-`k`
CS loss is smaller than the bytes-equivalent loss on the `WORDLIST_BUDGET.md`
frontier.

## Measurement at the canonical grid

4,096: `k = 32, 64`; 8,192: `k = 64`.  10,567 held-out identifiers (stride 40),
`kappa = 300`, seed 1; `scripts/shared_clusters.py --dir work/tw… --ks …`.

| model | k | bits | fit<=64 | fit<=128 | bytes |
|---|---|---|---|---|---|
| 4096 asymmetric | 32 | 51.355 | 78.2% | 98.1% | 20,065 |
| 4096 shared w=1/√2 | 32 | 51.571 | 78.0% | 98.1% | **17,505** |
| 4096 **shared w=1** | 32 | 51.544 | 78.1% | 98.1% | **17,505** |
| 4096 shared w=√2 | 32 | 51.744 | 77.8% | 98.0% | 17,505 |
| 4096 asymmetric | 64 | **50.622** | **79.1%** | 98.2% | 24,161 |
| 4096 **shared w=1** | 64 | 51.143 | 78.5% | 98.2% | **21,089** |
| 4096 asymmetric | 128 | 49.996 | 79.8% | 98.3% | 37,473 |
| 8192 asymmetric | 64 | **47.279** | **83.4%** | 98.8% | 45,721 |
| 8192 **shared w=1** | 64 | 47.611 | 82.9% | 98.7% | **39,577** |
| 8192 asymmetric | 128 | 46.948 | 83.6% | 98.8% | 60,057 |

(`w = 1` is quoted for the shared rows because the weight sweep has no
consistent winner — 0.707 at 4096/64, 1.0 at 4096/32, 1.414 at 8192/64, all
within 0.2 bits.  Keep the 1:1 default; the concatenation is not a handicap.)

### At matched `k` it loses; at matched bytes it wins

At matched `k` the constraint costs 0.19 bits at `k = 32` and 0.33-0.52 bits at
`k = 64` (0.27 and 0.43 on the 10x set), with fit<=64 down 0.1, 0.6 and 0.5
points.  That is not the question
the decision rule asks: it is about **matched total bytes**, and the asymmetric
model does not exist at 14.8, 18.4 or 33.8 kB.  Placing each shared point
against the asymmetric frontier interpolated to the same size:

| point | bytes | fit<=64 | frontier at that size | margin |
|---|---:|---:|---:|---:|
| 4096, `k = 32` | 17,505 | 78.1% | 77.6% (extrapolated below `k = 32`) | **+0.46 pt** |
| 4096, `k = 64` | 21,089 | 78.5% | 78.4% (between `k = 32` and 64) | +0.07 pt |
| 8192, `k = 64` | 39,577 | 82.9% | 82.2% (between `V = 4096` and 8192 at `k = 64`) | **+0.73 pt** |

Why the trade can pay: a point of fit<=64 costs 4.3-4.6 kB on this frontier, so
the 2.5-6.1 kB the shared assignment frees is worth 0.6-1.4 pt, against a
constraint that costs 0.1-0.6 pt.  In a model of under two kilobytes the same
percentage saving is 256 B — half a point — against a constraint that costs more
than a point, so the identical trade is a loss.  The verdict is a statement about
the size of the model, not about the constraint, and it must be re-measured, not
scaled: the testing-point run is recorded in
[`SMALL_DICT.md`](SMALL_DICT.md#shared-cluster-assignment-worktw512ns-k--16).

### The close-out: five seeds on the 10x held-out set

A margin of a tenth of a point cannot be carried by one seed, so both
`V = 4096` points were re-measured with five seeds on the 10x held-out set
(stride 10, 42,268 identifiers), re-interpolating the frontier per seed
(`scripts/c26_closeout.py`, which also counts the identifiers that cross the
64-bit line in each direction):

| point | margin over 5 seeds | paired SE | shared − asymmetric bits | crossings at 64 bits |
|---|---:|---:|---:|---:|
| 4096, `k = 32` | **+0.343 pt** | 0.068 | +0.274 ± 0.039 | +64 / −91 |
| 4096, `k = 64` | **−0.036 pt** | 0.055 | +0.429 ± 0.041 | +73 / −124 |

At `k = 32` the shared model is comfortably above the interpolated frontier:
+0.34 pt at 5σ, with 64 identifiers gained and 91 lost at the 64-bit line (a net
loss in that narrow sense, because the model also moves the whole distribution).
At `k = 64` there is no advantage at all — the margin is zero to within the
noise, and slightly negative — so the seed-1 `+0.08 pt` does not hold.  The
`V = 8192, k = 64` point is still a single seed and should be re-measured the
same way before it is quoted as a win.

### The same trade in the packed file

The tables above price the memberships in bits and the word list at a formula.
`scripts/model_size.py` builds the same constraint in the shipped format — one
shared assignment versus two independent ones — packs both, and decodes held-out
identifiers through the packed file (`MODEL_BUDGET.md` §7).  `q = 1`, stride 10;
"bought" is the bits the second map saves:

| point | one map | bits/id | fit ≤64 | two maps | bits/id | fit ≤64 | saved | bought |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4096, `k = 32` | 15,685 B | 48.926 | 80.4 % | 18,245 B | 48.287 | 80.9 % | 2,560 B | 0.64 bits |
| 8192, `k = 16` | 30,612 B | 45.790 | 84.1 % | 34,708 B | 45.317 | 84.6 % | 4,096 B | 0.47 bits |
| 8192, `k = 32` | 32,126 B | 45.221 | 84.8 % | 37,246 B | 45.190 | 84.8 % | 5,120 B | 0.03 bits |

* **The constraint's price falls with `k`**, faster than the accounting
  predicted: 0.47 bits at `k = 16`, 0.03 at `k = 32` — 8.7 and 170 kB per bit,
  against a frontier that charges 3.9–5.5.  Once the clusters are fine enough, a
  word's successor and predecessor profiles agree well enough that a second
  assignment adds almost nothing.  (These are Huffman-code numbers from a
  different model than the `assoc` table's 0.19–0.33 bits above; read the
  gradient, not the level.)
* **At `V = 4,096, k = 32` the two are nearly tied**: 2,560 B for 0.64 bits
  (4.0 kB/bit) and +0.5 pt of fit (5.1 kB/pt), both at the frontier's own rate.
  The size of the model is what decides, exactly as the decision rule says.
* **The map that is dropped is the left one.**  The packed file stores one
  label per word — the right cluster — and derives the left cluster from it
  (divided by `q`, so unchanged at `q = 1`).  A two-map file adds `V log₂ k`
  bits beside those labels: 2,560 B at `k = 32, V = 4,096` and 5,120 B at
  `k = 32, V = 8,192`.

### Verdict

**Adopt the shared assignment at `k = 32`** (one label as both `lcl` and `rcl`,
`w = 1`), keeping the `k^2` block: `D` asymmetry is 0.5-1.4 in Frobenius ratio,
so it cannot be halved.  At the small `k` the 2.5 kB it frees is worth about
half a point of fit, which is more than the constraint costs; at `k = 64` the
freed 3 kB is worth the same and the constraint costs the same, so the two
cancel and the scheme is **neutral**.  Two caveats to carry forward: the
`k = 32` margin relies on extrapolating the frontier below `k = 32` (there is no
smaller asymmetric point at `V = 4096`), and the two-clause rule should be
stated as the frontier placement test used here, not as "fit at matched `k`",
which reads as a rejection of a scheme that is in fact above the frontier.

## Implementation

New `scripts/shared_clusters.py` (≈120 lines, mostly reuse): `cluster_words.py`
for `M`, `assoc_numbers`, `bits_of`; `cluster_substrings_lib.kmeans_sphere` for
the joint clustering; `--ks 32,64 --dir work/tw… --stride 40 --half-weight 1`.
Report goes in this file when it has numbers.
