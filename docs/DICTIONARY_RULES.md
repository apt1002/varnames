# Choosing the merge: dictionary-building rules

Status: **the adopted rule, then the alternatives that were measured and
rejected.**  The dictionary is plain most-frequent-pair merge with **merges of a
symbol with itself forbidden**; the sections after the first record what was
tried against that rule and why it stayed.

## The adopted rule

Start from the character alphabet plus `\n` and repeatedly merge the most common
adjacent pair of words (`docs/TREE_WORDS.md` §2).  Two things the rule does
**not** do, decided by the experiments below:

* **It never merges a symbol with itself.**  A word `(uu)` is never created, and
  there is no flat run word `(u^k)`.  So every dictionary entry is a rule
  `P a b` with `a ≠ b`, and a doubled letter can only enter the vocabulary
  inside a word that also contains a neighbour (`sse`, `ess`, `tte`, `__i`).
* **It is greedy by frequency, not by the exact score.**  The exact greedy move
  would minimise `Δ = CS' − CS` over candidate pairs; the frequency rule is a
  cheap proxy for it.

Each departure gives up something in principle, so each was measured against
its obvious alternative: the exact `Δ` rule in "Adopted: greedy by frequency",
and run words in "Rejected: the run word".  Neither alternative is worth its
price.

Everything is measured as **corpus size** `CS = S1 − S2` in bits (base 2),
`S1 = Σ_u L(N(u))`, `S2 = Σ_{u,v} L(N(u,v))`, `L(z) = z log₂ z`, computed on the
cyclic tokenisation of the corpus; smaller is better.  `CS` and the identity are
defined and proved in [`TREE_WORDS.md`](TREE_WORDS.md) §4 (identity in §10).
Where a held-out number is quoted, the dictionary is built on a train half and
`CS` is measured on the disjoint test half (both using their own MLE counts —
i.e. how well the tokenisation the dictionary induces fits the test data).  The
synthetic corpora are described in `scripts/dict_experiments.py`.  Reproduce
with

    python3 scripts/dict_experiments.py --quick
    python3 scripts/dict_experiments.py --real work/camel/merged_training.txt

## Adopted: greedy by frequency

The exact greedy move minimises `Δ = CS' − CS` over candidate pairs;
[`TREE_WORDS.md`](TREE_WORDS.md) §5 shows `Δ` depends on the embedding (`A`,
`B`, `Q`) and not on `N(u,v)` alone, so the two rules can differ.  We build the
dictionary both ways at the same `NUM_PAIRS`, considering the top-8 candidate
pairs each step for the `Δ` rule.

**Synthetic** (run-length corpora, held-out, `NUM_PAIRS = 10`):

| runmean | pbound | freq | delta | Δ-rule gain |
|---:|---:|---:|---:|---:|
| 1.5 | 0.25 | 22 748 | 21 710 | **+4.6 %** |
| 3.0 | 0.6 | 19 567 | 18 427 | **+5.8 %** |
| 3.0 | 0.9 | 17 328 | 16 309 | **+5.9 %** |

**Real** (`merged_training.txt`, stride-500 sample, 3 804 train / 3 805 test,
63 symbols):

| NUM_PAIRS | freq | delta | better |
|---:|---:|---:|---|
| 8  | 253 999 | 253 194 | delta (**+0.32 %**) |
| 16 | 248 596 | 248 242 | delta (**+0.14 %**) |
| 24 | 244 369 | 243 891 | delta (**+0.20 %**) |

So the `Δ` rule's edge is large on structured synthetic data but **small and
unstable on real identifiers** — a third of a percent at `NUM_PAIRS = 8`, a
seventh at 16, for eight times the work per step (the `Δ` rule scores the top
eight candidate pairs).  The sign is not even stable across splits: on the
smaller 2 000 / 2 000 split of the same corpus it reads `+0.21 %`, `−0.10 %`,
`+0.02 %`.  (The pre-expansion table, on the smaller corpus, showed a reversal
at `NUM_PAIRS = 24`; that does not reproduce.)  This is exactly the documented
drawback: `Δ` is estimated on the training counts, so it happily spends words on
rare short-range patterns that do not generalise, whereas the most-frequent-pair
rule is a robust, cheap proxy.  For real corpora, keep the frequency rule.

**The same instinct was followed further, and it failed harder.**
[`PRUNE_WORDS.md`](PRUNE_WORDS.md) overshoots the word list by 1.5× and then
deletes the least valuable words using the *exact* removal cost — a more
thorough way to spend the last few words than either greedy rule.  It wins
**0.86 bits** on the raw bigram score at `NUM_PAIRS = 512` (and 0.145 at 2040),
but the win does not survive co-clustering, the representation we actually ship
(it is 0.6–1.8 bits *worse* there).  So two independent attempts to beat the
frequency proxy — one per step, one by post-hoc removal — agree: the merge rule
is not where the remaining bits are, and the cheap robust rule is the one to
keep.

## Rejected: the run word

