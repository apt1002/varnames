# The rejected strategy: a character-level successor model

Status: **rejected.**  Encoding each character from its preceding context is
the obvious information-theoretic design, and it does compress — but at a
comparable vocabulary the word model codes identifiers 10–16% shorter
([`WORD_COMPRESSIBILITY.md`](WORD_COMPRESSIBILITY.md)), and the successor model
pays for that in tables: 16 bytes for every common substring, against a word
list whose entries are derivable from a rule set.  The document is kept because
it is the reference design this project measured against, and because the
`(k, N)` size methodology it introduced carries over to the word matrix (see
[`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)).

## The model

Encode each character conditionally on the context that precedes it.  Wrap the
identifier as `^identifier$`; at each split position, credit the successor
character to the **longest common substring that is a suffix of the prefix**
(a longest-suffix / variable-order model), so after `^Ac` the successor is
credited to `^Ac` rather than `Ac` or `c`.  Every split position is assigned to
exactly one context — 81,455,598 of them on the current 10-ecosystem union
(41,272,149 on the pre-expansion corpus).  The rows are the common substrings
that can occur as a prefix suffix (non-empty, not ending in `$`), and a `#global`
row carries the corpus-wide successor marginal, used as a shared Dirichlet
prior for smoothing.  `scripts/successor_distributions.py` builds the table;
`scripts/code_lengths.py` turns it into the ideal arithmetic-code length of each
identifier, which is how the strategy's fixed-budget success rate is scored
([`CODE_LENGTHS.md`](CODE_LENGTHS.md)).

The model is far too big at full resolution — one successor distribution per
common substring — so the contexts are pooled into `k` clusters, each carrying
one distribution.  `scripts/cluster_substrings.py` does the pooling under two
objectives:

* **`--method kl`** (default) directly minimises the occurrence-weighted
  cross-entropy `sum_s N_s * H(p_s || P_cluster(s))`, which equals
  `H(next | cluster)`; assignment is to the smallest cross-entropy and the
  update is the pooled-count mean (Lloyd's algorithm for the KL/multinomial
  objective).  This optimises exactly the quantity we report.
* **`--method sphere`** embeds `sqrt(p)` on the unit sphere (squared Euclidean
  distance is twice the squared Hellinger distance, a metric surrogate for the
  non-metric KL "compression" distance) and runs spherical K-means.

Both are occurrence-weighted: each context contributes with weight `N_s`, and
the sphere update is the re-normalised count-weighted mean `sum N_s x_s` (the
`kl` update is the pooled-count mean).  The weighting does not affect the
assignment step, since it is a per-point constant.  The two methods agree to
within ~0.04 bits over `k = 2..100` (at most 0.035 bits, mean 0.015 on the
pre-expansion corpus; at most 0.052, mean 0.019 at threshold 2000), so it does
not matter which one you run.  `scripts/cluster_entropy.py` reports `H(next)`,
`H(next | substring)`, `H(next | cluster)` and the information retained.

`k` is fixed by the caller (`--k`); there is deliberately no automatic
selection.  Every criterion tried (the elbow of the bits curve, the mean
silhouette, and in principle held-out compression) was either arbitrary or
merely relocated the arbitrariness, so `k` is chosen by hand and the curve is
produced by sweeping `--k`.

On the current corpus `H(next) = 4.969` bits for every threshold, and the
exact-context floor `H(next | substring)` runs from 3.778 (`N = 278`) to 2.370
(`N = 80,869`); the clustering has to buy back as much of that 2.6-bit gap as
its `k` clusters allow.  At the pre-expansion vocabulary `H(next) = 4.966` and
`k = 12, 22, 100` gave 4.011, 3.821, 3.502 bits — so `k` is the dominant lever,
but 100 clusters still did not reach the exact-context 3.070 bits.

### What the clusters look like (pre-expansion record)

At the pre-expansion threshold `T = 2000` (11,758 common substrings, 10,890
analysable successor distributions) and a hand-picked `k = 17`, many clusters
are near-deterministic — each pinned to a single likely next character — plus a
digit/underscore cluster and a large mixed "junk drawer".  The entropies are
`H(next) = 4.966`, `H(next | substring) = 2.611`, `H(next | cluster) = 3.547`
bits, so 17 clusters retain 1.419 bits of the 2.355-bit achievable reduction.
That is the qualitative answer the size study below quantifies: a small `k`
buys the deterministic structure cheaply, and the tail is what resists.

The rest of this note is the size study: what `k` and `N` cost, and where the
Pareto frontier sits.

## The two knobs and what they cost

The successor model predicts the next character from the longest common
substring that is a suffix of the prefix (the "context").  Its two size knobs
are:

* **`N`** — the number of common substrings (the vocabulary), set by the
  occurrence threshold `T` (a substring is kept if it occurs at least `T`
  times).  Raising `N` admits longer, sharper contexts.
* **`k`** — the number of clusters the contexts are pooled into; each cluster
  carries one successor distribution.

Under the dense representation we intend (see
[the brief](CODE_LENGTHS.md)), a substring costs **16 bytes** (its
hash / index) and a cluster costs **128 bytes** (its dense distribution over the
`d ≈ 64` successor symbols).  So the model size is

    S(N, k) = 16 N + 128 k    bytes.

Only the *ratio* 128 : 16 = **8** matters for the trade-off; all conclusions
should be reported as a function of it, and checked for sensitivity.

## What "good for its size" means

Both knobs reduce the code length per character, `H(next | cluster)` in bits,
but at a byte cost.  **The model is paid for once and then used on a very large
corpus**, so its size is a *resource we choose to spend*, not a cost amortised
against the data — we do not add it to a data-coding cost (no MDL).  The study
is therefore a pure **Pareto** question:

* In the `(S, H)` plane keep only the **frontier** — points not dominated
  (smaller `S`, smaller `H`).  It answers "given an `S`-byte budget, what is the
  best `H`?", and each frontier point is a `(N, k)` pair.
* Because the data is effectively unlimited, there is **no interior optimum from
  a trade-off with the data**: for any fixed `S` the question is just which
  split of that budget between `N` and `k` minimises `H`, and whether the answer
  is the same at every scale (the constant-ratio hypothesis).  What limits us in
  practice is only the largest `N` and `k` we can build and afford.

## Do we need held-out entropy?  (checked — barely)

The obvious worry is that training `H(next | cluster)` is monotone decreasing in
both `N` and `k`, so the training frontier degenerates to `k = n_ctx`, and the
study is meaningless.  We therefore measured **held-out** entropy directly, by
binomial thinning of the counts: each occurrence is independently assigned to
train / test (p = 1/2), the clusters are fit on the *train* counts, and the
held-out cross-entropy `-Σ_test log2 P_cluster(successor)` is accumulated on the
*test* counts.  (This is a clean held-out split and needs only the aggregated
count matrix.)

Result (pre-expansion check): `H_held ≈ H_train` to **≤ 0.005 bits**, all the
way to `k = n_ctx`:

| T | n_ctx | k | H_train | H_held | Δ |
|---:|---:|---:|---:|---:|---:|
| 100000 | 150 | 150 | 3.932 | 3.932 | +0.001 |
| 20000 | 849 | 800 | 3.344 | 3.349 | +0.005 |
| 10000 | 1950 | 1000 | 3.127 | 3.132 | +0.005 |

The reason is structural: the threshold `T` keeps every retained context
*frequent* (≥ `T` occurrences), so its successor distribution is estimated well
even from half the data — over-clustering does not memorise noise.  **So
training `H` is a sound proxy here**, with the caveat that a low threshold
(rare contexts) would eventually overfit and then the held-out harness must be
used.  Keep the harness as a check anyway.

Consequence for the study: the raw `H(next | cluster)` curve keeps falling as
`k` grows all the way to `k = n_ctx` with no penalty, so every point on the
`(S, H)` frontier is a genuine data point, and the frontier's *shape* (where it
bends, and the `k/N` it implies) is the whole question.

## Data

Per threshold `T` we need the `H(next | cluster)` vs `k` curve, together with
`N`, `n_ctx`, `H(next)` and `H(next | substring)` (the `k = 1` and `k = n_ctx`
limits).  All eight thresholds were measured on the 10-ecosystem corpus,
spanning `N = 278 … 80,869`, and the sweep covers
`k = 8, 16, 32, 64, 128, 256, 512` (`256` at `T = 100000`, where `n_ctx = 260`).
The per-threshold `successor_distributions.tsv` under `work/common<T>` predate
the corpus rebuild and have been deleted; the recipe below regenerates them.
The lowest swept entropy is `2.609` bits at `T = 500, k = 512`, against a floor
of `2.370`; the caps are the largest runs this box affords at the tail
thresholds, and the consequence is discussed under *Results*.

## Method

1. **Grid.**  For each `T`, sweep `k` over a log-spaced grid from 8 up to 512
   (256 at `T = 100000`), clipped at `n_ctx` where smaller.  Record
   `(N, n_ctx, k, H)`.
2. **Points.**  Map each run to `(S = 16N + 128k, H)`.
3. **Frontier.**  Sort by `S`, take the lower envelope of `H`.
4. **Fit** the frontier, e.g. `H ≈ a − b·S^{-c}`, and tabulate the `(N, k)`
   pairs and their ratio `k / N` along it; also report the local slope
   `dH/dlog₂S` (bits saved per doubling of the model) to expose diminishing
   returns.
5. **Test the hypothesis** `k / N ≈ const`: regress `log k` on `log N` along the
   frontier; a slope near 1 with a tight intercept supports it.  Report the
   ratio and its spread, and whether it drifts with `S`.
6. **Budget table.**  For a few model-size budgets `S`, report the frontier's
   best `(N, k)` — the practical form of the answer.

## Sensitivity and controls (optional follow-ups; not run here)

* **Ratio.**  Rerun the frontier with cluster costs 32/64/128/512 bytes (ratio
  2…32) and report how the `k/N` ratio scales — expect `k / N ∝ 1 / (cluster
  cost)`.
* **Restarts.**  Report the best-of-`R` spread; flag grid points where restarts
  disagree by more than ~0.01 bits.
* **`k ≤ n_ctx`.**  Near the cap the model approaches the exact context model
  (`H → H(next|substring)`); mark this corner, since the frontier flattens there.
* **Tail thresholds.**  Confirm `H(next|substring)` stays monotone in `N`
  (a stale table once broke this — see below).

## Deliverables

1. A table of frontier `(T, N, k, S, H)`, `k / N` and `dH/dlog₂S` — produced by
   `scripts/cluster_size_frontier.py` (26 points; the script's stdout is the
   table).
2. A budget table: the best `(N, k)` at a few model sizes and the implied
   `k / N` — in the Results section below.
3. A figure: `S` (bytes, log axis) against bits/character, one curve per `N`,
   with the Pareto frontier drawn through them.  Not yet plotted; the table in
   (1) is the data for it.

## Results

`scripts/cluster_size_frontier.py` turns the sweep log into the frontier.  All
eight thresholds are covered, giving **26 frontier points** spanning
`S ≈ 5.5 kB` to `S ≈ 1.36 MB`.  The frontier is a staircase of per-`T` curves,
so the question is where it turns and what `k / N` it implies there.

At the endpoints the exact-context floors are:

| T | N | n_ctx | H(next) | H(next\|substring) |
|---:|---:|---:|---:|---:|
| 100000 | 278 | 260 | 4.969 | 3.778 |
| 50000 | 613 | 570 | 4.969 | 3.523 |
| 20000 | 1,788 | 1,656 | 4.969 | 3.163 |
| 10000 | 3,935 | 3,646 | 4.969 | 2.939 |
| 5000 | 8,038 | 7,335 | 4.969 | 2.758 |
| 2000 | 20,198 | 18,099 | 4.969 | 2.572 |
| 1000 | 40,168 | 35,362 | 4.969 | 2.466 |
| 500 | 80,869 | 69,744 | 4.969 | 2.370 |

`H(next)` is a property of the corpus, not of the vocabulary, so it is the same
for every threshold; `H(next | substring)` is the payoff of a larger vocabulary,
falling by 1.41 bits from `N = 278` to `N = 80,869`.  A bigger `N` therefore both
sharpens the target and costs 16 bytes a context, and the frontier is the trade
between that and the 128-byte clusters.

The best model within a size budget — the practical answer — is:

| budget `S` | `T` | `N` | `k` | `k/N` | `H` |
|---:|---:|---:|---:|---:|---:|
| 20 kB | 50000 | 613 | 64 | 0.104 | 3.916 |
| 50 kB | 20000 | 1,788 | 128 | 0.072 | 3.525 |
| 100 kB | 10000 | 3,935 | 256 | 0.065 | 3.216 |
| 200 kB | 5000 | 8,038 | 512 | 0.064 | 2.957 |
| 400 kB | 2000 | 20,198 | 512 | 0.025 | 2.780 |

**Answer to the hypothesis.**  The *budget-optimal* `k/N` is **not constant**
along the frontier: it falls monotonically from 0.10 at 20 kB to 0.03 at 400 kB,
i.e. from about ten substrings per cluster to about forty.  The drift is slow
enough that "`k ≈ N/10` at the small end, `k ≈ N/40` at the large end" is a
serviceable rule of thumb, but the earlier claim of a fixed `k/N ≈ 0.045` over a
wide band was an artefact of the pre-expansion vocabulary sizes: at those `N`,
20–100 kB happened to sit where the ratio was flat.  The raw pointwise span along
the frontier is 0.003–0.460; the extremes are the very small models at the bottom
and the capped grid at the top, not useful operating points.

**Remaining limitation.**  Every threshold is swept to `k = 512` (`T = 100000`
stops at 256, its `n_ctx`), which is short of `n_ctx` for the tail thresholds,
so the frontier does not reach the exact-context floor there: the lowest swept
`H` is 2.609 (`T = 500, k = 512`) against 2.370.  Extending `k` at `T = 500`
would lower the large-`S` end by at most 0.24 bits, at a model size already
beyond a megabyte; it cannot change the small-`S` answer, which is where the
model would have to live.

### Pre-expansion record

The first sweep (2026-10-29, 3.8 M-identifier corpus) produced 77 frontier points
over the same eight thresholds, with floors `H(next) = 4.966` and
`H(next | substring)` 3.932 / 3.711 / 3.344 / 3.070 / 2.856 / 2.611 / 2.477 /
2.363 for `N = 159` / 316 / 911 / 2,102 / 4,478 / 11,758 / 23,284 / 46,346
(`n_ctx` 150 … 42,895).  Its budget table was 20 kB → `T = 20000, k = 40`
(3.891); 50 kB → `10000, k = 100` (3.505); 100 kB → `5000, k = 200` (3.191);
200 kB → `5000, k = 768` (3.004); 400 kB → `2000, k = 1536` (2.736); 600 and
800 kB → `1000, k = 1536` (2.628), i.e. `k/N` ≈ 0.045 across 20–100 kB and a
staircase above 150 kB where the frontier switched to a larger `N`.  The grid
re-measure above reproduces the shape and the direction of the drift, and
replaces the numbers.

## Notes for the "distant future" encoding

* We have deliberately rejected storing occurrence frequencies and Huffman /
  arithmetic tables; this study is about the *clustered successor* model, whose
  whole size is `16N + 128k`, not a code table.
* The final scheme also needs the top-level 64-bit codeword plan and the
  hash + global-dictionary fallback; `(N, k)` is only the model-size part of
  the budget.  When that lands, the byte cost should be reconciled with the
  actual bit budget (64 bits) rather than the placeholder 16/128.
* `scripts/cluster_size_frontier.py` is the analysis entry point; the sweep
  itself is just `cluster_substrings.py --k K` over a grid of `K` and `T`.
