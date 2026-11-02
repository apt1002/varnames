# Overshoot the word list, then prune by removal cost

Status: **succeeded.**  Building the run-aware dictionary 1.5× too large and
then deleting the least valuable words down to size gives a word list that codes
held-out identifiers **0.86 bits better** than the plain greedy build of the
same size (63.77 → 62.91 bits at `NUM_PAIRS = 512`), recovering most of the
1.52-bit advantage of the 1.5× larger list (62.25 bits).

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
