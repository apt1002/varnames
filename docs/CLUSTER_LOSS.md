# Where the co-clustering loss lives, and the structure of a high-loss block

Status: **results, negative for per-block corrections.**  Two questions about the
`assoc` block model of [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md): *which* of its
`k × k` cells carry the ~11 bits/identifier it costs against the full table, and
whether the worst cells have structure a cheap correction could exploit.  The
answers: the loss is spread across the whole low-mass tail (not parked in a few
bad cells), and the worst blocks are neither low-rank nor sparsely deviating.

## Setup

`V = 2,104` (`work/tw2040`), `kappa = 300`, held-out validation at stride 40
(`n = 5,739` identifiers, 38,805 word bigrams).  The loss of a bigram `a → b` is

```
loss(a→b) = log2 P_table(b|a) − log2 P_assoc(b|a) ≥ 0,
```

attributed to the cell `(lcl(a), rcl(b))` — the storage unit the constraint acts
on.  `scripts/cluster_loss_attribution.py`.

## C21 — which cells carry the loss

Totals at `k = 52`: full table 45.86 bits/id, `assoc` 56.72, **net loss
10.85 bits/id**.  The net hides a large cancellation:

| | bits/id | share of bigrams |
|---|---:|---:|
| gross loss | **+12.48** | 75.1 % |
| gross gain | **−1.63** | 24.9 % |

So on a quarter of observed bigrams the block model is actually **better than the
table** — pooling a sparse row estimates it more sharply than the row's own
smoothed counts.  Only the +12.48 is "fixable".

**The loss is broad, not concentrated.** Sorted by cell mass, the top 5 % of
cells hold 65.8 % of the bigrams but carry only 40.0 % of the loss; the top 10 %
hold 80.7 % of bigrams and carry 61.5 % of the loss.  Loss lags mass everywhere.

Mean excess bits per bigram, by mass decile (`k = 52`):

| mass decile | cells | bigrams | loss share | bits/bigram |
|---:|---:|---:|---:|---:|
| 1 (heaviest) | 140 | 25,827 | 40.8 % | **0.98** |
| 2 | 140 | 5,771 | 21.9 % | 2.36 |
| 3 | 139 | 2,811 | 13.0 % | 2.87 |
| 4 | 139 | 1,664 | 8.7 % | 3.26 |
| 5–10 | 695 | 2,732 | 15.6 % | 3.2–3.9 |

The heaviest cells are modelled *well* (~1 bit/bigram); past decile 3 the
per-bigram loss is **flat at ~3.5 bits across the entire tail**.  There is no
small set of pathological cells to special-case.

**The junk clusters are exonerated.** The five smallest left clusters (2–8
words) carry 0.0–0.2 % of the loss each; the largest carry 3–11 %, roughly in
proportion to their mass.  The loss is not a small-cluster artefact.

The worst *cells*, for orientation (`k = 52`, `|A| × |B|` = left × right cluster
size):

| cell | \|A\|×\|B\| | bigrams | loss | bits/bigram | `D` |
|---|---|---:|---:|---:|---:|
| 2,48 | 69×121 | 429 | 923 | 2.15 | 2.09 |
| 4,48 | 114×121 | 370 | 871 | 2.35 | 1.06 |
| 4,0 | 114×348 | 192 | 828 | 4.31 | 0.57 |
| 48,3 | 45×94 | 265 | 793 | 2.99 | 3.97 |
| 12,0 | 14×348 | 2545 | 520 | **0.20** | 4.12 |

Note the contrast between the last two: cell `12,0` is the heaviest in the data
yet costs only 0.20 bits/bigram, while `4,0` — a *many-word* left cluster — costs
4.31.  That is the mechanism in one line: **the loss is the heterogeneity of a
many-word left cluster**, i.e. the residual error of the clustering itself.

## C22 — what one high-loss block looks like

Inside a cell the model says

