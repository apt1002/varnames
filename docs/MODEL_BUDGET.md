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
