# Overshoot the word list, then prune by removal cost

Status: **succeeded.**  Building the run-aware dictionary 1.5× too large and
then deleting the least valuable words down to size gives a word list that codes
held-out identifiers **0.86 bits better** than the plain greedy build of the
same size (63.77 → 62.91 bits at `NUM_PAIRS = 512`), recovering most of the
1.52-bit advantage of the 1.5× larger list (62.25 bits).  At `NUM_PAIRS = 2040`
the win is smaller but still positive (**+0.145 bits**, 59.22 → 59.08; the
overshoot 3060 list is 58.22).

## Idea

The greedy most-frequent-pair build (of [`TREE_WORDS.md`](TREE_WORDS.md) §2)
commits to its first `NUM_PAIRS` words.  Instead:

1. build `1.5 × NUM_PAIRS` words (the **overshoot**);
2. repeatedly delete the **removable** word — one that is not a child of any
   kept word — whose removal costs the least, until the list is back to
   `NUM_PAIRS`.

If the overshoot explored words the greedy prefix would have missed, the pruned
list keeps the better `NUM_PAIRS` and approaches the compression of the larger
list at the smaller model size.

## Removal cost (`Delta_CS`)

Deleting a pair word `w = (a, b)` is the exact inverse of the merge that created
it: every token `w` is split back into `a, b`.  The change in the corpus score
`CS = S1 − S2` (`L(z) = z log z`) is computed from the *current* bigram counts
alone — no trigram scan:

    U'[a] += N(w),  U'[b] += N(w),  U'[w] = 0,
    (x, w) -> (x, a) and (w, y) -> (b, y) for each occurrence,
    (w, w) removed once,  (a, b) created N(w) times,
    and each ``w w`` adjacency contributes a single (b, a).

`split_cost` implements it and `apply_split` mutates the counts; both are
verified against a brute-force recount (`prune_words.py selfcheck`, 0
mismatches).  Only pair words are pruned; run words (few, valuable) are kept.

The greedi est deletion is done with a lazily-updated min-heap: after each
split the costs change, so a popped word whose cost has moved is re-queued with
its fresh cost.  When a word is deleted its operands may stop being children of
any kept word and become removable; those are pushed then.

## Result (`NUM_PAIRS = 512`, `kappa = 300`)

Built on a stride-20 sample of `work/camel/merged_training.txt`; held-out mean
bits on a stride-20 sample of `work/camel/merged_validation.txt`.

| word list | words | `V` | mean bits |
|---|---:|---:|---:|
| greedy to 512 | 512 | 576 | 63.772 |
| **overshoot 768, prune to 512** | 512 | 576 | **62.908** |
| greedy to 768 (the overshoot) | 768 | 832 | 62.249 |

Pruning beats the plain greedy build by **0.864 bits** and captures 0.66 of the
1.52-bit gap to the larger list — i.e. it gets most of the rate of a 768-word
model from a 512-word model.

## Result (`NUM_PAIRS = 2040`, `kappa = 300`)

Same build/validation harness, target 2040, overshoot 1.5× (3060 words).

| word list | words | `V` | mean bits |
|---|---:|---:|---:|
| greedy to 2040 | 2040 | 2104 | 59.221 |
| **overshoot 3060, prune to 2040** | 2040 | 2104 | **59.075** |
| greedy to 3060 (the overshoot) | 3060 | 3124 | 58.219 |

The pruned list still wins, but by only **0.145 bits** — it captures 0.14 of the
1.00-bit gap to the 3060-word list, far less than the 0.66 captured at 512
words.  So the overshoot pays off much less at the larger size: at 2040 words
the greedy prefix already contains nearly all the valuable words, and the
overshoot tail is mostly reached-and-discarded.  This is why the adopted 2040
word list (plan C15) is only a marginal improvement over the greedy build, and
motivates the overshoot-size sweep (plan C14).  Per-32 rank counts of the kept
new words and the 80-of-256 / 232-of-1020 greedy-deletion figures appear in
`work/prune_512_removed.txt` / `work/prune_2040_removed.txt`.

### Caveat: the gain does *not* carry to the clustered model

