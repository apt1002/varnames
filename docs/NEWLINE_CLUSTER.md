# Reserving clusters for the stop token

Status: **rejected — and the `--profile full` control, which was outstanding
when the first canonical table was written, changes the *reason* rather than the
verdict.**  With the profile control in place the reservation is nearly free in
bits (0.007-0.19) and buys nothing generationally; the 0.3-0.44 bits the earlier
table charged to the singleton cell were mostly the clustering-profile change.
See "The profile control" below, which supersedes the attribution in the table
above it.

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

## Measurement at the canonical grid

(The first run of this experiment was at the testing vocabulary `V = 512`,
where the reservation looked free and beneficial — and where the observed
start-boundary defect turned out to be a resolution artefact rather than a
structural one.  Those numbers, and the `k` sweep that dissolved them, are in
[`SMALL_DICT.md`](SMALL_DICT.md#reserving-clusters-for-the-stop-token-worktw512ns-k--16).
Nothing is decided there; this section is the decision.)

`V = 4096, k = 32/64` and `V = 8192, k = 64`, 10,567 held-out identifiers
(stride 40), 20,000 samples, `profile=sub` (the pre-`full` command; see the
control note below):

| model | bits | fit<=64 | starts mid | ends mid | first-tok KL | last-tok KL | boundary share |
|---|---|---|---|---|---|---|---|
| 4096, plain(32) | **51.355** | **78.2%** | 2.4% | 1.8% | **0.127** | **1.401** | 23.5% |
| 4096, plain(31) | 51.366 | 78.3% | 2.4% | 1.9% | 0.127 | 1.403 | 23.4% |
| 4096, reserved(32) | 51.653 | 77.9% | 2.5% | 1.3% | 0.391 | 1.560 | 24.1% |
| 4096, plain(64) | **50.622** | **79.1%** | **1.8%** | **1.2%** | **0.113** | **1.385** | 23.7% |
| 4096, plain(63) | 50.633 | 79.1% | 1.6% | 1.1% | 0.116 | 1.395 | 23.7% |
| 4096, reserved(64) | 51.061 | 78.7% | 2.4% | 1.3% | 0.361 | 1.473 | 24.2% |
| 8192, plain(64) | **47.279** | **83.4%** | **3.1%** | **2.7%** | **0.096** | **1.639** | 26.9% |
| 8192, plain(63) | 47.288 | 83.3% | 3.0% | 2.7% | 0.096 | 1.641 | 26.9% |
| 8192, reserved(64) | 47.699 | 82.8% | 5.0% | 3.0% | 0.295 | 1.696 | 27.4% |

Three things are unambiguous:

1. **The reservation costs 0.30-0.44 bits (0.6-0.9%) and 0.4-0.6 points of
   fit<=64**, and it does so *in the boundary transitions*: 12.711 -> 13.072 at
   `V = 8192` (the interior moves by 0.06).  The design's premise is that the
   singleton cell makes the boundaries exact *up to the block*; in fact it makes
   the boundary **more expensive**, because it removes a useful pooling.
2. **`plain(k)` and `plain(k-1)` are indistinguishable** (0.01 bits, same fit),
   so the cost is not "one cluster fewer for the words" — it is the stop being
   alone.
3. **The generative gain does not appear**: mid-word starts get *worse* at
   `V = 8192` (3.1% -> 5.0%), mid-word ends do not improve (2.7% -> 3.0%), and
   both boundary KLs worsen by 3x.

### Why pooling wins here: closeness to the marginal

At `V = 4096/8192` almost every token can both start and end an identifier
(7,484 of 8,192 ever start, 7,806 ever end), so `P(first | .)` and `P(last | .)`
are nearly the **unigram restricted to startable/lastable words**.  When the
target is close to the marginal, the best estimator is heavily shrunk towards it
— and a pooled cell provides exactly that shrinkage for free: the block row is an
average over neighbouring words, which pulls it to the marginal.  The singleton
cell is unbiased at block resolution but noisier, and loses.  This is a
bias-variance effect, not an exactness effect, and it is invisible at `k = 16`,
where the singleton cell is *finer* than the pooled cell rather than merely
different.

The rule for when pooling wins is therefore: **pool whenever the boundary
distribution is close to the marginal over words** — i.e. whenever the token
set is nearly uniformly "startable".  At the canonical grid it is true, and the
reservation is inert; at a coarse vocabulary with few startable tokens it can be
false, which is why the testing point read the other way.  The primitive is
`startable/V`, not `V` itself, so the rule travels.

(This account explains the `profile=sub` charge in the table above.  With the
stop kept in each word's profile the charge largely disappears; see "The profile
control" below, which supersedes this attribution.)

### The outstanding control

The three canonical runs used `profile=sub`.  `profile=full` keeps the stop's
row and column inside each word's clustering profile; it was chosen at the
testing point, where it recovers the start boundary (see
[`SMALL_DICT.md`](SMALL_DICT.md)), and carried forward as the definition of the
reservation.  Until that control is run the verdict is
"rejected, with one configuration of the design untested" — but note that it
cannot explain a deficit that sits in the *boundary transitions* while the
clustering only changes which words share a cell.  Expect it to narrow the gap,
not to reverse it.

## Two corrections to the generative reading

**The generated length is compared in matched units.**  An earlier revision of
this note reported the model as generating identifiers "3x too long"; that was a
units bug in `newline_cluster.py` (string characters compared against corpus
tokens), recorded with its numbers in
[`SMALL_DICT.md`](SMALL_DICT.md).  With units matched the length distribution is
reproduced well, and the residual is explained by the prior — see the section
below.

**The "real identifier" hit rate is not a success metric.**  A model that
generalises is *supposed* to emit identifiers that are not in the corpus, so the
rate cannot be required to be high.  What it measures is **memorisation**: at 2%
of 20,000 samples against a 3.8M-identifier corpus, the model is reproducing
literally several hundred corpus members, which is a high rate, not a low one.
Report it under that name or not at all.

Of the generative numbers, only the mid-word metrics actually discriminate, and
they need the marginal baseline: a token drawn from the unigram is "mid-word"
with probability `1 - (startable / V)`, which is 8.6% at `V = 8192`.  The
reservation's generative advantage at a smaller vocabulary was real but small,
and it disappeared at the canonical grid, where the reservation is *worse* on
starts (5.0% vs 3.1% at `V = 8192`).  So the rejection rests on the compression
numbers, where there is no ambiguity; the generative columns are weak
corroboration, not the case against the design.

### The profile control: the cost was mostly the *profile*, not the cell

`profile=full` keeps the stop's own row and column inside every word's clustering
profile, so the only difference from `plain` is the singleton cell itself.
10,567 held-out identifiers, 20,000 samples:

| V, k | config | bits | fit<=64 | starts (chance) | ends (chance) | first KL | last KL | digit | exact table recovers |
|---|---|---|---|---|---|---|---|---|---|
| 4096, 32 | plain | 51.355 | 78.2% | 2.4% (8.1) | 1.8% (2.7) | 0.127 | 1.401 | 0.23% | 0.404 |
| 4096, 32 | reserved full | 51.376 | 78.3% | 2.9% | 1.4% | 0.139 | 1.410 | 0.97% | 0.418 |
| 4096, 64 | plain | **50.622** | **79.1%** | **1.8%** | 1.2% | **0.113** | **1.385** | 0.14% | 0.206 |
| 4096, 64 | reserved full | 50.812 | 78.9% | 3.0% | 1.3% | 0.150 | 1.422 | 0.93% | 0.275 |
| 8192, 64 | plain | 47.279 | 83.4% | 3.1% | 2.7% | 0.096 | 1.639 | 0.17% | 0.302 |
| 8192, 64 | reserved full | **47.286** | 83.3% | 3.1% | 2.8% | **0.094** | 1.644 | 0.16% | 0.315 |

(`plain(k-1)` sits between the two everywhere: 51.366 / 50.633 / 47.288.)

Three conclusions, all different from the first pass:

1. **The reservation is nearly free in bits** with the profile control:
   +0.021 (4096/32), +0.190 (4096/64), **+0.007** (8192/64) — where the `sub`
   runs charged +0.30/+0.44/+0.42.  So most of that charge was the *profile*
   change (words clustered without the stop's row and column), not the singleton
   cell.  The "shrinkage" explanation is therefore wrong as an account of the
   cost: with the stop kept in the profiles, pooling gains almost nothing on
   bits.
2. **It still buys no generative improvement.**  At `V = 8192` it is a complete
   no-op (starts 3.1% both, ends 2.7 vs 2.8, first KL 0.094 vs 0.096).  At
   `V = 4096` it is *worse* on the two metrics the design targeted: mid-word
   starts rise (1.8% -> 3.0% at `k = 64`) and the digit first-token mass rises
   4-7x (0.14% -> 0.93%).  Only mid-word *ends* improve, slightly and only at
   `V = 4096` (1.2% -> 1.3%, 1.8% -> 1.4%).
3. **The exact boundary table is also dead.**  At the canonical grid an exact
   `2V`-number stop row and column would recover only 0.21-0.42 bits/identifier.
   Eight kB (`V = 4096`) on a frontier worth ~4.3 kB per bit is ~1.9 bits
   equivalent, so the table cannot pay for itself either.

So the verdict is **reject**, now on the clean ground that there is nothing to
buy: the reservation is cheap but inert, and the mechanism it was supposed to
exploit (an exact boundary row/column) is worth less at the canonical grid than
the bytes it would take to store it.

## Length: the model is ~13% short, and the prior explains it

With units matched, every configuration generates identifiers slightly
*shorter* than the corpus: 4.05-4.08 tokens against 5.06 at `V = 8192`, 4.69-4.72
against 5.72 at `V = 4096`.  The `kappa` prior accounts for a known part of it:
it adds `kappa*V/T = 0.128` of the stop column's mass at `V = 8192` (`T` is the
transition count), i.e. it inflates `P(stop|.)` by ~13% and shortens the walk by
~1/1.128.  That predicts 4.49 tokens where 4.07 is measured, so the rest is
model error.  It is a *regularisation* effect with a knob (`kappa`), not a
defect.

## Implementation

Extend the model builder rather than the clusterer: a `--reserve-stop` flag on a
new `scripts/newline_cluster.py` that reuses `cluster_words.cluster_axis`,
`model_fit_rates.assoc_numbers` and `budget64_study.sample` (move `sample` and
the realism test into a small shared helper so both reports use one copy).  The
`\n` cell must be built from its own row/column, not from a block mean over a
cell of one (which is the same thing, but assert it).
