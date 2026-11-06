# Where the co-clustering loss lives, and the structure of a high-loss block

Status: **results, negative for per-block corrections.**  Two questions about the
`assoc` block model of [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md): *which* of its
`k × k` cells carry the ~9 bits/identifier it costs against the full table, and
whether the worst cells have structure a cheap correction could exploit.  The
answers are unchanged from the pre-expansion measurement, and now confirmed at
three points of the canonical grid: the loss is spread across the low-mass tail
(not parked in a few bad cells), and the worst blocks are neither low-rank nor
sparsely deviating.

## Setup

`V = 4,096` (`work/tw4096ns`, the `--sample 20 --stride 0` build),
`kappa = 300`, held-out validation at stride 40 (`n = 10,567` identifiers,
60,436 word bigrams).  The loss of a bigram `a → b` is

```
loss(a→b) = log2 P_table(b|a) − log2 P_assoc(b|a) ≥ 0,
```

attributed to the cell `(lcl(a), rcl(b))` — the storage unit the constraint acts
on.  `scripts/cluster_loss_attribution.py`.

## C21 — which cells carry the loss

| `k` | full table | `assoc` | net loss | gross loss | gross gain | cells used |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 42.202 | 51.580 | **9.378** | +11.018 (74.3 %) | −1.640 (25.7 %) | 237 / 256 |
| 32 | 42.202 | 51.355 | **9.154** | +10.772 (74.8 %) | −1.618 (25.2 %) | 621 / 1,024 |
| 64 | 42.202 | 50.623 | **8.421** | +10.028 (74.2 %) | −1.606 (25.8 %) | 1,777 / 4,096 |

The net hides a large cancellation, and the split is remarkably stable across
`k`: on a quarter of observed bigrams the block model is actually **better than
the table** — pooling a sparse row estimates it more sharply than the row's own
smoothed counts.  Only the ~+10 to +11 bits of gross loss is "fixable", and the
gain does not shrink as clusters get finer (it is −1.6 bits at every `k`), so a
perfect per-cell correction could not recover the net loss either.

**The loss is broad, not concentrated.** Sorted by cell mass, at `k = 16` the
top 5 % of cells hold half the bigrams but carry only 21.6 % of the loss; the
top 10 % hold 65.9 % of bigrams and carry 38.2 %.  Loss lags mass everywhere.
Finer tables concentrate both:

| `k` | top 1 % by mass | top 5 % | top 10 % | top 25 % |
|---:|---:|---:|---:|---:|
| 16 | 22.7 % mass → 2.0 % loss | 50.0 → 21.6 | 65.9 → 38.2 | 87.5 → 70.4 |
| 32 | 31.3 → 7.8 | 67.6 → 38.8 | 83.2 → 59.7 | 96.3 → 89.5 |
| 64 | 44.2 → 15.8 | 77.9 → 51.6 | 89.1 → 72.0 | 97.9 → 93.9 |

That is a mechanical consequence of `k`: with more cells each cell is lighter, so
the heaviest ones carry more of the loss.  It does not mean the loss is
fixable — the *per-bigram* cost inside the heaviest decile is ~0.93 bits at all
three `k`, i.e. the cells are modelled as well as they can be, and the total
falls only because there are fewer bigrams in the tail.

Mean excess bits per bigram, by mass decile:

| mass decile | `k = 16` | `k = 32` | `k = 64` |
|---:|---:|---:|---:|
| 1 (heaviest) | **0.935** | **0.999** | **0.933** |
| 2 | 2.301 | 2.302 | 2.481 |
| 3 | 2.792 | 3.819 | 3.226 |
| 4 | 3.569 | 4.172 | 3.648 |
| 5 | 4.084 | 4.270 | 4.202 |
| 6 | 4.354 | 4.592 | 4.235 |
| 7 | 4.396 | 5.098 | 4.373 |
| 8 | 4.482 | 5.123 | 4.088 |
| 9 | 5.087 | 4.264 | 4.082 |
| 10 (lightest) | 4.515 | 4.587 | 4.264 |

The shape is the same at every `k`: one cheap decile, then **flat at ~4–5 bits
across the entire tail**.  There is no small set of pathological cells to
special-case.

**The junk clusters are exonerated.** At `k = 16` the five smallest left clusters
(13–85 words) carry 0.1–2.0 % of the loss each; the largest (964 words, 11,494
bigrams) carries 16.3 %, and the next (945 words) 12.2 %, roughly in proportion
to mass.  At `k = 32` the smallest clusters (1–4 words) carry 0.0–0.1 %; at
`k = 64` (1–2 words) 0.0 %.  The loss is not a small-cluster artefact.

The worst *cells*, for orientation (`|A| × |B|` = left × right cluster size):

| `k` | cell | \|A\|×\|B\| | bigrams | loss | bits/bigram | `D` |
|---:|---|---:|---:|---:|---:|---:|
| 16 | 2,3 | 366×338 | 2,120 | 5,706 | 2.69 | 2.02 |
| 16 | 2,10 | 366×960 | 696 | 3,046 | 4.38 | 0.72 |
| 16 | 2,15 | 366×258 | 730 | 2,792 | 3.82 | 2.35 |
| 16 | 5,14 | 964×335 | 2,429 | 2,656 | 1.09 | 1.97 |
| 32 | 2,26 | 256×371 | 566 | 2,258 | 3.99 | 1.62 |
| 32 | 2,6 | 256×201 | 508 | 1,954 | 3.85 | 2.12 |
| 64 | 2,37 | 227×403 | 410 | 1,606 | 3.92 | 1.26 |