```
P(v | u) = c[v] / C[j]    for every u in the left cluster, v in the right
                          cluster j,
```

a **row-independent** shape: every left-word gets the global unigram restricted
to the right cluster.  So the block is worth a cheaper storage only if the true
`P(v|u)` is low-rank (rank-truncate it) or the deviation `D[u,v] = P(v|u) −
c[v]/C[j]` is sparse (store a few big entries).  `scripts/block_structure.py`;
`rank1…r8` are the energy fractions captured by the leading singular values,
`dev1%`/`dev10%` the share of `|D|` mass in the largest 1 % / 10 % of cells, and
each is compared against a **permutation null** (same block masses, row identity
destroyed).

| cell | \|A\|×\|B\| | density | tv | rank1 | rank2 | rank4 | rank8 | dev1 % | dev10 % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,48 (loss 923) | 69×121 | 0.28 | 0.67 | 0.40 | 0.50 | 0.63 | 0.78 | 0.32 | 0.67 |
| *null* | | | | 0.07 | 0.13 | 0.23 | 0.39 | 0.24 | 0.62 |
| 4,0 (loss 828) | 114×348 | 0.14 | 0.70 | 0.16 | 0.29 | 0.50 | 0.70 | 0.38 | 0.64 |
| *null* | | | | 0.14 | 0.26 | 0.42 | 0.57 | 0.37 | 0.63 |
| 4,3 (loss 742) | 114×94 | 0.15 | 0.67 | 0.24 | 0.36 | 0.51 | 0.74 | 0.31 | 0.66 |
| *null* | | | | 0.12 | 0.21 | 0.35 | 0.52 | 0.27 | 0.63 |
| 12,0 (loss 520) | 14×348 | 0.42 | 0.57 | **1.00** | 1.00 | 1.00 | 1.00 | 0.29 | 0.58 |
| *null* | | | | 0.78 | 0.83 | 0.90 | 0.97 | 0.20 | 0.60 |
| 20,5 (median mass) | 127×5 | 0.04 | **0.11** | 1.00 | 1.00 | 1.00 | 1.00 | 0.15 | 0.85 |

Three things:

* **Not low-rank.** In the high-loss blocks rank-1 captures 0.16–0.40 of the
  energy (twice the null, so the structure is real, but far from compressible);
  even rank-8 leaves 22–30 %.  The block that *is* rank-1, `12,0`, is the one
  that already costs 0.20 bits/bigram — and it is rank-1 only because it has 14
  rows.
* **Not sparse.** `dev10%` in every real block matches its permutation null to
  within a couple of points (0.64 vs 0.63, 0.67 vs 0.62).  The deviation from the
  row-independent shape is exactly as spread out as chance.
* **The good blocks are row-independent.** The median-mass control
  (`20,5`, 127×5) has `tv = 0.11` — its rows agree with the marginal almost
  perfectly — and costs nothing.  The model is right where the block is simple
  and wrong where the left cluster is heterogeneous.

## What it shows

* The `assoc` loss is the **within-left-cluster heterogeneity** — the residual
  of the clustering — not a handful of bad cells, not the small clusters, and
  not sparse or low-rank anywhere it matters.  A per-cluster-pair "splat" /
  low-rank correction would need about as many numbers as the block has cells,
  so it cannot be cheaper than storing the block.
* The only real lever is `k` itself, and
  [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md) already prices it: at matched model
  size a larger word list beats a finer `k × k` table, so buying back this loss
  with clusters is a bad trade.
* The **25 % of bigrams where the block model wins** is a real effect and sets a
  floor: the net loss (10.85) is smaller than the gross (12.48), and a perfect
  per-cell model could not capture the whole gross without giving the gain back.

## Reproducing

```
python3 scripts/cluster_loss_attribution.py --dir work/tw2040 --ks 52,105 --stride 40
python3 scripts/block_structure.py --dir work/tw2040 --ks 52,105 --auto-top 6 --stride 40
```
