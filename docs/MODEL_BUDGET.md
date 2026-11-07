# Model size in bytes, word list included

Status: **results (grid).**  The clustering notes measure the model in
"numbers" (`k² + 2V`); this note replaces that with an end-to-end **byte** count
of a practical in-memory representation, so the word list can be charged for and
the size compared against the project's budget.  Everything below is measured at
the canonical grid (`V = 4096 / 6144 / 8192`, `kappa = 300`) on the 10× held-out
set (`n = 42,268`), and the inventory is stated once, so that no object is
charged twice.  The pre-grid measurements are kept in "Pre-grid record" at the
end.

## What the decoder stores

| object | representation | cost at `V = 8192, k = 16` |
|---|---|---:|
| word list — rules | one merge rule per word: two child indices, Zipf-coded | 21.1 kB |
| word list — unigram | the `V` word probabilities, in creation order, one byte each | 8.2 kB |
| membership | the two maps word → left/right cluster | 8.2 kB |
| block | the `k × k` cluster-pair table, one byte per cell | 0.3 kB |
| program code | — | 2.0 kB |
| **total** | | **39.8 kB** |

The 63 characters are implicit in the identifier syntax and cost nothing, and
anything derivable at load time — notably the *cluster* → list-of-words index
(`V log₂V` bits at runtime) — is not charged.  Probabilities are quantised to one
byte per number on the logarithmic grid `P ∝ exp(byte/resolution) − 1`,
`resolution = 12`; this is **free** to within 0.01 bits (`model_fit_rates.py`).

This is the **arithmetic** model: the decoder evaluates `P(b | a)` from stored
numbers.  The published-*Huffman* variant stores code lengths instead and is a
**different object**, not an addition to this one — see "The two model shapes"
below.

## The word list

The rule table is the largest single object once it is charged, so its
representation matters.

### Child indices

Every child index is `< s`, the number of symbols defined when its rule was
created (children always precede their parent), so `s ≤ V` and the naive
`⌈log₂V⌉` is not the right cost.  Coding the index stream four ways
(`scripts/model_budget.py --index-code`, and the empirical entropy of the index
histogram for the last column):

| `V` | fixed `⌈log₂V⌉` | variable `⌈log₂s⌉` | Zipf `p(j) ∝ (j+1)^−0.7` | empirical optimum |
|---:|---:|---:|---:|---:|
| 4,096 | 12.1 kB (24.0 b/rule) | 11.2 (22.2) | **9.8 (19.5)** | 9.2 (18.2) |
| 6,144 | 19.8 (26.0) | 17.8 (23.5) | **15.4 (20.2)** | 14.4 (19.0) |
| 8,192 | 26.4 (26.0) | 24.5 (24.1) | **21.1 (20.8)** | 19.9 (19.6) |

So the answer to "can we get away with fewer than `log V` bits" is **yes, about
20 % fewer** (19 / 22 / 20 % from 4,096 to 8,192), but almost all of it comes
from coding the *skew within* `[0, s)`, not from `s < V`: variable-width buys
7–10 %, and a two-parameter Zipf prior over the index range buys another 12–14 %
at no side-information cost.  The empirical optimum is a further 5–6 % away and
would need the distribution stored, so it is not worth it.  Two tempting ideas do
**not** work: the *unigram* distribution is a poor code for child indices (43.4 kB
at `V = 11 758` on the pre-grid build, worse than plain uniform — the two
distributions are unrelated), and the children come in index order only 54–55 %
of the time (`a < b` 55.4 / 54.9 / 53.8 %), so there is no triangular saving.

`k_frontier.py` and the table below use the Zipf code, which is what the byte
figures charge.

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
| `tw4096ns` (`V = 4 096`) | 1 998 / 4 031 (49.6 %) | 17.9 % of `V` |
| `tw6144ns` (`V = 6 144`) | 2 978 / 6 079 (49.0 %) | 16.7 % of `V` |
| `tw8192ns` (`V = 8 192`) | 3 976 / 8 127 (48.9 %) | 15.8 % of `V` |

(`scripts/wordlist_order.py`.  All three are `--sample 20` builds, and the
sampling mismatch roughly doubles the rise rate: the full-corpus `s0` builds
measured 26–27 %.  The displacement is the robust figure.)

