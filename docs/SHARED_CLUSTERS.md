# One cluster assignment for both sides

Status: **measured at the testing point and at the canonical grid.**  Rejected
at `V = 512, k = 16`; **adopted at the canonical grid**, where it sits at or
above the asymmetric frontier at matched total bytes.  The reading of the
decision rule that produces the flip is spelled out below, because it is the
part that changed.

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

Against a CF-sized model (word list + unigram + memberships + block ≈ 21 kB at
`V = 4,096, k = 64`) that is **12–15 %**, i.e. roughly **three quarters of the
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
   (`cluster_substrings_lib.kmeans_sphere`), `k ∈ {32, 64}` (`k = 16` at the
   `V = 512` testing point) — one label per word,
   used as both `lcl` and `rcl`.
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
unigram + membership + block), and the full-table reference bits.  Adopt if at
**matched total bytes** the fit rate is no worse than the asymmetric model
(within ±0.3 pt, the run-to-run noise of the frontier), or if the matched-`k`
CS loss is smaller than the bytes-equivalent loss on the `WORDLIST_BUDGET.md`
frontier.

## Measurement (`V = 512`, `k = 16`, `work/tw512ns`)

4,227 held-out identifiers (stride 100), `kappa = 300`, seed 1;
`scripts/shared_clusters.py --dir work/tw512ns --ks 16 --stride 100`.

| model | k | bits | fit<=64 | fit<=128 | bytes | `D` asymmetry |
|---|---|---|---|---|---|---|
| full table | — | 53.134 | 77.0% | 97.8% | — | — |
| `asymmetric` | 16 | 68.105 | 57.1% | 93.7% | 1,980 | 1.33 |
| `shared`, `w = 1/√2` | 16 | 69.071 | 54.8% | 93.4% | 1,724 | 0.92 |
| `shared`, `w = 1` | 16 | **68.784** | 55.9% | 93.5% | 1,724 | 1.20 |
| `shared`, `w = √2` | 16 | 69.140 | 55.0% | 93.5% | 1,724 | 1.09 |
| `asymmetric` | 32 | 66.480 | 59.0% | 94.2% | 2,872 | 1.37 |

**The weight sweep vindicates the 1:1 default** — `w = 1` is the best of the
three, so the concatenation's equal weighting is not a handicap.

**The constraint costs 0.68 bits/identifier and 1.2 points of fit<=64**, in
exchange for 256 B (13% of the model).  The frontier slope at this point is read
off the `k`-doubling control: 892 B buys 1.63 bits, so 256 B is worth ~0.47 bits
— the shared model loses 0.68 and saves 0.47.  **Dominated at matched bytes**,
so the decision rule says do not adopt, and the margin (1.2 pt) is four times
the +-0.3 pt noise band.

Note that the saving here is the *smallest* case in the design note's table
(13% at `V = 512`, `k = 16` against 12-15% at the canonical grid), and the
frontier slope is what scales with it, so the verdict is not obviously a
small-`V` artefact — but it is one point, and at `k = 16` the memberships are
cheap.  Confirm at `V = 4096, k = 32/64` before closing it: that is where the
membership saving is 2.5-3.0 kB against a 21 kB model and where the clustering
has enough clusters for "the same kind of token from either side" to be a
meaningful claim.

`D` asymmetry 1.2-1.4 (Frobenius ratio `||D - D^T|| / ||D||`) confirms the block
is genuinely not symmetric, so the `k^2` table cannot be halved.

## The canonical grid: measured, and it flips the verdict

4,096: `k = 32, 64`; 8,192: `k = 64`.  10,567 held-out identifiers (stride 40),
`kappa = 300`, seed 1; `scripts/shared_clusters.py --dir work/tw… --ks …`.

