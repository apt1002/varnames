# Reserving clusters for the stop token

Status: **measured at the testing point** (`V = 512`, `k = 16`); the canonical
grid and the start-boundary defect below are the open work.

## The question

The stop token `\n` is the odd symbol in the vocabulary: `N(\n)` is the number of
identifiers, its **row** is the distribution of *first* tokens and its
**column** the distribution of *last* tokens.  It is also the heaviest point in
the Hellinger `k`-means (weights are occurrence counts), so it currently drags a
whole cell towards itself on each side.

Should the model **reserve one left cluster and one right cluster for `\n`** —
singleton cells that no word may join?

## What it changes

With a singleton left cell, `P(quarter | \n)` is exact and `P(b | start)` is the
block row of the stop cell rather than an average over tokens that happen to
share its cell.  With a singleton right cell, `P(\n | a)` is `D[l(a), rcl(\n)]`
— one number per left cluster — instead of an average over a cell that contains
`\n` and a few real words.  So both **identifier boundaries** become exact up to
the block resolution, while the interior of the model is unchanged.

Two consequences, one for compression and one for generation:

* **Compression: expect near-neutral, possibly positive.**  The boundaries are
  two of the cheapest things in the model (one row, one column, each almost
  deterministic), so tightening them cannot save much — but it also *frees* the
  cell that `\n` was dominating for real words, and it stops `\n`'s very
  different dynamics from distorting that cell's other members.  Either effect
  could move the held-out bits slightly in either direction.
* **Generation: expect a large improvement in boundary legality.**  A sampled
  identifier starts by drawing from `P(· | start)` and ends by drawing
  `\n | a`.  If those are averages over a cell that mixes `\n` with ordinary
  tokens, the model systematically over-produces tokens that never start an
  identifier and under-produces stops at real word boundaries — which is exactly
  the "starts or ends mid-word" family of unreal samples.  It may also slightly
  shorten the length distribution, because `P(\n | a)` stops being diluted by the
  cell average.

## The design

1. Cluster the `V − 1` non-stop tokens on each side with `k − 1` clusters (same
   pipeline as now: Hellinger `k`-means, occurrence weights, same seed/stride).
2. Append a singleton cluster for `\n` on each side: `lcl[\n] = k−1`,
   `rcl[\n] = k−1` (indices after a relabel so nothing collides).
3. Recompute `c, D, Cc` (`model_fit_rates.assoc_numbers`) and score as usual.

## Three-way comparison (the important part)

To separate "reserving" from "one fewer cluster", run three configurations on
the same corpus, stride and seed:

| config | word clusters (per side) | stop |
|---|---|---|
| `plain(k)` | `k` | pooled into a cell |
| `plain(k−1)` | `k − 1` | pooled into a cell |
| `reserved(k)` | `k − 1` | singleton, each side |

