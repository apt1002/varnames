# Choosing the merge: dictionary-building rules

`docs/TREE_WORDS.md` specifies the dictionary: repeatedly merge the **most
common pair** of words.  It notes two things worth measuring:

* the "most frequent pair" rule sees only bigrams, so it is a *proxy* for the
  exact best move, "merge the pair that shrinks `CS` the most";
* the flat run word `(u^k)` and the ordinary bigram `(uv)` both compete for the
  same budget when a run abuts a different word, e.g. `uuuuv` as `(u⁴)v` versus
  `uuu(uv)`.

This note reports the experiments.  Reproduce with

    python3 scripts/dict_experiments.py --quick
    python3 scripts/dict_experiments.py --real work/camel/merged_training.txt

Everything is measured as **corpus size** `CS = S1 − S2` in bits (base 2),
`S1 = Σ_u L(N(u))`, `S2 = Σ_{u,v} L(N(u,v))`, `L(z) = z log₂ z`, computed on the
cyclic tokenisation of the corpus.  Smaller is better.  Where a held-out number
is quoted, the dictionary is built on a train half and `CS` is measured on the
disjoint test half (both using their own MLE counts — i.e. how well the
tokenisation the dictionary induces fits the test data).  The synthetic corpora
are described in `scripts/dict_experiments.py`.

## Greedy by frequency vs greedy by `Δ`

The exact greedy move minimises `Δ = CS' − CS` over candidate pairs;
`docs/TREE_WORDS.md` shows `Δ` depends on the embedding (`A`, `B`, `Q`) and not
on `N(u,v)` alone, so the two rules can differ.  We build the dictionary both
ways at the same `NUM_PAIRS`, considering the top-8 candidate pairs each step
for the `Δ` rule.

**Synthetic** (run-length corpora, held-out, `NUM_PAIRS = 10`):

| runmean | pbound | freq | delta | Δ-rule gain |
|---:|---:|---:|---:|---:|
| 1.5 | 0.25 | 22 748 | 21 710 | **+4.6 %** |
| 3.0 | 0.6 | 19 567 | 18 427 | **+5.8 %** |
| 3.0 | 0.9 | 17 328 | 16 309 | **+5.9 %** |

**Real** (`merged_training.txt`, stride-500 sample, 2 000 train / 2 000 test):

| NUM_PAIRS | freq | delta | better |
|---:|---:|---:|---|
| 8  | 143 779 | 143 293 | delta (**+0.34 %**) |
| 16 | 140 443 | 140 123 | delta (**+0.23 %**) |
| 24 | 137 434 | 137 625 | freq (**−0.14 %**) |

So the `Δ` rule's edge is large on structured synthetic data but **small and
non-monotone on real identifiers** — it fades to a fraction of a percent and
actually reverses by `NUM_PAIRS = 24`.  This is exactly the documented drawback:
`Δ` is estimated on the training counts, so it happily spends words on rare
short-range patterns that do not generalise, whereas the most-frequent-pair rule
is a robust, cheap proxy.  For real corpora, keep the frequency rule.

## The `(u^k)` run word vs the `(uv)` boundary word

When a run `u^k` is followed by `v`, the flat run word `(u^k)` and the boundary
word `(uv)` compete for the same slot.  Two regimes, both measured held-out.