The counterexample is stark.  The first created words are `er` 66 665,
`on` 29 190, `es` 51 855, `at` 29 429, `in` 37 791, `en` 28 996 — so `on` was
merged *before* `es`, and at that moment `on` was the more frequent pair, yet in
the final segmentation `es` outnumbers it 1.8 to 1, because `on` is absorbed into
longer words (`only`, `once`, `control`, …) far more heavily.

The order is semantic — the tokeniser merges the lowest-ranked adjacent pair
first — so it cannot be renumbered without changing the tokenisation, and
storing the permutation would cost `V log₂V` bits, four times the unigram
itself.

Costed honestly it is `V` bytes (4.1 / 6.1 / 8.2 kB).  Entropy-coding the byte
grid (5.4–5.8 bits/value on the pre-grid builds, i.e. ~0.7 `V`) would bring it
to 2.9 / 4.3 / 5.7 kB; that refinement is not charged anywhere below.

## Model size at the grid

Zipf index code, raw-byte unigram, +2 kB code (`scripts/model_budget.py`):

| `V` | `k` | rules | unigram | members | block | code | total |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | 16 | 9.8 | 4.1 | 4.1 | 0.3 | 2.0 | **20.3 kB** |
| 4,096 | 32 | 9.8 | 4.1 | 5.1 | 1.0 | 2.0 | 22.0 |
| 4,096 | 64 | 9.8 | 4.1 | 6.1 | 4.1 | 2.0 | 26.1 |
| 6,144 | 16 | 15.4 | 6.1 | 6.1 | 0.3 | 2.0 | 29.9 |
| 6,144 | 32 | 15.4 | 6.1 | 7.7 | 1.0 | 2.0 | 32.2 |
| 8,192 | 16 | 21.1 | 8.2 | 8.2 | 0.3 | 2.0 | **39.8** |
| 8,192 | 32 | 21.1 | 8.2 | 10.2 | 1.0 | 2.0 | 42.6 |
| 8,192 | 64 | 21.1 | 8.2 | 12.3 | 4.1 | 2.0 | 47.7 |

## The 64-bit frontier

The same accounting against the held-out fit, every measured configuration, with
dominated points removed (a point is kept if it is smaller *and* better than
everything cheaper):

| bytes | `V` | `k` | mean bits | fit ≤64 | fit ≤128 | kB/pt to next |
|---:|---:|---:|---:|---:|---:|---:|
| 19,041 | 4096 | 8 | 51.904 | 77.2 % | 98.0 % | 2.0 |
| 20,257 | 4096 | 16 | 51.462 | 77.8 % | 98.1 % | 9.2 |
| 21,176 | 4096 | 24 | 51.333 | 77.9 % | 98.1 % | 4.4 |
| 22,049 | 4096 | 32 | 51.245 | 78.1 % | 98.1 % | 4.7 |
| 23,928 | 4096 | 48 | 50.889 | 78.5 % | 98.2 % | 5.5 |
| 26,145 | 4096 | 64 | 50.527 | 78.9 % | 98.3 % | **1.1** |
| 26,597 | 6144 | 4 | 50.384 | 79.3 % | 98.3 % | 2.3 |
| 28,181 | 6144 | 8 | 49.674 | 80.0 % | 98.4 % | 3.5 |
| 29,909 | 6144 | 16 | 49.317 | 80.5 % | 98.5 % | 5.8 |
| 32,213 | 6144 | 32 | 48.959 | 80.9 % | 98.5 % | 4.4 |
| 36,637 | 8192 | 6 | 48.282 | 81.9 % | 98.7 % | — (bits only) |
| 37,515 | 8192 | 8 | 48.240 | 81.9 % | 98.7 % | 4.3 |
| 38,793 | 8192 | 12 | 48.019 | 82.2 % | 98.7 % | 3.2 |
| 39,755 | 8192 | 16 | 47.727 | 82.5 % | 98.8 % | 7.6 |
| 41,273 | 8192 | 24 | 47.535 | 82.7 % | 98.8 % | 13.0 |
| 42,571 | 8192 | 32 | 47.481 | 82.8 % | 98.8 % | 24.8 |
| 45,049 | 8192 | 48 | 47.399 | 82.9 % | 98.8 % | 13.2 |
| 47,691 | 8192 | 64 | 47.285 | 83.1 % | 98.8 % | 31.6 |
| 54,009 | 8192 | 96 | 47.108 | 83.3 % | 98.9 % | 80.2 |
| 62,027 | 8192 | 128 | 46.964 | 83.4 % | 98.9 % | — |