Note the contrast with the heaviest cells of the same table: at `k = 16` the
964-word cluster's row of cells costs ~1.1 bits/bigram on 2,100–2,400 bigrams
each, while cluster `2` (366 words) costs 2.7–4.4.  That is the mechanism in one
line: **the loss is the heterogeneity of a many-word left cluster**, i.e. the
residual error of the clustering itself — and cluster `2` pools 366 words of
mixed shape, so its bigrams are the worst modelled.

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

`k = 16`:

| cell | \|A\|×\|B\| | density | tv | rank1 | rank2 | rank4 | rank8 | dev1 % | dev10 % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,3 (loss 5,706) | 366×338 | 0.15 | 0.700 | 0.281 | 0.433 | 0.538 | 0.663 | 0.408 | 0.743 |
| *null* | | | | 0.225 | 0.268 | 0.341 | 0.419 | 0.347 | 0.719 |
| 2,10 (loss 3,046) | 366×960 | 0.07 | 0.663 | 0.101 | 0.168 | 0.282 | 0.431 | 0.458 | 0.682 |
| *null* | | | | 0.028 | 0.048 | 0.084 | 0.152 | 0.410 | 0.659 |
| 5,14 (loss 2,656) | 964×335 | 0.37 | 0.560 | 0.403 | 0.456 | 0.534 | 0.642 | 0.218 | 0.550 |
| *null* | | | | 0.039 | 0.058 | 0.093 | 0.148 | 0.216 | 0.560 |
| 12,3 (loss 2,462) | 192×338 | 0.12 | 0.781 | 0.143 | 0.212 | 0.328 | 0.474 | 0.441 | 0.751 |
| *null* | | | | 0.042 | 0.073 | 0.127 | 0.226 | 0.364 | 0.726 |
| 2,4 (median-mass control) | 366×32 | 0.03 | **0.252** | 0.626 | 0.735 | 0.894 | 0.967 | 0.433 | 0.811 |

`k = 64` (the finer table behaves the same way):

| cell | \|A\|×\|B\| | density | tv | rank1 | rank2 | rank4 | rank8 | dev1 % | dev10 % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,37 (loss 1,606) | 227×403 | 0.13 | 0.730 | 0.086 | 0.153 | 0.247 | 0.393 | 0.406 | 0.651 |
| *null* | | | | 0.060 | 0.112 | 0.187 | 0.290 | 0.362 | 0.636 |
| 2,48 (loss 1,396) | 227×101 | 0.22 | 0.639 | 0.330 | 0.403 | 0.536 | 0.706 | 0.326 | 0.739 |
| *null* | | | | 0.059 | 0.111 | 0.200 | 0.342 | 0.238 | 0.641 |
| 60,39 (loss 624) | 352×485 | 0.31 | 0.598 | 0.533 | 0.604 | 0.673 | 0.739 | 0.199 | 0.507 |
| *null* | | | | 0.112 | 0.165 | 0.231 | 0.307 | 0.196 | 0.528 |

Three things:

* **Not low-rank.** In the high-loss blocks rank-1 captures 0.09–0.40 of the
  energy (usually 2–4× the null, so the structure is real, but far from
  compressible); even rank-8 leaves 25–60 %.  The one block that is near
  rank-1, `2,4`, is the *low-loss* control — and it is rank-1 because it has 32
  right words.
* **Not sparse.** `dev10%` in the high-loss blocks matches its permutation null
  to within a couple of points (0.743 vs 0.719, 0.651 vs 0.636, 0.550 vs
  0.560).  The deviation from the row-independent shape is exactly as spread out
  as chance.
* **The good blocks are row-independent.** The median-mass control at `k = 16`
  (`2,4`, 366×32) has `tv = 0.252` and pays nothing; the `k = 32` control
  (`5,27`, 505×4) has `tv = 0.014`.  The model is right where the block is
  simple — a small right cluster, or one whose rows share the marginal — and
  wrong where the left cluster is heterogeneous.

## What it shows

* The `assoc` loss is the **within-left-cluster heterogeneity** — the residual
  of the clustering — not a handful of bad cells, not the small clusters, and
  not sparse or low-rank anywhere it matters.  A per-cluster-pair "splat" /
  low-rank correction would need about as many numbers as the block has cells,
  so it cannot be cheaper than storing the block.
* The only real lever is `k` itself, and [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)
  already prices it: at `V = 4096` going `k = 16 → 64` buys 0.96 bits for 45 %
  more storage (8,448 → 12,288 numbers), whereas going `V = 4096 → 8,192` at
  fixed `k = 16` buys 3.87 bits (51.580 → 47.713) for about twice the store.
  Buying back this loss with clusters is the worse trade of the two.
* The **25 % of bigrams where the block model wins** is a real effect and sets a
  floor: the net loss (9.4) is smaller than the gross (11.0), and a perfect
  per-cell model could not capture the whole gross without giving the gain back.

## Pre-expansion record

The C21/C22 measurement that established these conclusions was taken at
`V = 2,104` (`work/tw2040`), `k = 52`, stride 40, `n = 5,739`: full table 45.86,
`assoc` 56.72, net loss 10.85, gross +12.48 on 75.1 % of bigrams and −1.63 on
24.9 %; top 5 % of cells 65.8 % of bigrams and 40.0 % of loss; ranks and
deviations against the null as above.  The grid measurement reproduces every
qualitative claim with the numbers shifted by the smaller table.

## Reproducing

```
python3 scripts/cluster_loss_attribution.py --dir work/tw4096ns --ks 16,32,64 --stride 40
python3 scripts/block_structure.py --dir work/tw4096ns --ks 16,32,64 --auto-top 6 --stride 40
```
