# Tokenisation speed: is a precedence parser faster?

The tree-word tokeniser (`tree_words.tokenize`) is the hot loop of every
scoring and counting pass, so it is worth asking whether it can be made faster.
The question here: **given the word tree, can the tokenisation be done with an
operator-precedence parser (a stack) instead of the heap the code uses?**

Short answer: **a naive precedence parser is ~2.3× faster but wrong; a
correct preprocessing of the same idea — an ascending-rank bucket parser — is
exactly equivalent, ~1.4× faster, and is now the production path.**

## What the tokeniser does

A dictionary is a list of rules in creation order: pair merges `(a,b) -> c` and
run collapses. A *pair block* is a run of consecutive pair rules; tokenising
applies a block by repeatedly merging the **lowest-ranked** applicable adjacent
pair (ties leftmost), then the next block, and so on. The production code
(`_apply_pair_block`) does this with a doubly linked list of positions plus a
binary heap of candidate pairs — `O(n log n)`.

## The precedence parser (faster, but wrong)

The natural stack formulation: push each symbol; before pushing the next, keep
reducing the top pair while its rank is `<=` the rank of the pair it would form
with the lookahead. This is the classic shift/reduce comparison, and it is
2.3–2.5× faster (`tokenize_stack`, `_apply_pair_block_stack`).

It is **not** equivalent. On `selectFilesByVersion` (`tw96`) the pair ranks are

    se = 64    el = 42    le = 17    ec = 14    ct = —

Lowest rank first merges `ec` (14) then `el` (42), giving `s · el · ect`. The
stack parser, reaching `l`, defers `el` (42) in favour of the tighter `le` (17);
reaching `c` it defers `le` in favour of the tighter `ec` (14); it merges `ec`,
and now the pair `(l, ec)` directly above `el` is unmergeable, so the top of the
stack is a dead end and the still-reducible `el` is **buried** and never
merged. The stack only ever looks at the top pair; the true minimum can sit one
level down once an unmergeable pair has been pushed on top of it.

This is not rare: **~5 % of identifiers** tokenise differently (222 of 4 000 on
`tw96`; 1 288 of 25 000 on `tw2040`). So the plain precedence parser cannot be
used.

## The fix: an ascending-rank bucket parser (correct, and faster)

The heap can be replaced by a bucket queue because the ranks are **nested**: a
merge's rank always exceeds the ranks of the merges that built its operands
(the dictionary only defines a rule for a pair once both words exist). Hence a
merge never *creates* a pair with a rank lower than its own, so a single sweep
over ranks `0, 1, 2, …` performs exactly the lowest-rank-first merges. Pairs are
bucketed by rank (a dict, plus a tiny heap over the handful of *distinct* ranks
currently live); stale entries are skipped through the linked list. `O(n)` in
practice (`_apply_pair_block_buckets`, production `tokenize`).

## Benchmark

Held-out identifiers, `tokenizer_bench.py`; the reference is the heap
(`tokenize_heap`), verified byte-identical to the bucket parser.

| dictionary | n | heap (ms/id) | stack (ms/id) | stack ×  | stack mism. | buckets (ms/id) | buckets × | buckets mism. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `tw96` | 4 000 | 0.178 | 0.071 | 2.49× | 222 | 0.129 | 1.38× | **0** |
| `tw512` | 4 000 | 0.484 | 0.209 | 2.32× | 222 | 0.336 | 1.44× | **0** |
| `tw2040` | 4 000 | 0.656 | 0.291 | 2.26× | 222 | 0.462 | 1.42× | **0** |
| `tw2040` | 25 000 | 0.658 | 0.286 | 2.31× | 1 288 | 0.463 | 1.42× | **0** |

The bucket parser is `1.4×` faster and produces identical token sequences; the
stack parser is `2.3×` faster but unusable. The `1.4×` (not `2.5×`) reflects
that the bucket sweep still does a rank lookup and a bucket insert per merge,
so the heap's `O(log n)` factor was never the bottleneck — Python-level per-token
work is.

## Status

`tree_words.tokenize` now uses the bucket parser; `tokenizer_bench.py` checks it
against the heap reference; `check_tree_words.py` (synthetic + `--real`) still
passes. The precedence-parser experiment is kept in the code
(`_apply_pair_block_stack`) as the documented negative result.

Reproduce:

```sh
python3 scripts/tokenizer_bench.py work/tw2040 work/camel/merged_validation.txt --n 25000
python3 scripts/check_tree_words.py --trials 40
python3 scripts/check_tree_words.py --real
```