Four things follow.

* **The cheap stretch is 20–39 kB at 1–6 kB per fit point**, and it is the `V`
  step out of 4096 plus the low-`k` 6144 and 8192 configurations.  Below 20 kB
  you are on 4096 with a coarse `k`; above 40 kB each further point costs 8, 13,
  25, 32 and finally 80 kB per point.
* **The best value on the whole curve is the corner at 26 kB**: 4096 / `k = 64`
  → 6144 / `k = 4` costs 452 B for +0.4 pt (1.1 kB/pt) because the bigger word
  list pays for itself twice — better tokens *and* a `k` that can be coarser.
* **`V = 6144` dominates the upper half of the 4096 sweep.**  Its *worst* point
  (`k = 4`, 26.6 kB, 79.3 %) matches the best 4096 point that costs less
  (31.9 kB at `k = 96`, 79.3 %) at 5.3 kB cheaper, and 6144 at `k = 16`
  (29.9 kB, 80.5 %) beats 4096's best overall (39.5 kB at `k = 128`, 79.6 %) by
  0.9 points for 9.6 kB less.
* **Fit ≤128 is saturated** (98.0–98.9 % everywhere), so every trade here is a
  64-bit trade.

### The frontier along `k` — the interior slices

`scripts/k_frontier.py` sweeps `k` at fixed `V` with the same accounting and the
same held-out set.  These are the same points as the frontier table above, kept
separate because the *local slope* is what prices a change made inside a model
(C26's shared clusters, C27's reserved cell, C28's quarters).

`V = 4096`, stride 10 (`n = 42,268`):

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 8 | 51.904 | 77.2 % | 98.0 % | 19,041 |
| 16 | 51.462 | 77.8 % | 98.1 % | 20,257 |
| 24 | 51.333 | 77.9 % | 98.1 % | 21,176 |
| 32 | 51.245 | 78.1 % | 98.1 % | 22,049 |
| 48 | 50.889 | 78.5 % | 98.2 % | 23,928 |
| 64 | 50.527 | 78.9 % | 98.3 % | 26,145 |
| 96 | 50.203 | 79.3 % | 98.3 % | 31,864 |
| 128 | 49.919 | 79.6 % | 98.4 % | 39,457 |

`V = 6144`:

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 4 | 50.384 | 79.3 % | 98.3 % | 26,597 |
| 8 | 49.674 | 80.0 % | 98.4 % | 28,181 |
| 16 | 49.317 | 80.5 % | 98.5 % | 29,909 |
| 32 | 48.959 | 80.9 % | 98.5 % | 32,213 |
| 64 | 48.626 | 81.3 % | 98.6 % | 36,821 |
| 96 | 48.322 | 81.6 % | 98.6 % | 42,840 |

`V = 8192`:

| `k` | mean bits | fit ≤64 | fit ≤128 | bytes |
|---:|---:|---:|---:|---:|
| 4 | 48.995 | 81.2 % | 98.6 % | 35,419 |
| 6 | 48.282 | 81.9 % | 98.7 % | 36,637 |
| 8 | 48.240 | 81.9 % | 98.7 % | 37,515 |
| 12 | 48.019 | 82.2 % | 98.7 % | 38,793 |
| 16 | 47.727 | 82.5 % | 98.8 % | 39,755 |
| 24 | 47.535 | 82.7 % | 98.8 % | 41,273 |
| 32 | 47.481 | 82.8 % | 98.8 % | 42,571 |
| 48 | 47.399 | 82.9 % | 98.8 % | 45,049 |
| 64 | 47.285 | 83.1 % | 98.8 % | 47,691 |
| 96 | 47.108 | 83.3 % | 98.9 % | 54,009 |
| 128 | 46.964 | 83.4 % | 98.9 % | 62,027 |

| step | Δbits | Δbytes | kB/bit | Δ fit ≤64 | kB per point |
|---|---:|---:|---:|---:|---:|
| 4096: 8→16 | −0.442 | +1,216 | 2.8 | +0.6 | 2.0 |
| 4096: 16→24 | −0.129 | +919 | 7.1 | +0.1 | 9.2 |
| 4096: 24→32 | −0.088 | +873 | 9.9 | +0.2 | 4.4 |
| 4096: 32→48 | −0.356 | +1,879 | 5.3 | +0.4 | 4.7 |
| 4096: 48→64 | −0.362 | +2,217 | 6.1 | +0.4 | 5.5 |
| 4096: 64→96 | −0.324 | +5,719 | 17.7 | +0.4 | 14.3 |
| 4096: 96→128 | −0.284 | +7,593 | 26.7 | +0.3 | 25.3 |
| 6144: 4→8 | −0.710 | +1,584 | 2.2 | +0.7 | 2.3 |
| 6144: 8→16 | −0.357 | +1,728 | 4.8 | +0.5 | 3.5 |
| 6144: 16→32 | −0.358 | +2,304 | 6.4 | +0.4 | 5.8 |
| 6144: 32→64 | −0.333 | +4,608 | 13.8 | +0.4 | 11.5 |
| 6144: 64→96 | −0.304 | +6,019 | 19.8 | +0.3 | 20.1 |
| 8192: 4→6 | −0.713 | +1,218 | 1.7 | +0.7 | 1.7 |
| 8192: 6→8 | −0.042 | +878 | 20.9 | +0.0 | — |
| 8192: 8→12 | −0.221 | +1,278 | 5.8 | +0.3 | 4.3 |
| 8192: 12→16 | −0.292 | +962 | 3.3 | +0.3 | 3.2 |
| 8192: 16→24 | −0.192 | +1,518 | 7.9 | +0.2 | 7.6 |
| 8192: 24→32 | −0.054 | +1,298 | 24.0 | +0.1 | 13.0 |
| 8192: 32→48 | −0.082 | +2,478 | 30.2 | +0.1 | 24.8 |
| 8192: 48→64 | −0.114 | +2,642 | 23.2 | +0.2 | 13.2 |
| 8192: 64→96 | −0.177 | +6,318 | 35.7 | +0.2 | 31.6 |
| 8192: 96→128 | −0.144 | +8,018 | 55.7 | +0.1 | 80.2 |

Five things follow.

* **`k = 16` is the floor, at both vocabularies.**  Fit *falls* below it —
  77.8 → 77.2 % at 4096 and 82.5 → 81.9 → 81.2 % from 16 down to 6 and 4 at
  8192 — so there is a genuine optimum rather than "the lowest affordable `k`".
  At 8192, `k = 6` is the same fit as `k = 8` for 878 B less, and `k = 4` is a
  full point worse.  The earlier open question ("`k = 8` may be better still")
  is answered: it is not.
* **Below `k = 16` the curve is as cheap as the `V` direction** (1.7–3.3 kB/pt
  at 8192) because a very coarse clustering is genuinely broken, and the repair
  is worth paying for.  Above 16 it is a plateau and then a dead zone: 16 → 64
  buys 0.6 points for 7.9 kB (13 kB/pt), 64 → 96 buys 0.2 for 7.3 kB
  (32 kB/pt), and 96 → 128 buys 0.1 for 8.0 kB (80 kB/pt).
* **The apparent cheap segment at 32→48 was noise.**  At `n = 4,227` it looked
  like 2.8 kB/pt, inviting a story about a cheap stretch; at `n = 42,268` it is
  4.7, in line with its neighbours.  The 10× held-out set was run for exactly
  this reason: with 4,227 identifiers, adjacent fit differences of 0.2–0.7 pt
  are ±0.9 pt, so segment *slopes* were never reliable to better than a factor
  of two.  Absolute fit rates also fell 0.2–0.9 pt at every `k`.
* **The knee is the `k²` block taking over from the memberships, and it moves
  with `V`.**  At 4096 the block is 1.0 kB at `k = 32`, 4.1 at 64 and 16.4 at
  128, so the curve is still paying about 5 kB/pt up to 64 and 14.3 beyond it.
  At 8192 the memberships are already 8.2 kB at `k = 16` and every step above it
  costs 7.6–13 kB/pt.  The block table, not the memberships, dominates the top
  of the curve.
* **The envelope is a ramp, not a staircase — and the earlier claim was an
  artefact.**  Reading only the two `k`-sweeps, the frontier looked
  discontinuous: 4096's best point (31.9 kB, 79.3 %) against 8192's worst
  (35.4 kB, 81.2 %) was a 1.9-point jump for 3.5 kB.  That comparison put the
  *top* of one `k`-curve (where `k` is worth nothing) against the *bottom* of
  the next.  With `V = 6144` measured in between, the jump disappears: the
  envelope passes 79.3 % at 26.6 kB and 81.2 % at 32.2 kB on the way to 81.9 %
  at 36.6 kB.

**This is a slice, not the frontier.**  The sweep answers what the *next*
kilobyte buys **at fixed `V`**, which is the right comparison for a candidate
that adds bytes to an existing model but the wrong one for "should this model be
bigger".  Used that way the two pictures agree: the k-curve is interior to the
`V`-envelope, and its local slope (4.7 kB/pt in the middle of the 4096 sweep) is
the opportunity cost of spending a kilobyte *inside* a model rather than
replacing it.

### `V` against `k` at matched size

Once the rule table is charged, the earlier "`V` is 2–6× cheaper than `k`" claim
softens but survives:

* the `V` step at matched `k` is **3.6 kB/pt** (4096→6144, `k = 16`),
  **4.9** (6144→8192, `k = 16`) and **5.5** (6144→8192, `k = 32`);
* the `k` step above 16 at 8192 is **7.6 / 13.0 / 24.8 / 13.2** kB/pt
  (16→24→32→48→64), then 31.6 to 96 and 80.2 to 128.

So a bigger word list is still the cheaper way to buy a point, but by 1.5–4×
against the 8–25 kB/pt the `k` direction costs above 16, not by the 2–6× claimed
when the rule table was omitted.  The mechanism is mechanical: a bigger word list shortens identifiers
(held-out mean length falls 4.70 → 4.05 tokens from `V = 4096` to `8192`) and
the 64-bit budget is dominated by the *long* identifiers, so `V` attacks the part
of the distribution the threshold measures; a finer `k` only shaves the
conditional entropy of tokens already inside an identifier.

## The two model shapes

The tables above price the **arithmetic** model: stored probabilities, evaluated
as `P(b | a)`.  The standard ships a **Huffman** code instead (`ENCODING.md` §3:
publish the code, not the probabilities), and that is a different object:

| object | arithmetic | Huffman |
|---|---|---|
| word list rules | rule table | rule table |
| the distributions | unigram + memberships + block | code lengths (`CF`/`CQF`) |
| program code | 2 kB | 2 kB |

A code length is one byte per symbol, so the codebook is a re-encoding of the
same information, not an addition to it: it replaces the unigram, both cluster
assignments and `D`.  **The two must not be added.**  An earlier draft of this
note did exactly that — it took a "code-side" figure that already contained
`2(V−k) + V log V` bits of Huffman *bottom-stage* codebook and charged the rule
table on top of it, then called the sum the model.  At `V = 8192, k = 16` that
gave 53.5 kB where the arithmetic model is 39.8 kB; the difference, 13.7 kB, is
one bottom-stage codebook plus a double-charged 2 kB of code.

The factorised codebook is priced in [`ENCODING.md`](ENCODING.md) §5 (`CF` and
`CQF`: 8.0 kB at 4096/32, 19.4 kB at 8192/64).  Its bottom-stage `2(V−k)` is
not a fudge for "two bytes": it is the **bracket skeleton** of the bottom trees
— every internal node is one `(` and one `)`, so two bits each, and a tree with
`L` leaves has `L−1` internal nodes — and the `V log₂V` beside it is the
depth-first **leaf list**.  The skeleton alone gives every code length; the list
alone gives the assignment; together they reconstruct the tree.

§3's one byte per code length is a **different store of the same information**,
not a bigger price for the same object, and at the grid it is the cheaper one:
the bracket form pays `log₂V` bits per leaf where a length table pays 8 bits
plus `log₂k` for the map.  The crossover is `V/k = 64`; above it the table wins
by 0.4 kB at 4096/32, 3 kB at 8192/16 and 1 kB at 8192/64 with two maps, and by
2.9 / 7.0 kB with C26's shared assignment (one map serves both sides).  What
both figures omit is the **word→left-cluster** map (another `V log₂k` bits)
unless the assignment is shared.

The upshot is that the two shapes cost the **same** bytes at the operating
point, not different ones: one byte per symbol either way (a length in one, a
quantised probability in the other), plus the same maps and the same block.
The codebook only looks smaller than the tables because §5 prices the
*compressed* bracket form, and only looks bigger once its left map is charged.
So the Huffman choice is not a size argument at all — it is worth ~1–2 bits per
identifier for the free terminator (`CODING_OVERHEAD.md`), at equal size.
Neither omission moves C28's increments (`q = 2` costs +1.1 kB at `k = 32`,
`q = 4` 3.2× that), which is what that verdict rests on.