An earlier version of the dictionary allowed run words.  The first step was the
ordinary merge `(uu)`, which the adopted rule forbids; on top of that, a run of
`k` copies could be collapsed to one flat, `k`-ary word `(u^k)`, one word per
observed length.  It was a bad idea, and it is gone — the run path has been
deleted from `scripts/tree_words.py` rather than left as a dead branch.

**Why it lost.**  Runs are 2.17 % of character adjacencies and 99.0 % of them
are length 2 ([`RUN_LENGTHS.md`](RUN_LENGTHS.md)), so the run rules mostly buy
`ss`, `tt`, `ee`, `__`, `00` — words that a pair word containing a neighbour
(`sse`, `ess`, `tte`, `__i`) delivers anyway.  What the rules mostly add on real
identifiers is a handful of corpus-specific long runs (`f*15`, `0*19`), which
generalise badly.  And the machinery is real: a `k`-ary node type, a
run-length table with one word per length, the run replay in the tokeniser and
the run branch of the word-list encoder, for **0.2–0.4 % of the word list**.

The measurement that settled it: both rules on the same stride-20 training
sample, counted on the full training corpus and scored on the full held-out
validation set (229,534 identifiers, `kappa = 1000`):

> **Historical measurement.** These are the pre-expansion numbers (the
> 2.37 M-identifier corpus, held-out 229,534). The run path has since been
> deleted from `scripts/tree_words.py`, so the comparison cannot be re-run at the
> canonical grid; the tables stand as the record of why the rule was dropped.
> The run statistics that justify it are re-measured in
> [`RUN_LENGTHS.md`](RUN_LENGTHS.md).

| vocab `V` | run rules | rules | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 576 | 7 → 0 | 499 → 512 | 54.05 → **53.83** | 169,980 → **170,672** | 224,782 → 224,816 |
| 2,104 | 11 → 0 | 2,023 → 2,040 | 45.79 → 45.79 | 195,017 → 195,014 | 227,611 → 227,606 |
| 4,478 | 23 → 0 | 4,389 → 4,414 | 42.48 → 42.48 | 205,531 → 205,486 | 228,506 → 228,512 |

Cost of storing the list, Zipf-coded (`docs/MODEL_BUDGET.md`): 1,019 → 1,036 B,
4,645 → 4,663 B, 10,815 → 10,850 B — the naive list needs a few more rules for
the same `V` and each rule is marginally dearer, so the run machinery saves
**0.2–0.4 % of the word list** and nothing else.

* **At the sizes we use, the run rule is free to drop.**  At `V = 2,104` and
  `4,478` the mean is identical to two decimals; the 64-bit fit moves by 3
  identifiers out of 229,534 at `V = 2,104` and by 45 (0.02 pt) at `V = 4,478`,
  and the 128-bit fit by 5 and 6.
* **At a tiny vocabulary it is worth dropping.**  At `V = 576` the 13 words the
  7 run rules buy (13 lengths of `r f m _ s 1 0`-doubles, including `f*15` and
  `0*19`) are worth less than the 13 ordinary pairs the no-run list buys with the
  same budget: 0.22 bits cheaper and 692 more identifiers inside 64 bits.

### What the case for run words looked like

On run-heavy *synthetic* corpora the run rule does win, and this is why it was
pursued for so long.  When a run `u^k` is followed by `v`, the flat run word
`(u^k)` and the boundary word `(uv)` compete for the same slot.  Two regimes,
both measured held-out.

**(a) The full run-aware rule**, against plain BPE (`NUM_PAIRS = 12`, run lengths
exponential, so many lengths present):

| runmean | pbound | run mass N(u,u) | N(u,v) | freq | runs | winner |
|---:|---:|---:|---:|---:|---:|---|
| 1.5 | 0.2 | 2 930 | 554 | 22 796 | 21 893 | runs |
| 1.5 | 0.6 | 2 902 | 1 703 | 22 368 | 21 795 | runs |
| 1.5 | 0.9 | 2 893 | 2 574 | 20 010 | 19 544 | runs |
| 3.0 | 0.2 | 5 014 | 425 | 19 905 | 18 911 | runs |
| 3.0 | 0.6 | 5 078 | 1 219 | 19 394 | 18 523 | runs |
| 3.0 | 0.9 | 5 254 | 1 822 | 17 476 | 16 712 | runs |

The run-aware rule wins **whenever there is run mass**, even when `N(u,v) >
N(u,u)` (rows 3, 6): it changes only the *doubled-pair* steps, and doing them as
flat runs is strictly better than the nested `((uu)u)…` that plain BPE builds.
That real effect is what the no-run rule gives up; on identifiers, with 99 % of
runs at length 2, it turns out to be worth almost nothing.

**(b) A *single* word.**  Spend one slot only — the modal run word `(u^k*)` or
the boundary `(uv)`:

