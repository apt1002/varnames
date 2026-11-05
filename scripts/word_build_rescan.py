#!/usr/bin/env python3
"""Prototype: build the word list by *rescanning* the whole corpus
sample each merge, instead of maintaining a position index.

Idea: keep the corpus as one compact ``int64`` array with a separator ``-1``
between identifiers (no holes, no positions).  Each step:

* find the most frequent pair from an incrementally-maintained count dict
  (and heap) -- counting is cheap and local;
* find its occurrences by a global numpy scan  ``(arr[:-1]==a)&(arr[1:]==b)``;
* rebuild the array with those occurrences merged (vectorised, O(N));
* fix up the counts for the pairs touching a merged slot, vectorised.

This is the same algorithm as ``tree_words.build_dictionary`` (most-frequent
pair, self-merges forbidden), with the position index and all the hole logic
removed.

Status: *prototype, not wired into the pipeline.*  It produces a byte-identical
word list (``chars``, ``sym``, ``rules``) and on the stride-20 sample is ~2x
faster and ~30% lighter (see the plan).  The rescan is O(N) per merge, so time
it at ``--sample 0`` before switching the default.
"""
import sys
import time
import heapq
from collections import Counter

import numpy as np

SEP = -1


def _counts_all(arr):
    """Pair -> count over the whole array, excluding separator adjacencies."""
    if len(arr) < 2:
        return {}
    m = (arr[:-1] != SEP) & (arr[1:] != SEP)
    ka = arr[:-1][m].tolist()
    kb = arr[1:][m].tolist()
    return Counter(zip(ka, kb))


def build_fast(chars, seqs, num_pairs, verbose=False):
    nchars = len(chars)
    sym = list(chars) + ['\n']
    rules = []
    next_id = nchars + 1
    budget = num_pairs

    pieces = []
    for s in seqs:
        pieces.append(np.asarray(s, dtype=np.int64))
        pieces.append(np.array([SEP], dtype=np.int64))
    arr = np.concatenate(pieces) if pieces else np.empty(0, dtype=np.int64)

    def seg_bounds(a):
        sep = np.flatnonzero(a == SEP)
        starts = np.concatenate(([0], sep[:-1] + 1))
        return starts, sep

    cnt = dict(_counts_all(arr))
    heap = [(-c, p) for p, c in cnt.items() if c > 1 and p[0] != p[1]]
    heapq.heapify(heap)

    step = 0
    while budget > 0:
        p = None
        while heap:
            neg, pp = heapq.heappop(heap)
            if cnt.get(pp, 0) == -neg and -neg > 1 and pp[0] != pp[1]:
                p = pp
                break
        if p is None:
            break
        a, b = p

        # ---- pair merge ----
        idx = np.flatnonzero((arr[:-1] == a) & (arr[1:] == b))
        if idx.size == 0:
            cnt[p] = 0
            continue
        new = next_id
        next_id += 1
        sym.append(sym[a] + sym[b])
        rules.append(('pair', (a, b), new))

        # Count diff, vectorised.  Only pairs touching a merged slot change.
        # For a chain of adjacent occurrences (..a b a b..) the pair *between*
        # two merged tokens is (b,a) (removed once, via the second's left) and
        # (new,new) (created once, via the first's right), so the left/right
        # contributions are suppressed on the "inside" of a chain.
        n = arr.size
        isocc = np.zeros(n, dtype=bool)
        isocc[idx] = True
        L = idx - 1
        Lm = np.maximum(L, 0)
        Lvalid = (L >= 0) & (arr[Lm] != SEP)
        Ltok = arr[Lm]
        cl = np.maximum(idx - 2, 0)
        chain_left = (idx - 2 >= 0) & isocc[cl]
        R = idx + 2
        Rm = np.minimum(R, n - 1)
        Rin = R < n
        Rvalid = Rin & (arr[Rm] != SEP)
        Rtok = arr[Rm]
        chain_right = Rin & isocc[Rm]

        rem = Counter({(a, b): int(idx.size)})
        for x in Ltok[Lvalid].tolist():
            rem[(x, a)] += 1
        for y in Rtok[Rvalid & ~chain_right].tolist():
            rem[(b, y)] += 1
        cre = Counter()
        for y in np.where(chain_right, new, Rtok)[Rvalid].tolist():
            cre[(new, y)] += 1
        for x in Ltok[Lvalid & ~chain_left].tolist():
            cre[(x, new)] += 1

        d = Counter(cre)
        d.subtract(rem)
        for q, dc in d.items():
            if dc:
                cnt[q] = cnt.get(q, 0) + dc
                if cnt[q] > 1 and q[0] != q[1]:
                    heapq.heappush(heap, (-cnt[q], q))
        cnt[p] = 0

        keep = np.ones(n, dtype=bool)
        keep[idx + 1] = False
        arr2 = arr.copy()
        arr2[idx] = new
        arr = arr2[keep]
        budget -= 1
        step += 1
        if verbose and step % 500 == 0:
            print(f"  step {step} pair {sym[new]!r} vocab {len(sym)}",
                  flush=True)
    return chars, rules, sym


def main():
    sys.path.insert(0, 'scripts')
    import tree_words as tw
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--num-pairs', type=int, default=2040)
    ap.add_argument('--sample', type=int, default=20)
    ap.add_argument('--corpus', default='work/camel/merged_training.txt')
    ap.add_argument('--lines', type=int, default=0)
    ap.add_argument('--check', action='store_true',
                    help='compare against tree_words.build_dictionary')
    a = ap.parse_args()

    lines = tw.read_lines(a.corpus, stride=a.sample)
    if a.lines:
        lines = lines[:a.lines]
    chars = sorted(set(''.join(lines)))
    cid = {c: i for i, c in enumerate(chars)}
    seqs = [[cid[c] for c in s] for s in lines]
    print(f"{len(lines)} lines, {sum(map(len, seqs))} chars, "
          f"pairs {a.num_pairs}", flush=True)

    t = time.time()
    chars2, rules2, sym2 = build_fast(chars, seqs, a.num_pairs, verbose=True)
    t_fast = time.time() - t
    print(f"fast: {t_fast:.1f}s  {len(rules2)} rules, vocab {len(sym2)}",
          flush=True)

    if a.check:
        t = time.time()
        chars1, rules1, sym1 = tw.build_dictionary(lines, a.num_pairs)
        print(f"tree_words: {time.time()-t:.1f}s  {len(rules1)} rules, "
              f"vocab {len(sym1)}")
        print("chars equal:", chars == chars1)
        print("sym equal   :", sym2 == sym1)
        if sym2 != sym1:
            d = [i for i, (x, y) in enumerate(zip(sym2, sym1)) if x != y]
            print(f"  first diffs at {d[:5]}: "
                  f"{[(sym2[i], sym1[i]) for i in d[:5]]}")
        print("rules equal :", rules2 == rules1)


if __name__ == '__main__':
    main()
