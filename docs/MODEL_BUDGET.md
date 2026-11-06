# Model size in bytes, word list included

Status: **results (revised).**  The clustering notes measure the model in
"numbers" (`k² + 2V`); this note replaces that with an end-to-end **byte** count
of a practical in-memory representation, so the word list can be charged for and
the size compared against the project's budget.  It also costs the word list
itself three ways, which is where the remaining slack is.

## What the decoder stores

| object | representation | cost |
|---|---|---|
| word list — structure | one merge rule per word: two child indices (or a run base + lengths) | see below |
| word list — unigram | the `V` word probabilities, stored in creation order | `V` bytes (raw), ~0.7 `V` (entropy-coded) |
| membership | the two maps word → left/right cluster | `2V · ⌈log₂k / 8⌉` B |
| block | the `k × k` cluster-pair table, one byte per cell | `k²` B |

The 63 characters are implicit in the identifier syntax and cost nothing, and
anything derivable at load time — notably the *cluster* → list-of-words index
(`V log₂V` bits at runtime) — is not charged.  The program code is allowed 2 kB.
Probabilities are quantised to one byte per number on the logarithmic grid
`P ∝ exp(byte/resolution) − 1`, `resolution = 12`; this is **free** to within
0.01 bits (`model_fit_rates.py`).

## The word list

### Child indices

Every child index is `< s`, the number of symbols defined when its rule was
created (children always precede their parent), so `s ≤ V` and the naive
`⌈log₂V⌉` is not the right cost.  Coding the index stream three ways
(`scripts/model_budget.py --index-code`):

| `V` | fixed `⌈log₂V⌉` | variable `⌈log₂s⌉` | Zipf `p(j) ∝ (j+1)^−0.7` | empirical optimum |
|---:|---:|---:|---:|---:|
| 2,104 | 5.4 kB | 4.8 kB | **4.5 kB** | 4.2 kB |
| 4,478 | 13.0 kB | 11.5 kB | **10.6 kB** | 9.9 kB |
| 11,758 | 38.4 kB | 34.5 kB | **30.9 kB** | 29.3 kB |

So the answer to "can we get away with fewer than `log V` bits" is **yes, about
20 % fewer**, but almost all of it comes from coding the *skew within* `[0, s)`,
not from `s < V`: variable-width buys only ~10 %, and a two-parameter Zipf prior
over the index range buys another ~10 % at no side-information cost.  The
empirical optimum (`H = 10.3` bits/child) is a further 5 % away and would need
the distribution stored, so it is not worth it.  Two tempting ideas do **not**
work: the *unigram* distribution is a poor code for child indices (43.4 kB at
`V = 11 758`, worse than plain uniform — the two distributions are unrelated),
and the children come in index order only 54–58 % of the time, so there is no
triangular saving.

### Unigram probabilities

**The word list is in *creation* order, and that is not unigram order.**  The
greedy rule selects the most frequent *pair* of adjacent symbols, so the sequence
of **selection counts** is monotone non-increasing — but the stored unigram is
the word's count in the **final** segmentation, and a word created early keeps
being absorbed into longer words later, by an amount that is not monotone in the
creation index.  So the guarantee does not hold, even when the dictionary and
the counts come from the same corpus:

| build | adjacent rises | mean rank displacement |
|---|---:|---:|
| `tw2040s0` (`V = 2 104`, full corpus) | 548 / 2 039 (26.9 %) | 20.9 % of `V` |
| `tw11694s0` (`V = 11 758`, full corpus) | 3 039 / 11 693 (26.0 %) | 16.9 % of `V` |
| `tw11694` (5 % stride build) | 5 785 / 11 693 (49.5 %) | 19.3 % of `V` |

The counterexample is stark.  In `tw2040s0` the first created words are
`er` 73 989, `es` 57 952, **`on` 28 624, `at` 34 669**, `in` 42 286, …,
`al` 52 119, **`ed` 117 676**.  `on` was merged *before* `at`, so at that moment
`on` was the more frequent pair — yet in the final segmentation `at` outnumbers
it, because `on` is absorbed into longer words (`only`, `once`, `control`, …)
far more heavily.  (The sampling mismatch does add disorder — a stride build
doubles the rise rate — but it is not the cause.)

