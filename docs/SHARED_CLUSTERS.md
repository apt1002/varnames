# One cluster assignment for both sides

Status: **measured at the testing point** (`V = 512`, `k = 16`): rejected there,
by the decision rule below.  The canonical-grid confirmation is the open item.

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

## Implementation

New `scripts/shared_clusters.py` (≈120 lines, mostly reuse): `cluster_words.py`
for `M`, `assoc_numbers`, `bits_of`; `cluster_substrings_lib.kmeans_sphere` for
the joint clustering; `--ks 32,64 --dir work/tw… --stride 40 --half-weight 1`.
Report goes in this file when it has numbers.
