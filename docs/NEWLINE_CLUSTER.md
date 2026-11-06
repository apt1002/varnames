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

## First measurement (`V = 512`, `k = 16`, `work/tw512ns`)

Held-out: 2,114 validation identifiers (stride 200), `kappa = 300`; generation:
2,000 samples.  `scripts/newline_cluster.py --dir work/tw512ns --k 16
--stride 200`.

| config | bits | fit<=64 | fit<=128 | starts mid | ends mid | first-tok KL | last-tok KL | len (chars) | "real" |
|---|---|---|---|---|---|---|---|---|---|
| `plain(k)` | 67.725 | 57.1% | 93.7% | 3.0% | 2.2% | 0.300 | 1.170 | 16.66 | 1.45% |
| `plain(k-1)` | 67.766 | 57.3% | 93.7% | 3.0% | 2.1% | 0.292 | 1.161 | 16.32 | 1.75% |
| `reserved(k)`, `profile=sub` | 67.617 | 57.7% | 93.9% | 2.9% | **0.1%** | 0.488 | 1.195 | 16.05 | 2.45% |
| `reserved(k)`, `profile=full` | 67.703 | 57.2% | 93.8% | **2.1%** | **0.0%** | 0.311 | **1.096** | 16.82 | 2.40% |

(The corpus values for the same held-out set: 9.14 tokens / 16.26 characters,
digit first-token mass 0.00%, last-token digit mass 5.58%, chance mid-word
5.9% starts / 0.6% ends.  The `"real"` column is a memorisation rate, not a
success rate — see the correction below.)

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

### The defect does not survive larger `k`

Raising `k` at the testing point (`V = 512`, diagnostic `k` — the canonical
pairing is `k = 32/64` at `V = 4096/8192`), `reserved(k)`, `profile=full`,
2,114 held-out identifiers, 1,500 samples:

| k | bits | fit<=64 | starts mid | ends mid | first-tok KL | digit mass | boundary table would recover |
|---|---|---|---|---|---|---|---|
| 16 | 67.703 | 57.2% | 2.1% | 0.0% | 0.311 | 1.91% | 0.83 bits |
| 32 | 66.056 | 59.8% | 0.5% | 0.2% | 0.220 | 0.02% | 0.38 bits |
| 64 | 63.624 | 63.0% | 0.3% | 0.1% | 0.180 | 0.02% | 0.08 bits |

So the start-boundary defect is a **resolution** artefact, not a structural
flaw in the reservation: once the right clusters are fine enough, the words that
never start an identifier separate on their own ("preceded by the stop" is the
first entry of a word's column profile, and `profile=full` puts it in the
clustering metric).  Options 2 and 3 are therefore unnecessary — and at `k = 64`
the exact-table reference is even *worse* than the block model (−0.04 bits,
because the exact raw-count row is unfitted where the block model carries the
`kappa` prior).

### `reserved` vs `plain` at `k = 64`

| config | bits | fit<=64 | fit<=128 | starts mid | ends mid | first-tok KL | last-tok KL | digit |
|---|---|---|---|---|---|---|---|---|
| `plain(k)` | **63.227** | **63.7%** | 94.9% | 2.5% | 0.4% | 0.204 | 1.102 | 1.7% |
| `plain(k-1)` | 63.325 | 63.4% | 94.9% | 2.4% | 0.3% | 0.210 | 1.104 | 1.8% |
| `reserved(k)` | 63.624 | 63.0% | **95.0%** | **0.3%** | **0.1%** | **0.180** | **1.039** | **0.0%** |

The reservation now **costs** 0.40 bits (0.6%) and 0.7 points of fit<=64, where
at `k = 16` it was free.  Under the decision rule of this note, (a) fails
marginally and (b) is strong: mid-word starts fall 8x, mid-word ends 4x, the
digit leak is eliminated, and both boundary KLs improve.  **Recommend adopting
it with `profile=full`** — the compression price is 0.6% and the generative
property is what the product sells.  Note also that the pooled stop leaks digits
at *every* `k` (1.7% at `k = 64`), so this is not a small-`k` curiosity on the
`plain` side either.

Two things that are *not* C27 effects but are visible here and matter later:
the sampled length distribution is ~1.8x too long in every configuration
(16.7 vs 9.1 tokens), and the real-identifier hit rate is 1.5-2.5% — both are
properties of the sampler/model as it stands (`docs/BUDGET64_STUDY.md`).

## The canonical grid reverses it

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