**(a) The full run-aware rule.**  `docs/TREE_WORDS.md` ("Relaxing the
three-consecutive-repeats assumption") replaces the doubled-word merge `(u,u)`
by *one flat word per observed run length*.  Against plain BPE
(`NUM_PAIRS = 12`, run lengths exponential, so many lengths present):

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

## The heuristic

For a single slot, **prefer the flat run word `(u^k)` over the boundary word
`(uv)` iff the tokens it collapses outweigh the boundaries it would capture**,

    (k − 1) · (#runs of length k)   >   N(u,v) ,

i.e. compare the `u u` mass the run word removes against the `u v` mass `(uv)`
would remove.  This rule is correct on every case above: **run wins** when a run
length dominates (fixed `R`, so `#runs` is huge), **`uv` wins** when the run
lengths are spread (no single `k` carries enough mass).

The consequence for the full rule is the useful one: because a single run word
covers only its own length, when run lengths are **spread out** no one `(u^k)`
is worth a slot alone — the boundary `(uv)` should take it — but the *full*
run-aware rule, which spends **one word per length**, still beats plain BPE.  So:

* run lengths concentrated → the run word is a bargain, take it early;
* run lengths spread → let the boundary take the first slot, and pick up the
  runs length-by-length as the budget allows.

The exact tie-break is, as ever, `Δ` — but on real data the frequency
proxy is good enough, and the rule above needs only the two counts `N(u,v)` and
the run-length histogram.

**The predictor is just a pair count.**  A run `u^k` contains exactly `k − 1`
adjacent `uu` pairs, so `(k − 1)·#runs(k)` counts the `uu` pairs *inside runs of
length exactly k* (and `Σ_k (k − 1)·#runs(k) = N(u,u)`).  The rule above is
therefore nothing more than the **most-common-pair rule** applied to the two
candidates: count the `uu` joins against the `uv` joins and take the larger.
The only subtlety is *which* `uu` count a candidate owns — a **single** run word
claims just one length's slice, so it can lose to `(uv)` even when
`N(u,u) > N(u,v)`; the **full** run-aware rule claims every length at once, so
it *is* exactly `N(u,u) > N(u,v)`.  The genuinely new part is not the
*selection* (still most-common-pair) but the *action*: when the top pair is a
doubled word, collapse the run instead of merging two copies — which is why
run-aware beats plain BPE even in grid points where `N(u,u) < N(u,v)`.

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
  `docs/RUN_LENGTHS.md`: runs are almost all length 2 (99 % of runs, 98 % of the
  `uu` mass), so on real identifiers the crossover above is usually decided by
  `N(u,u)` vs `N(u,v)` alone — the length-`k` cases above are the synthetic
  stress tests.

## Removing run words altogether (`--self-merge forbid`)

Everything above assumes the run rule is *in use*.  The obvious question is
whether it is needed at all: forbid **every** merge of a pair with itself, so a
doubled character (or doubled word) is never collapsed — not even to `(uu)`, let
alone a flat `(u^k)` — and a double can only enter the vocabulary inside a pair
word that also contains a neighbour (`sse`, `ess`, `tte`, …).  The dictionary is
then plain most-frequent-pair merge, with no k-ary nodes, no run-length table and
no run path in the tokeniser.

Both rules were built on the same stride-20 training sample (`work/tw*` vs
`work/tw*ns`), counted on the full training corpus and scored on the full
held-out validation set (229,534 identifiers, `kappa = 1000`):

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
* **Why it is cheap.**  Runs are 2.13 % of character adjacencies and 99 % of
  them are length 2 (`docs/RUN_LENGTHS.md`), so the run rules mostly buy `ss`,
  `tt`, `ee`, `__`, `00` — words that a pair word containing a neighbour
  (`sse`, `ess`, `tte`, `__i`) delivers anyway.  What the run rules mostly add
  on real identifiers is a handful of corpus-specific long runs (`f*15`,
  `0*19`), which generalise badly.
* **The simplification is the point.**  Dropping the rule removes the k-ary
  node type, the run-length table and its per-length words, the run replay in
  the tokeniser, and the run branch of the word-list encoder.  Nothing in the
  model's statistics or its storage depended on it.

So the run-aware rule is retired: the dictionary is plain pair-merge with
self-merges forbidden.  The held-out numbers in
[`WORD_COMPRESSIBILITY.md`](WORD_COMPRESSIBILITY.md) were measured on the
run-aware rule and are unchanged by the switch (same `V`, same counts to within
3 identifiers), so they stand.

*Caveat: measured on one corpus, one `kappa`, one stride; the 576 row is the
only place the two rules differ appreciably, and the corpus rebuild recorded in
`PLAN.md` will re-measure all of it.*