The pruned list is better only for the **un-clustered** bigram model.  Padding
it through the co-clustering pipeline of [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)
(the representation that is actually competitive with the Hellinger
factorisation at matched storage) it is consistently *worse*:

| `k` | store | greedy `work/tw2040` assoc / 1-sided | pruned `work/tw2040p` assoc / 1-sided |
|---:|---:|---:|---:|
| 26 | 4 884 | 57.33 / 54.90 | **59.09 / 56.21** |
| 52 | 6 912 | 56.58 / 53.69 | **57.91 / 54.67** |
| 105 | 15 233 | 55.35 / 52.16 | **56.31 / 52.96** |

(held-out full table: greedy 45.77, pruned **45.42** — the pruned list wins
un-clustered, loses ~1-2 bits clustered; the sqrtcnt-match columns are worse by
the same margin, and the result is stable to the k-means seed.)  The pruned list
tokenises to slightly *more*, more fragmented tokens (N 14.13 M vs 13.92 M over
the same 2 065 806 identifiers), which apparently makes the matrix harder to
approximate by a few hundred clusters.  So the 2040 prune is a win for the raw
bigram score but **not** a drop-in win for the co-clustered production model;
re-tuning the clustering for the pruned matrix (or reconsidering adoption) is
the open question — plan C16.

## Which pairs are removed

Deletion is in increasing removal cost.  The **first** words removed (the least
valuable) are the rare, long overshoot words — e.g. `_Vtbl`, `Policy`, `Length`,
`Level`, `Number`, `Default`, `Version`, `View`, `Check`, `Method`, `Service`,
`ization` (cost ≈ 260–430 nats each).  The **last** words removed (the most
valuable of the overshoot) are short frequent fragments — `Be`, `ave`, `imit`,
`ender`, `Sel`, `Var` (cost ≈ 1000–1150 nats).  So the removal cost separates
"long specific word" from "short frequent morpheme" exactly as one would want.

The overlap diagnostic (`prune_words.py` prints it, and writes the full list to
`work/prune_512_removed.txt`) answers "is the overshoot the right size?": of the
256 deleted words, **80 are words the greedy-512 build would itself have kept**
and **176 are overshoot words**; so of the 512 kept words **432 are greedy-512
words and 80 are new** (not in greedy-512).  The two numbers are forced to
match: the overshoot pool is exactly greedy-512 ∪ 256 new words (the greedy
build is a prefix process), so `kept new = 256 − 176 = 80 = 80 removed greedy`.
Pruning is thus doing real work rather than truncating — it drops 80
early-created words the greedy build believed in (e.g. the rare `_Vtbl`) and
replaces them with 80 words the greedy-512 build never reached.

> An earlier revision of this section reported "14 kept words are new".  That
> was a bug in the diagnostic: `remap_rules` renumbers the kept words, but the
> overlap count indexed the *original* oversize symbol table with the *new* ids,
> so the kept-word names were read from the wrong slots.  The correct count is
> 80, which is the only value consistent with the 80/256 greedy deletions
> recorded in `work/prune_512_removed.txt`.

## Reading the overshoot size

The result is a clear win at 1.5× with a modest 0.86-bit gain, and the deleted
words are mostly overshoot-tail words rather than greedy words (176 of 256) —
so 1.5× is a reasonable setting; the gain per extra word is already small, so a
much larger overshoot would buy little more.

Where do the 80 kept new words come from within the overshoot?  Creation order
is roughly descending pair frequency, and the kept words are **front-loaded but
not confined to the front**.  Counting new words kept per 32 created, in
creation order:

| overshoot rank | 1–32 | 33–64 | 65–96 | 97–128 | 129–160 | 161–192 | 193–224 | 225–256 |
|---|---|---|---|---|---|---|---|---|
| kept / 32 | 15 | 14 | 12 | 12 | 13 | 4 | 3 | 7 |

66 of the 80 sit in the first 160 ranks (median rank 95), so the earlier overshoot
is much the more productive half.  But the tail still contributes 14 words the
greedy-512 build never reached (e.g. `eed`, `aut`, `air`, `del`, `vi`), so the
whole overshoot is doing some work — just with sharply diminishing returns,
which is exactly why 1.5× is enough.