The order is semantic — the tokeniser merges the lowest-ranked adjacent pair
first — so it cannot be renumbered without changing the tokenisation, and
storing the permutation would cost `V log₂V` bits, four times the unigram
itself.

Costed honestly it is `V` bytes (11.5 kB at `V = 11 758`); entropy-coding the
byte grid (5.4–5.8 bits/value) brings it to **8.3 kB**.  Not negligible, but the
second-smallest of the four objects.

## Model size

Zipf index code, raw-byte unigram, +2 kB code:

| `V` | k=26 | 52 | 105 | 210 |
|---:|---:|---:|---:|---:|
| 2,104 | 12.3 | **14.3** | 22.9 | 55.7 |
| 4,478 | 22.6 | 26.1 | **35.3** | 68.7 |
| 11,758 | 61.0 | **64.2** | 75.2 | 110.3 |

(kB; `scripts/model_budget.py`.)

## Byte frontier with the 64-bit fit

Held-out validation at stride 40 (`n = 5 739`), `kappa = 300`; bits and fit rates
from `scripts/model_fit_rates.py`.  ★ = not beaten by any smaller model.

| size | `V` | `k` | mean bits | fit ≤64 | fit ≤128 | |
|---:|---:|---:|---:|---:|---:|---|
| 14.3 kB | 2,104 | 52 | 56.72 | 70.4 % | 97.0 % | ★ |
| 22.9 kB | 2,104 | 105 | 55.48 | 71.8 % | 97.3 % | ★ |
| 26.1 kB | 4,478 | 52 | 51.75 | 76.3 % | 98.1 % | ★ |
| 35.3 kB | 4,478 | 105 | 51.10 | 77.0 % | 98.2 % | ★ |
| 64.2 kB | 11,758 | 52 | 47.21 | 82.5 % | 98.9 % | ★ |
| 75.2 kB | 11,758 | 105 | 46.90 | 82.9 % | 98.9 % | ★ |

The full tables are far larger and their fit rates are the ceilings:
`V = 2 104` 4.2 MB / 85.1 %, `V = 4 478` 19.1 MB / 89.4 %,
`V = 11 758` 131.8 MB / 93.5 % (≤64 bits).  Those rates use stride 40;
[`BUDGET64_STUDY.md`](BUDGET64_STUDY.md) repeats them at stride 10 and the two
largest move up by under a point (77.8 % and 83.2 %).

### The frontier along `k` — an interior slice

