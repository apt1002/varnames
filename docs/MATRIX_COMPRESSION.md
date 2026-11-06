# Compressing the word × word matrix directly

Status: **closed, negative.**  Storing the largest `N` observed cells verbatim
and modelling the rest with the independence prior is the natural direct coding
of the largest table.  The residual after any low-rank / marginal fit is *not*
sparse, and at the grid direct coding is behind the block model even under the
counting convention that ignores the cost of naming the coded cells.  Neither
route gives a compact, near-lossless table.

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

It is not.  On `work/tw4096ns` (`scripts/matrix_compress.py --residual`,
`kappa = 300`):

* the raw observed matrix is very concentrated — 50% of the mass sits in 10,916
  cells (0.6% of the support, 0.07% of `V²`), 90% in 467,979 cells (2.8% of
  `V²`), 99% in 1.60M cells (9.5% of `V²`);
* but the residual after a Hellinger fit is *not* concentrated.  A rank-4 fit
  leaves `|rel Fro| = 0.18`, yet 90% of `|residual|` is spread over 1,383,920
  cells (8.3% of `V²`); rank-256 (`|rel Fro| = 0.078`) spreads 90% over 2,187,369
  cells (13.0%); the rank-1 marginal fit (`|rel Fro| = 2.32`) spreads 90% over
  3.73M cells (22%).  Every fit leaves its error everywhere — there is no small
  set of "probable entries" to code separately and correct.

The scheme that *does* work is to store the `N` largest observed cells verbatim
and give every other cell the prior.  For the cyclic matrix `M_mar` is the
rank-1 **independence** prior `(r/T)(c/T)ᵀ` (`r = c =` the unigram counts), so
"the `M_mar` fallback" models each uncoded cell by the product of its marginals:
the scheme is *top-`N` cells + independence prior*, row-normalised.  Held-out
bits vs `N` (`scripts/matrix_compress.py`, stride-20 validation, `kappa = 300`;
full table 42.08 bits, prior-only fallback 54.60):

| `N` coded | bits (Δ vs full) | % of `V²` |
|---:|---:|---:|
| 100 | 56.07 (+13.98) | 0.00% |
| 1,000 | 56.46 (+14.38) | 0.01% |
| 4,000 | 55.20 (+13.11) | 0.02% |
| 10,000 | 52.74 (+10.66) | 0.06% |
| 30,000 | 49.21 (+7.13) | 0.18% |
| 100,000 | 46.24 (+4.16) | 0.60% |
| 300,000 | 44.09 (+2.00) | 1.79% |
| 800,000 | 42.75 (+0.67) | 4.77% |
| all support (1,813,165) | 42.09 (+0.01) | 10.81% |

The table is only **mildly** compressible.  Staying within ~1 bit of the full
table needs between 300,000 and 800,000 cells — 2–5% of `V²`, 17–44% of the
support, and ~93–99% of the mass.  That is a ~2–5× reduction in stored cells,
against the ~9,000 numbers of the `k = 32` block model: nowhere near a compact
standard.

Bolting exact cells onto the compact *block* model instead of the independence
prior does not help either (`scripts/matrix_compress.py --fallback cluster`):
code the `N` largest cells at their empirical value and model the rest with the
`k = 32` `assoc` table.  The block model alone is 51.14 bits; adding **all**
1,813,165 support cells still leaves 43.13 bits, i.e. `+1.05` above the full
table (and at `N = 300,000`, `+1.60`).  The block model assigns non-trivial mass
to the unsupported cells inside almost-full blocks, and verbatim cells cannot
recover it; at equal `N` the independence prior is the better fallback.

So direct compression trades a fixed ~1 bit for a table still ~30–90× the block
model's size; the block model trades ~9 bits for ~9K cells.  Neither route alone
yields a compact, near-lossless table — the block model wants a small `k`,
direct coding wants a large `N`, and the two curves cross well above the
projected budget.

### Top-`N` cells vs the block model at *matched size*

The curve above is read by *matched accuracy*: to reach the block model's
accuracy the top-`N` table needs ~300–800K cells.  Read the other way — at
*matched model size* — whether a top-`N` table is competitive with the cluster
model at its operating point.  On `work/tw4096ns` (stride-20 validation) the
block models' stores are `k² + 2V`:

| model | store (numbers) | held-out bits |
|---|---:|---:|
| top-`N`, `N = 1,000` + independence prior | 1,000 | 56.46 |
| top-`N`, `N = 10,000` + independence prior | 10,000 | 52.74 |
| co-clustering, `k = 16` | 8,448 | 51.36 |
| co-clustering, `k = 32` | 9,216 | 51.14 |
| top-`N`, `N = 30,000` + independence prior | 30,000 | 49.21 |
| co-clustering, `k = 64` | 12,288 | 50.42 |

At `tw2040` this comparison was a tie (top-`N` at `N = 15 233` gave 54.24
against the block model's 55.35); **at the grid the tie breaks towards the block
model**.  At ~9–12K stored numbers the block model codes 50.4–51.4 bits where a
top-`N` table of the same size codes ~52.7–53 — a 1.5–2 bit edge.  Beyond that
the top-`N` curve does keep falling (49.2 at 30,000 numbers, 46.2 at 100,000)
and the block model needs a finer `k` for the same store, so the curves cross
somewhere well above the project's budget; the crossing moves further out again
under the naming cost below.  The reason for the shift at the grid is the
concentration result above: at `V = 4,096` the mass is spread over enough cells
that a small `N` starts from a poor prior-only baseline (54.60), while the block
model pools whole blocks from the first cluster.

**The naming cost points the same way, only harder.**  `k² + 2V` counts only
*entries*: the block matrix's positions are implied by a dense `k × k` array,
and the cluster labels cost only `V·log₂k` (≈ 8,192 × 5 = 41 kbit at `k = 32`).
The top-`N` scheme must *additionally transmit which* `N` of the `V²` cells are
coded — a subset entropy of `≳ N·log₂V² ≈ N·24` bits, i.e. 240 kbit at
`N = 10,000`, ~6× the cluster labels.  So the block model keeps an edge under a
bit-accurate accounting as well, and neither is near the full table.
