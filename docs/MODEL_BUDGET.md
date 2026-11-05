# Model size in bytes, word list included

Status: **results.** The clustering notes measure the model in "numbers"
(`k² + 2V`); this note replaces that with an end-to-end **byte** count of a
practical in-memory representation, so the word list can be charged for and the
size compared against the project's budget. The word model's *stored* size is
what decides whether a configuration is usable at all, so it belongs next to the
held-out bits, not behind them.

## What the decoder stores

| object | representation | cost |
|---|---|---|
| word list | one fixed-width record per word: left child ‖ right child ‖ unigram byte, padded to whole bytes | `(V − 64)` records |
| unigram | folded into the word record | — |
| membership | the two maps word → left/right cluster, whole-byte labels | `2V · ⌈log₂k / 8⌉` B |
| block | the `k × k` cluster-pair table, one byte per cell | `k²` B |

The 63 characters (letters, `_`, digits) are implicit in the identifier syntax
and cost nothing; the program code is allowed 2 kB. Because the record carries
the unigram byte, the record width is `⌈(2⌈log₂V⌉ + 8) / 8⌉` bytes:

| `V` | index width | record | word list |
|---:|---:|---:|---:|
| ≤ 256 | 8 | 3 B | — |
| 2,104 | 12 | **4 B** | 8.0 kB |
| 4,478 | 13 | 5 B | 21.6 kB |
| 11,758 | 14 | 5 B | 58.5 kB |

There is a cliff at `V = 4096`: 12-bit indices keep the record at exactly 32
bits, one bit more costs 25 % of the whole list. Fixed-width indices are what a
real tokeniser/encoder wants (a variable-width, information-theoretic encoding
is ~25 % smaller but needs an impractical decode structure).

The `assoc` transition probability is

```
P(b | a) = c[b] · D[lcl(a), rcl(b)] / Σ_j D[lcl(a), j] · C[j],
```

so the stored numbers that matter are the unigram `c` and the block table `D`
(the row marginal cancels — see `CLUSTER_WORDS.md`). Probabilities are
quantised to **one byte per number** on the logarithmic grid
`P ∝ exp(byte/resolution) − 1` with `resolution = 12`, the scale inferred per
array from its smallest positive entry.

## Model size

With fixed-width records and the 2 kB code allowance, the total is:

| `V` | k=26 | 52 | 105 | 210 |
|---:|---:|---:|---:|---:|
| 2,104 | 14.7 | **16.7** | 24.8 | 57.1 |
| 4,478 | 32.9 | 34.9 | **43.0** | 75.3 |
| 11,758 | 82.7 | 84.7 | 92.8 | 125.1 |

(kB; `scripts/model_budget.py`.)

## Byte frontier with the 64-bit fit

Held-out validation (`n = 5 739`), `kappa = 300`; bits and fit rates from
`scripts/model_fit_rates.py`. Rows sorted by size; ★ = not beaten by any smaller
model.

| size | `V` | `k` | mean bits | fit ≤64 | fit ≤128 | |
|---:|---:|---:|---:|---:|---:|---|
| 16.7 kB | 2,104 | 52 | 56.72 | 70.4 % | 97.0 % | ★ |
| 24.8 kB | 2,104 | 105 | 55.48 | 71.8 % | 97.3 % | ★ |
| 34.9 kB | 4,478 | 52 | 51.75 | 76.3 % | 98.1 % | ★ |
| 43.0 kB | 4,478 | 105 | 51.10 | 77.0 % | 98.2 % | ★ |
| 75.3 kB | 4,478 | 210 | 50.44 | 78.0 % | 98.2 % | ★ |
| 84.7 kB | 11,758 | 52 | 47.21 | 82.5 % | 98.9 % | ★ |
| 92.8 kB | 11,758 | 105 | 46.90 | 82.9 % | 98.9 % | ★ |

The full tables are far larger and the fit rates there are the ceilings:
`V = 2 104` 4.2 MB / 85.1 %, `V = 4 478` 19.1 MB / 89.4 %,
`V = 11 758` 131.8 MB / 93.5 % (≤64 bits).

## What it shows

* **The word list is small next to the cluster table at large `k`.** At
  `V = 11 758` the list is 58.5 kB, but a `k = 840` block table alone is 706 kB;
  a `k = 420` table is 176 kB, larger than the whole `V = 4 478` model. The byte
  view *reinforces* the word-list conclusion of `CLUSTER_WORDS.md`: buy words,
  keep `k` small. `V = 2 104 / k = 840` (703 kB, 48.7 bits) is dominated by
  `V = 11 758 / k = 52` (85 kB, 47.2 bits) — ten times smaller *and* better.
* **But the word list sets a floor.** A larger vocabulary costs `2V` labels plus
  the records, so `V = 11 758` cannot be had for less than ~83 kB; the
  "93 % ≤ 64 bits" configuration needs ~85–93 kB, not 50 kB.
* **One byte per number is free.** Quantising `c` and `D` to the logarithmic
  byte grid changes the mean by ≤ 0.01 bits and the 64-bit fit by ≤ 0.1 point —
  so the byte counts above stand, and the `k²` block table really is `k²` bytes.
* **Size is not what costs the 64-bit set — clustering is.** The full table at
  `V = 2 104` fits 85.1 %, the clustered models that fit in 17–25 kB fit
  70–72 %; `V = 4 478` drops 89.4 % → 77 %, `V = 11 758` 93.5 % → 82.9 %. The
  128-bit fit barely moves (99.4 % → 98.1 %): the loss lands on the identifiers
  near the 64-bit boundary. So the honest summary is *"82.9 % of distinct
  identifiers in 64 bits for 93 kB"* (`V = 11 758, k = 105`), and *"70.4 % for
  17 kB"* (`V = 2 104, k = 52`) — not the full-table ceilings.

## Rejected / not done

* Variable-width (information-theoretic) indices: ~25 % smaller list, but needs
  a decode structure we would not build.
* Entropy-coding the word list: the merge-rule stream is highly structured, so
  this is the obvious next lever on the list; unmeasured.
* A cluster → members index would speed up decoding but is not charged here (it
  is derivable at load time); if it must be stored it adds ~2–4 `V` bytes.