On bits, the Huffman code with the adopted zero-weight stop measured **−1.0
bit/identifier** and **+1.5 pt of fit** over the arithmetic reference at both
checked cells (`CODING_OVERHEAD.md`: 8192/16 goes 47.727 → 45.027 bits, 82.5 →
85.3 %).

## What it shows

* **The rule table is more than half the model** — 21.1 of 39.8 kB at the
  operating point, well ahead of the unigram and the memberships (8.2 kB
  each).  Zipf-coding already takes 20 % off
  the fixed-width index stream; the empirical optimum is only a further 5 % and
  would have to be stored.  The real lever is a smaller vocabulary, which is the
  `V`-against-`k` trade above.
* **The frontier is 19 kB / 77 %, 30 kB / 81 %, 40 kB / 83 %** for 64-bit
  coverage — comfortably inside the "50 kB-ish is acceptable if it rescues the
  64-bit set" band, and 2× the 20 kB goal.
* **Size is not what costs the 64-bit set — clustering is.**  The full-table
  ceilings are 85–94 %; the shipped models fit 77–83 %.  The gap is the
  membership and block structure, not the word list.
* **The next two objects are the unigram and the memberships** (8.2 kB each at
  the operating point).  `2V · ⌈log₂k / 8⌉` doubles by `k = 64`, so it is also
  the term that makes a fine `k` expensive; it is what C26's shared assignment
  buys down.  The unigram is one byte per word by house convention and has an
  entropy-coded version about 30 % smaller that nothing charges for yet.

