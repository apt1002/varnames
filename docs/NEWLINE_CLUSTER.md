# Reserving clusters for the stop token

Status: **planned; not started.**  Design and decision rule only.

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

## Implementation

Extend the model builder rather than the clusterer: a `--reserve-stop` flag on a
new `scripts/newline_cluster.py` that reuses `cluster_words.cluster_axis`,
`model_fit_rates.assoc_numbers` and `budget64_study.sample` (move `sample` and
the realism test into a small shared helper so both reports use one copy).  The
`\n` cell must be built from its own row/column, not from a block mean over a
cell of one (which is the same thing, but assert it).