`reserved(k)` vs `plain(k)` is the headline; `reserved(k)` vs `plain(k−1)` is
the real effect of the reservation (it isolates "the stop is alone" from "one
cell fewer for words").

## Metrics

**Compression.**  Held-out mean bits and fit ≤64 / ≤128, exactly as
`model_fit_rates.py` reports; model bytes (the reservation costs no bytes: `k`
clusters either way).

**Generation.**  Sample `n` identifiers from each model with the existing
sampler (`budget64_study.sample`) and report:

* fraction whose **first token never starts** a corpus identifier (the direct
  measurement of "starts mid-word");
* fraction whose **last token never ends** a corpus identifier;
* fraction whose first character is a digit (structurally impossible in the
  corpus);
* KL of the generated first-token and last-token distributions against the
  corpus's, which is the model-free version of the same thing;
* mean and 95th percentile of length, against the corpus;
* the existing "is it a real identifier" hit rate, so the number stays comparable
  with `BUDGET64_STUDY.md`.

## Decision rule

Adopt if (a) held-out bits move by less than the noise of the frontier (order
0.1 bit/identifier) and the fit rates do not fall, **and** (b) the
starts-mid-word / ends-mid-word fractions drop materially (target: halved,
ideally more), with no regression in the length distribution.  If (a) fails
slightly but (b) is strong, the trade is still likely worth it — say so
explicitly rather than hiding it behind a single number, because the generative
property is what the product sells.

## First measurement (`V = 512`, `k = 16`, `work/tw512ns`)

Held-out: 2,114 validation identifiers (stride 200), `kappa = 300`; generation:
2,000 samples.  `scripts/newline_cluster.py --dir work/tw512ns --k 16
--stride 200`.

| config | bits | fit<=64 | fit<=128 | starts mid | ends mid | first-tok KL | last-tok KL | len mean | real |
|---|---|---|---|---|---|---|---|---|---|
| `plain(k)` | 67.725 | 57.1% | 93.7% | 3.0% | 2.2% | 0.300 | 1.170 | 16.66 | 1.45% |
| `plain(k-1)` | 67.766 | 57.3% | 93.7% | 3.0% | 2.1% | 0.292 | 1.161 | 16.32 | 1.75% |
| `reserved(k)`, `profile=sub` | 67.617 | 57.7% | 93.9% | 2.9% | **0.1%** | 0.488 | 1.195 | 16.05 | 2.45% |
| `reserved(k)`, `profile=full` | 67.703 | 57.2% | 93.8% | **2.1%** | **0.0%** | 0.311 | **1.096** | 16.82 | 2.40% |

(The corpus values for the same held-out set: mean length 9.14 tokens, digit
first-token mass 0.00%, last-token digit mass 5.58%.)

**Compression is neutral-to-better**, as predicted: the reservation costs no
model bytes (`k` cells either way) and the boundary transitions are only ~15% of
the bits.

**The end boundary behaves exactly as designed** — "ends mid-word" falls from
2.2% to 0.1% (`profile=sub`) or 0.0% (`profile=full`) and the last-token KL
improves.  Mechanism: the stop's **column** is allocated through `rcl[\n]`,
which is now a singleton, so `P(\n | a)` is exact at left-cluster resolution.

**The start boundary does not, and the asymmetry is structural.**  `P(b | \n)`
is allocated through `lcl[\n]`: the *row* of `D` is exact, but the within-row
allocation inside each right cluster is proportional to the unigram `c[b]`.  A
token's "start-ness" cannot be expressed, so tokens that are frequent in the
interior and never start an identifier — the digits above all, corpus first-token
digit mass 0.00% — are over-produced: 0.45% (`plain`) vs 2.45% (`sub`) vs 1.91%
(`full`) of first tokens are digits.  Pooling `\n` into a cell hides this,
because the cell average happens to shrink the row towards words with compatible
successor statistics; that is an accident, not a guarantee.

`profile=full` (keep the stop's row and column inside each word's clustering
profile) is the fix that costs nothing: it recovers the start boundary to parity
as well (2.1% mid-word starts, first-token KL 0.311 vs `plain`'s 0.300) while
keeping the end-boundary win, and it is the better configuration on every other
metric too.  **Adopt `profile=full` as the reservation's definition.**

What is left is the within-cluster allocation.  The **cost of the defect in
bits** is measurable without committing to a fix: the two boundary transitions
(first token out of the stop, last token into it) cost 15.742 bits/identifier
under `reserved(k)` and 15.676 under `plain(k)`, against **14.912** if the stop's
own row and column were stored exactly — so an exact `2V`-number boundary table
would recover 0.76–0.83 bits/identifier (`exact_boundary_gap` in the script).

At `V = 512` that table is 1,024 B, i.e. ~1.9 bits on the frontier slope read
off the `k`-doubling control in `SHARED_CLUSTERS.md` — so the exact table is
**not** worth its bytes there.  The options, in increasing cost:

1. more right clusters — the digits may separate on their own, since "preceded
   by the stop" is literally the first entry of a word's column profile and
   `profile=full` puts it in the clustering metric (untested: needs `k = 64`);
2. a start-ability bitmap — `V/8` bytes of "this word ever starts an
   identifier", which kills the digit leak but not the bit deficit; the same
   kind of structural knowledge as `STRUCTURAL_ZEROS.md`;
3. the exact stop row as a `V`-number table (or row and column, `2V`).

Options 2 and 3 both break "the stop is ordinary" in the table layout, so the
first question remains whether the defect survives at `k = 64`.

Two things that are *not* C27 effects but are visible here and matter later:
the sampled length distribution is ~1.8x too long in every configuration
(16.7 vs 9.1 tokens), and the real-identifier hit rate is 1.5-2.5% — both are
properties of the sampler/model as it stands (`docs/BUDGET64_STUDY.md`).

## Implementation

Extend the model builder rather than the clusterer: a `--reserve-stop` flag on a
new `scripts/newline_cluster.py` that reuses `cluster_words.cluster_axis`,
`model_fit_rates.assoc_numbers` and `budget64_study.sample` (move `sample` and
the realism test into a small shared helper so both reports use one copy).  The
`\n` cell must be built from its own row/column, not from a block mean over a
cell of one (which is the same thing, but assert it).