| model | k | bits | fit<=64 | fit<=128 | bytes |
|---|---|---|---|---|---|
| 4096 asymmetric | 32 | 51.355 | 78.2% | 98.1% | 17,400 |
| 4096 shared w=1/√2 | 32 | 51.571 | 78.0% | 98.1% | **14,840** |
| 4096 **shared w=1** | 32 | 51.544 | 78.1% | 98.1% | **14,840** |
| 4096 shared w=√2 | 32 | 51.744 | 77.8% | 98.0% | 14,840 |
| 4096 asymmetric | 64 | **50.622** | **79.1%** | 98.2% | 21,488 |
| 4096 **shared w=1** | 64 | 51.143 | 78.5% | 98.2% | **18,416** |
| 4096 asymmetric | 128 | 49.996 | 79.8% | 98.3% | 34,784 |
| 8192 asymmetric | 64 | **47.279** | **83.4%** | 98.8% | 39,920 |
| 8192 **shared w=1** | 64 | 47.611 | 82.9% | 98.7% | **33,776** |
| 8192 asymmetric | 128 | 46.948 | 83.6% | 98.8% | 54,240 |

(`w = 1` is quoted for the shared rows because the weight sweep has no
consistent winner — 0.707 at 4096/64, 1.0 at 4096/32, 1.414 at 8192/64, all
within 0.2 bits.  Keep the 1:1 default; the concatenation is not a handicap.)

### At matched `k` it loses; at matched bytes it wins

At matched `k` the constraint costs 0.19 bits at `k = 32` and 0.33-0.52 bits at
`k = 64`, with fit<=64 down 0.1, 0.6 and 0.5 points.  That reads as a rejection
— and it is how the `V = 512` measurement was decided.  But the decision rule is
about **matched total bytes**, and the asymmetric model does not exist at 14.8,
18.4 or 33.8 kB.  Placing each shared point against the asymmetric frontier
interpolated to the same size:

| point | bytes | fit<=64 | frontier at that size | margin |
|---|---:|---:|---:|---:|
| 4096, `k = 32` | 14,840 | 78.1% | 77.6% (extrapolated below `k = 32`) | **+0.46 pt** |
| 4096, `k = 64` | 18,416 | 78.5% | 78.4% (between `k = 32` and 64) | +0.08 pt |
| 8192, `k = 64` | 33,776 | 82.9% | 82.0% (between `V = 4096` and 8192 at `k = 64`) | **+0.93 pt** |

All three sit at or above the frontier, two comfortably and one at the
noise boundary.  The rule's tolerance is +-0.3 pt, so all three pass: the shared
point is *not below* the asymmetric frontier anywhere measured, and at `V = 8192`
it is a clear 0.9 points above it.

**Why the testing point said otherwise.**  The frontier is steep in bytes at
`V = 512` — 892 B buys 1.9 points of fit<=64 (0.47 kB/pt) — so saving 256 B is
worth almost nothing, while the constraint still costs 1.2 points.  At the
canonical grid the frontier is 4,287-4,542 B/pt over the same kind of step: bytes
are worth four to ten times more, and the membership saving is 2.5-6.1 kB rather
than 256 B.  The `V = 512` verdict was a statement about a cheap model, not about
the constraint.

### Verdict

**Adopt the shared assignment at the canonical grid** (one label as both `lcl`
and `rcl`, `w = 1`), keeping the `k^2` block: `D` asymmetry is 0.5-1.4 in
Frobenius ratio, so it cannot be halved.  It buys 15-17% of the model for
0.19-0.52 bits, which is a *gain* on the bytes-for-fit frontier at every
canonical point measured.  Two caveats to carry forward: the `k = 64` at
`V = 4096` margin (+0.08 pt) is inside the noise, so that cell is "no worse"
rather than "better"; and the two-clause rule should be stated as the frontier
placement test used here, not as "fit at matched `k`", which reads as a rejection
of a scheme that is in fact above the frontier.

## Implementation

New `scripts/shared_clusters.py` (≈120 lines, mostly reuse): `cluster_words.py`
for `M`, `assoc_numbers`, `bits_of`; `cluster_substrings_lib.kmeans_sphere` for
the joint clustering; `--ks 32,64 --dir work/tw… --stride 40 --half-weight 1`.
Report goes in this file when it has numbers.