| regime | run length | save `(k*−1)·#runs(k*)` | `N(u,v)` | run CS | uv CS | winner |
|---|---|---:|---:|---:|---:|---|
| fixed `R=3` | 3 | 4 980 | 240 | 9 353 | 14 280 | run |
| fixed `R=3` | 3 | 4 988 | 1 154 | 10 475 | 14 965 | run |
| fixed `R=5` | 5 | 6 820 | 159 | 7 019 | 11 443 | run |
| fixed `R=5` | 5 | 6 756 | 1 421 | 7 346 | 11 538 | run |
| spread, runmean 1.5 | 2 | 767 | 799 | 21 922 | 21 636 | uv |
| spread, runmean 1.5 | 2 | 798 | 2 006 | 20 777 | 20 526 | uv |
| spread, runmean 3.0 | 2 | 513 | 583 | 18 811 | 18 426 | uv |
| spread, runmean 3.0 | 2 | 515 | 1 405 | 17 905 | 17 520 | uv |

(Both subtables are the `--quick` grid; the predictor below is right on all of
them, `10/10` including the rows omitted here.)

### The selection was never the novel part

For a single slot, the run word beats the boundary word iff the tokens it
collapses outweigh the boundaries it would capture,

    (k − 1) · (#runs of length k)   >   N(u,v) ,

i.e. compare the `u u` mass the run word removes against the `u v` mass `(uv)`
would remove.  This rule is correct on every case above: **run wins** when a run
length dominates (fixed `R`, so `#runs` is huge), **`uv` wins** when the run
lengths are spread (no single `k` carries enough mass).

But a run `u^k` contains exactly `k − 1` adjacent `uu` pairs, so
`(k − 1)·#runs(k)` counts the `uu` pairs *inside runs of length exactly k* (and
`Σ_k (k − 1)·#runs(k) = N(u,u)`).  The rule above is therefore nothing more than
the **most-common-pair rule** applied to the two candidates: count the `uu` joins
against the `uv` joins and take the larger.  The only subtlety is *which* `uu`
count a candidate owns — a **single** run word claims just one length's slice, so
it can lose to `(uv)` even when `N(u,u) > N(u,v)`; the **full** run-aware rule
claims every length at once, so it *is* exactly `N(u,u) > N(u,v)`.

So the genuine novelty was never the *selection* — it was the *action*: when the
top pair is a doubled word, collapse the run instead of merging two copies.  That
action is what bought the synthetic wins above, and it is also what cost the
`k`-ary node, the run-length table and the replay path.  On identifiers, the
action buys the handful of `ss`/`tt`/`__` runs that a neighbour pair delivers
anyway — hence the verdict.

### Robustness of the conclusion

Before dropping the machinery, the same comparison was repeated on the two
other axes that could have hidden the run rule's value.

**At the `kappa` the model-fit sweep actually prefers** (`kappa = 300` instead of
the `1000` used above), the same story, with the smallest vocabulary again
favouring the no-run list:

| vocab `V` | mean bits | fit ≤64 | fit ≤128 |
|---:|---|---:|---:|
| 576 | 53.99 → **53.76** | 170,137 → **170,856** | 224,796 → **224,850** |
| 2,104 | 45.59 → 45.59 | 195,621 → 195,615 | 227,684 → 227,676 |
| 4,478 | 42.02 → 42.03 | 206,737 → 206,692 | 228,603 → 228,590 |

**Under the co-clustered `assoc` model** (`scripts/model_fit_rates.py`, stride
40, `k = 52` and `k = 105`), the clustering residual swamps the difference and
the no-run dictionary is if anything the better one:

| vocab `V` = 2,104 | `k` | mean bits | fit ≤64 |
|---|---:|---|---:|
| run-aware | 52 | 56.715 | 70.4 % |
| no-run | 52 | 56.732 | 70.3 % |
| run-aware | 105 | 55.477 | 71.8 % |
| no-run | 105 | **55.441** | **72.0 %** |

Differences of 0.02–0.04 bits and ≤0.2 pt, in both directions — noise, against
a saving of two model-budget items (the run-length table and the k-ary node
type).

*Caveat: measured on the pre-expansion corpus at one stride; the 576 row is the
only place the two rules differ appreciably.  The canonical grid runs the no-run
rule only, so this table is the record rather than a live comparison.*

## Caveats

* In-sample `CS` is gameable, so every comparison here is held-out; the
  synthetic corpora are tiny (a few hundred strings, length 20) and the numbers
  are illustrative, not calibrated to real identifier statistics.
* The `Δ`-greedy rule is restricted to the top-8 frequent pairs per step
  (exhaustive `Δ` over the whole vocabulary is far too slow); a wider candidate
  set would only help it.
* `scripts/dict_experiments.py` uses its own simple, recount-based builder and
  tokeniser — it is a clean-room check of the *rules*, independent of the fast
  production path in `scripts/tree_words.py`.
* The **run-length histogram of the real corpus** is measured in
  [`RUN_LENGTHS.md`](RUN_LENGTHS.md): runs are almost all length 2 (99 % of runs,
  98 % of the `uu` mass), so the crossover above is usually decided by `N(u,u)`
  vs `N(u,v)` alone — the length-`k` cases above are the synthetic stress tests.