## Reproducing

```sh
# model size, with the rule table priced from the directory
for d in work/tw4096ns work/tw6144ns work/tw8192ns; do
  python3 scripts/model_budget.py --dirs $d --ks 16,32,64 --index-code zipf --code 2000
done

# the k-sweeps (bytes in the full inventory by default; --code-side for the
# Huffman codebook accounting used in SHARED_CLUSTERS.md)
python3 scripts/k_frontier.py --dir work/tw4096ns --ks 8,16,24,32,48,64,96,128 --stride 10
python3 scripts/k_frontier.py --dir work/tw6144ns --ks 4,8,16,32,64,96 --stride 10
python3 scripts/k_frontier.py --dir work/tw8192ns --ks 4,6,8,12,16,24,32,48,64,96,128 --stride 10

# creation order vs unigram order
python3 scripts/wordlist_order.py --dirs work/tw4096ns,work/tw6144ns,work/tw8192ns
```

## Pre-grid record

Before the 10-ecosystem corpus the frontier was measured on the older
vocabularies (`V = 2 104 / 4 478 / 11 758`) at stride 40 (`n = 5 739`) and priced
with the codebook accounting discussed above.  Those numbers are **not**
comparable with the tables in this note — different corpus, vocabulary and
accounting — and are kept only as the record of what was believed at the time:

| size | `V` | `k` | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 14.3 kB | 2,104 | 52 | 56.72 | 70.4 % | 97.0 % |
| 22.9 kB | 2,104 | 105 | 55.48 | 71.8 % | 97.3 % |
| 26.1 kB | 4,478 | 52 | 51.75 | 76.3 % | 98.1 % |
| 35.3 kB | 4,478 | 105 | 51.10 | 77.0 % | 98.2 % |
| 64.2 kB | 11,758 | 52 | 47.21 | 82.5 % | 98.9 % |
| 75.2 kB | 11,758 | 105 | 46.90 | 82.9 % | 98.9 % |

Full tables (stride 40): `V = 2 104` 4.2 MB / 85.1 %, `V = 4 478` 19.1 MB /
89.4 %, `V = 11 758` 131.8 MB / 93.5 %.  The old 64.2 kB point and the current
47.7 kB point (`8192, k = 64`) differ by 0.6 pt of fit, but they are different
corpora: the size difference is mostly the smaller vocabulary and its cheaper
memberships, not a better model.

## Rejected / not done

* Reordering the word list by unigram — not possible without changing the
  tokenisation; the list is in creation order (measured above).
* A unigram-derived code for the child indices — worse than uniform.
* Storing the empirical child-index distribution — 5 % of the index stream,
  paid for by storing the distribution.
* Entropy-coding the *index stream* beyond the two-parameter Zipf prior.
* A cluster → members index: derivable at load time, not charged.
* Charging a Huffman codebook *and* the arithmetic tables for one model — they
  are alternatives (see "The two model shapes").
