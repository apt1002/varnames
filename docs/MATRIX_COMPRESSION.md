# Compressing the word × word matrix directly

Status: **closed, negative.**  Storing the largest `N` observed cells verbatim
and modelling the rest with the independence prior is the natural direct coding
of the largest table.  The residual after any low-rank / marginal fit is *not*
sparse, and direct coding is only competitive with the block model at *matched
model size* under a counting convention that ignores the cost of naming the
coded cells.  Neither route gives a compact, near-lossless table.

Companion to [`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md) (the
low-rank model) and [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md) (the block model).
`scripts/matrix_compress.py`.

---

## Is the residual sparse?

[`CLUSTER_WORDS.md`](CLUSTER_WORDS.md) concluded that the block (cluster)
model cannot be both small and accurate, so the fallback is to store the word ×
word matrix itself, compressed directly.  The natural scheme is to approximate it
by a low-rank / `M_mar` fit and encode codewords only for the entries where the
fit is off, falling back to the fit for the rest.  That pays only if the
**residual is sparse**.

It is not.  On `tw2040` (`scripts/matrix_compress.py --residual`):

* the raw observed matrix is very concentrated — 50% of the mass sits in 5,749
  cells (0.13% of `V²`), 90% in 178,384 cells (4.03%);
* but the residual after a Hellinger fit is *not* concentrated.  A rank-4 fit
  leaves `|rel Fro| = 0.26`, yet 90% of `|residual|` is spread over 433,845 cells
  (9.8% of `V²`); rank-256 (`|rel Fro| = 0.09`) spreads 90% over 845,859 cells
  (19.1%); the rank-1 marginal fit (`|rel Fro| = 1.58`) spreads 90% over 1.09M
  cells.  Every fit leaves its error everywhere — there is no small set of
  "probable entries" to code separately and correct.

The scheme that *does* work is to store the `N` largest observed cells verbatim
and give every other cell the prior.  For the cyclic matrix `M_mar` is the
rank-1 **independence** prior `(r/T)(c/T)ᵀ` (`r = c =` the unigram counts), so
"the `M_mar` fallback" models each uncoded cell by the product of its marginals:
the scheme is *top-`N` cells + independence prior*, row-normalised.  Held-out
bits vs `N` (`scripts/matrix_compress.py`, stride-20 validation; full tables
45.77 / 54.16 bits):

| `N` coded | `tw2040` bits (Δ) | `tw512` bits (Δ) |
|---:|---:|---:|
| 100 | 63.21 (+17.45) | 79.58 (+25.41) |
| 1,000 | 63.69 (+17.92) | 84.32 (+30.15) |
| 4,000 | 60.10 (+14.34) | 71.36 (+17.20) |
| 10,000 | 55.96 (+10.19) | 63.74 (+9.58) |
| 30,000 | 51.96 (+6.20) | 57.72 (+3.56) |
| 100,000 | 48.82 (+3.05) | 54.34 (+0.17) |
| 300,000 | 46.71 (+0.95) | — |
| 800,000 / all support | 45.77 (+0.00) ‡ | 54.16 (+0.00) |

The table is only **mildly** compressible (‡: 800,000 cells on `tw2040` is 99.7%
of its support).  Staying within ~1 bit of the full
table needs the largest ~300K cells on `tw2040` (6.8% of `V²`, ~37% of the
support, ~97% of the mass), or ~100K cells on `tw512` (30% of `V²`).  That is a
~15× / ~3× reduction in stored cells — nowhere near the ~15K cells of the `k=105`
block model, and far too many for a compact standard.

Bolting exact cells onto the compact *block* model instead of the independence
prior does not help either (`scripts/matrix_compress.py --fallback cluster`):
code the `N` largest cells at their empirical value and model the rest with the `k = 105` `assoc` table.  The
block model alone is 55.35 bits (`tw2040`) / 62.42 bits (`tw512`); adding **all**
802,606 / 149,932 support cells still leaves 47.14 / 55.39 bits, i.e. `+1.38` /
`+1.23` above the full table.  The block model assigns non-trivial mass to the
unsupported cells inside almost-full blocks, and verbatim cells cannot recover
it; at equal `N` the independence prior is the better fallback.

So direct compression trades a fixed ~1 bit for a table still ~14× the block
model's size; the block model trades ~10 bits for ~15K cells.  Neither route
alone yields a compact, near-lossless table — the block model wants a small `k`,
direct coding wants a large `N`, and the two curves cross well above the
projected budget.

### Top-`N` cells vs the `k = 105` block model at *matched size*

The curve above is read by *matched accuracy*: to reach the block model's
accuracy the top-`N` table needs ~300K cells.  Read the other way — at *matched
model size* — the two curves answer whether a top-`N` table is competitive with
the cluster model at its operating point.  On `tw2040` (stride-20 validation)
the `k = 105` model's store is `k² + 2V = 15 233`:

| model | store (numbers) | held-out bits |
|---|---:|---:|
| top-`N`, `N = 10 000` + independence prior | 10 000 | 55.958 |
| top-`N`, `N = 15 233` + independence prior | 15 233 | 54.240 |
| co-clustering, `k = 76` | 9 984 | 55.985 |
| co-clustering, `k = 105` | 15 233 | 55.354 |

Under the project's store convention — a model's size is its number of stored
**numbers** — the top-`N` + independence-prior table is *competitive with, and
at equal store slightly better than, the `k = 105` block model*: 54.240 vs
55.354 (~1.1 bits at store 15 233), and at `N = 10 000` it ties `k = 76`
(55.958 vs 55.985, store ~10K).  Both sit ~8.5–10 bits above the full table
(45.77).

**This tie is an artefact of the store convention, and it reverses under a
bit-accurate accounting.**  `k² + 2V` counts only *entries*: the block matrix's
positions are implied by a dense `k × k` array, and the cluster labels cost only
`V·log₂k ≈ 14 kbit`.  The top-`N` scheme must *additionally transmit which* `N`
of the `V²` cells are coded — a subset entropy of `≳ N·log₂V² ≈ N·22` bits, or
≈147 kbit at `N = 15 233`, ~10× the cluster labels.  Charging both models for
their index metadata at equal bits per number, the top-`N` table at matched
*true* size is ~1.3–4 bits **worse** than `k = 105` (e.g. at 8 bits/number the
block model is ~136 kbit total, matched by `N ≈ 5 400` → ≈59 bits).  So it is a
genuine tie in the counting convention this project uses, not a clean compression
win; the block model keeps a small edge once storage is counted honestly, and
neither is near the full table.