### Why the testing point misled us

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
set is nearly uniformly "startable".  At `V = 512`, `k = 16` that was false
(482 of 512 startable, and the stop's cell was dominated by words with genuinely
different dynamics); at the canonical grid it is true.

### The outstanding control

The three canonical runs used `profile=sub`.  `profile=full` was adopted at the
testing point because it recovers the *start* boundary there (first-token KL
0.488 -> 0.311, mid-word starts 2.9% -> 2.1%); it keeps the stop's row and column
inside each word's clustering profile.  Until that control is run the verdict is
"rejected, with one configuration of the design untested" — but note that it
cannot explain a deficit that sits in the *boundary transitions* while the
clustering only changes which words share a cell.  Expect it to narrow the gap,
not to reverse it.

## Correction: the length numbers were a units bug

An earlier revision of this note reported the model as generating identifiers
"3x too long".  That was wrong, and the fault was in
`newline_cluster.py`: the generated length was the length of the *string* in
characters while the corpus length was the number of *tokens*.  Matched units
(`V = 512`, `k = 16`, 3,000 samples):

| config | tokens (corpus 9.14) | chars (corpus 16.26) |
|---|---|---|
| `plain(k)` | 8.37 | 16.61 |
| `plain(k-1)` | 8.14 | 16.23 |
| `reserved(k)`, `profile=full` | 8.38 | 16.67 |

The length distribution is in fact reproduced well — 2% long in characters, 8%
short in tokens, with the 95th percentile slightly heavy (24 vs 18 tokens).  The
penalty of the factorisation is 8% on the token mean, not a factor of three.

The same correction applies to every "real identifier hit rate" figure quoted
here.  That number is **not** a success metric: a model that generalises is
*supposed* to emit identifiers that are not in the corpus, so the rate cannot be
required to be high.  What it does measure is **memorisation** — at 2% of 20,000
samples against a 3.8M-identifier corpus, the model is reproducing literally
several hundred corpus members, which is a high rate, not a low one.  It should
be reported under that name or not at all.

Of the generative numbers, only the mid-word metrics actually discriminate, and
they need the marginal baseline: a token drawn from the unigram is "mid-word"
with probability `1 - (startable / V)`, which is 5.9% at `V = 512` and 8.6% at
`V = 8192`.  Against that, every configuration is *better* than chance on
starts, so the metric discriminates weakly and the reservation's advantage at the
testing point (2.1% vs `plain`'s 3.3%, chance 5.9%) is real but small.  At the
canonical grid the ordering reverses (5.0% vs 3.1% at `V = 8192`).  On ends the
signal is at least consistent: at the testing point `plain` is *worse* than
chance (2.4% vs 0.6%) while `reserved` is perfect (0.0%).  So the rejection rests
on the compression numbers, where there is no ambiguity; the generative columns
are weak corroboration, not the case against the design.

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
   `2V`-number stop row and column would recover only 0.21-0.42 bits/identifier
   — not the 0.83 found at `V = 512`.  Eight kB (`V = 4096`) on a frontier worth
   ~4.3 kB per bit is ~1.9 bits equivalent, so the table cannot pay for itself
   either.

So the verdict is **reject**, now on the clean ground that there is nothing to
buy: the reservation is cheap but inert, and the mechanism it was supposed to
exploit (an exact boundary row/column) is worth less at the canonical grid than
the bytes it would take to store it.

## Length: the model is ~13% short, and the prior explains it

With the units bug fixed, every configuration generates identifiers slightly
*shorter* than the corpus: 4.05-4.08 tokens against 5.06 at `V = 8192`, 4.69-4.72
against 5.72 at `V = 4096`.  The `kappa` prior accounts for a known part of it:
it adds `kappa*V/T = 0.128` of the stop column's mass at `V = 8192` (`T` is the
transition count), i.e. it inflates `P(stop|.)` by ~13% and shortens the walk by
~1/1.128.  That predicts 4.49 tokens where 4.07 is measured, so the rest is
model error.  It is a *regularisation* effect with a knob (`kappa`), not a
defect, and it is the opposite of the 3x over-generation I wrongly reported.

## Implementation

Extend the model builder rather than the clusterer: a `--reserve-stop` flag on a
new `scripts/newline_cluster.py` that reuses `cluster_words.cluster_axis`,
`model_fit_rates.assoc_numbers` and `budget64_study.sample` (move `sample` and
the realism test into a small shared helper so both reports use one copy).  The
`\n` cell must be built from its own row/column, not from a block mean over a
cell of one (which is the same thing, but assert it).