The frontier above is a set of points at different `V`; anything priced against
it (C26's shared clusters, C27's reservation, C28's quarters) was compared with
a *slope* obtained from two of those points.  `scripts/k_frontier.py` sweeps `k`
at fixed `V` with the same accounting and the same held-out set, which turns the
slope into a curve.  `V = 4096`, stride 100 (`n = 4,227`):

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 16 | 51.294 | 78.5 % | 97.9 % | 15,612 |
| 24 | 51.191 | 78.5 % | 98.1 % | 16,529 |
| 32 | 51.071 | 78.7 % | 98.0 % | 17,400 |
| 48 | 50.708 | 79.3 % | 98.1 % | 19,275 |
| 64 | 50.337 | 79.8 % | 98.1 % | 21,488 |
| 96 | 50.043 | 80.4 % | 98.2 % | 27,199 |

| step | Δbits | Δbytes | kB/bit | Δ fit ≤64 | kB per point |
|---|---:|---:|---:|---:|---:|
| 16→24 | −0.103 | +917 | 8.9 | +0.0 | — |
| 24→32 | −0.120 | +871 | 7.2 | +0.2 | 5.3 |
| 32→48 | −0.363 | +1,875 | 5.2 | +0.7 | **2.8** |
| 48→64 | −0.371 | +2,213 | 6.0 | +0.5 | 4.7 |
| 64→96 | −0.294 | +5,711 | 19.4 | +0.6 | 9.3 |

Three things follow.

* **The curve is not straight.** The marginal cost per fit point ranges from
  2.8 kB (32→48) to 9.3 kB (64→96), a factor of 3.3.  The average over
  `k = 32..64` is 3.4 kB/pt, which *understates* the last step by 2.7x and
  overstates the cheapest step by 1.2x.  Since every pricing decision uses a
  local slope, the neighbouring segment has to be quoted, not the average.
* **The knee is at `k ≈ 64`**, where the `k²` cluster-pair table starts to
  dominate: bytes per step go 871 → 1,875 → 2,213 → 5,711 while the bit gain
  stays flat at ≈0.3–0.37 per step.  Buying `k` beyond 64 is the worst
  available use of bytes on this grid.
* **Fit ≤128 is saturated** (97.9–98.2 % across the whole sweep), so every
  trade here is a 64-bit trade.  A byte spent for a 128-bit gain is worth
  nothing.

The earlier two-point estimates (4.5–5.8 kB/pt for `k = 32 → 64`, 3.9 kB/pt for
`V = 4096 → 8192`) sit inside this range and are consistent with it; the sweep's
value is not that they were wrong but that the *sign* of the error is now known.

**This is a slice, not the frontier.**  The frontier is the envelope over `V` as
well as `k`, and the earlier finding stands: **`V` is the productive direction
and `k` is not.**  In this document's own table, `k = 52 → 105` costs 8.6–9.2 kB
for 0.7–1.4 points (6–13 kB/pt), while `V = 2 104 → 4 478` at `k = 52` costs
11.8 kB for 5.9 points (2.0 kB/pt).  The reason is mechanical, not accidental: a
bigger word list shortens identifiers — held-out mean length falls 4.70 → 4.05
tokens from `V = 4096` to `8192` — and the 64-bit budget is dominated by the
*long* identifiers, so `V` attacks the part of the distribution the threshold
measures.  A finer `k` only shaves 0.3–0.4 bits off the conditional entropy of
tokens already inside an identifier.

So the sweep answers a narrower question than "where is the frontier": it says
what the *next* kilobyte buys **at fixed `V`**, which is the right comparison for
a candidate that adds bytes to an existing model (C26's shared clusters, C27's
reserved cell, C28's quarters) but the wrong one for "should this model be
bigger".  Read it that way and the two pictures agree: the k-curve is interior to
the V-envelope, and its local slope (2.8 kB/pt at `k = 32 → 48`) is the
opportunity cost of spending a kilobyte *inside* a model rather than replacing
it.

The gap in the record is that the envelope is only sampled at six points, one per
`V`, all at `k ≈ 52` or 105.  The configuration that would test the `V`-first
policy directly — same bytes, more words versus more clusters — is a `k` sweep at
`V = 8192`: `k = 16` there costs ≈32 kB, the same budget as `V = 4096, k = 48`
(19.3 kB) plus slack, and the comparison has never been run.

## What it shows

* **Cheaper coding moves the whole frontier, and it is the word list that
  moves.** The structure + unigram of the list fell from 57.1 kB to 39.2 kB at
  `V = 11 758` — the model at `k = 52` went from 84.7 kB to 64.2 kB. The
  `k = 840` block table alone is still 706 kB, so "buy words, keep `k` small"
  holds more strongly than ever: `V = 2 104 / k = 840` (703 kB, 48.7 bits) is
  dominated by `V = 11 758 / k = 52` (64 kB, 47.2 bits).
* **The frontier is now 14 kB / 70 %, 35 kB / 77 %, 64 kB / 83 %** for 64-bit
  coverage — the 83 % figure needs 64 kB, comfortably inside the "50 kB-ish is
  acceptable if it rescues the 64-bit set" band.
* **Size is not what costs the 64-bit set — clustering is.** The full table at
  `V = 2 104` fits 85.1 %, the clustered models that fit in 14–23 kB fit
  70–72 %; `V = 4 478` 89.4 % → 77 %; `V = 11 758` 93.5 % → 83 %.
* **Membership is now the second-largest item and the next thing worth
  attacking**: `2V · ⌈log₂k / 8⌉` is 17.6 kB at `V = 11 758, k = 52`, more than
  the unigram and half the index stream.

## Rejected / not done

* Reordering the word list by unigram — not possible without changing the
  tokenisation; the list is in creation order (measured above).
* A unigram-derived code for the child indices — worse than uniform.
* Storing the empirical child-index distribution — 5 % of the index stream,
  paid for by storing the distribution.
* Entropy-coding the *index stream* beyond the two-parameter Zipf prior.
* A cluster → members index: derivable at load time, not charged.
