#!/usr/bin/env python3
"""Timing and verification driver for the rescan dictionary builder.

The builder itself now lives in ``tree_words`` (``read_corpus_array`` +
``build_dictionary_arr`` + ``count_adjacency_stream``); this script only times
it against the reference implementation and checks that the word list is
identical.  Keep it as the regression test for the fast path.

History: the reference ``build_dictionary`` keeps a
``{(a, b): {(seq, pos), ...}}`` position index and a list of lists of ids, which
is 10-100x the size of the packed array and is what made the full-corpus
(stride 0) build need gigabytes.  The rescan builder finds its occurrences with
a numpy scan of an int32 array instead.

Usage:
    word_build_rescan.py --sample 20 --num-pairs 2040 --check
    word_build_rescan.py --sample 0 --num-pairs 512        # time only
"""
import argparse
import sys
import time

import numpy as np

sys.path.insert(0, 'scripts')
import tree_words as tw                                        # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--num-pairs', type=int, default=2040)
    ap.add_argument('--sample', type=int, default=20)
    ap.add_argument('--corpus', default='work/camel/merged_training.txt')
    ap.add_argument('--lines', type=int, default=0)
    ap.add_argument('--check', action='store_true',
                    help='compare against tree_words.build_dictionary')
    a = ap.parse_args()

    t0 = time.time()
    chars, arr = tw.read_corpus_array(a.corpus, stride=a.sample, limit=a.lines)
    n_id = int(np.count_nonzero(arr == tw.SEP))
    print(f"{n_id} lines, {arr.size - n_id} chars, pairs {a.num_pairs} "
          f"(read {time.time() - t0:.1f}s, {arr.nbytes / 1e6:.0f} MB)",
          flush=True)

    t = time.time()
    chars2, rules2, sym2 = tw.build_dictionary_arr(chars, arr, a.num_pairs,
                                                   verbose=True)
    t_fast = time.time() - t
    print(f"fast: {t_fast:.1f}s  {len(rules2)} rules, vocab {len(sym2)}",
          flush=True)

    if a.check:
        lines = tw.read_lines(a.corpus, stride=a.sample, limit=a.lines)
        t = time.time()
        chars1, rules1, sym1 = tw.build_dictionary(lines, a.num_pairs)
        print(f"tree_words: {time.time() - t:.1f}s  {len(rules1)} rules, "
              f"vocab {len(sym1)}")
        print("chars equal:", chars == chars1)
        print("sym equal   :", sym2 == sym1)
        if sym2 != sym1:
            d = [i for i, (x, y) in enumerate(zip(sym2, sym1)) if x != y]
            print(f"  first diffs at {d[:5]}: "
                  f"{[(sym2[i], sym1[i]) for i in d[:5]]}")
        print("rules equal :", rules2 == rules1)

    if a.sample:
        cid = {c: i for i, c in enumerate(chars2)}
        plan = tw.make_plan(rules2, len(chars2))
        lines = tw.read_lines(a.corpus, stride=a.sample, limit=a.lines)
        t = time.time()
        big, uni = tw.count_adjacency(lines, cid, plan, len(chars2))
        t_ref = time.time() - t
        t = time.time()
        rows, cols, data, u2 = tw.count_adjacency_stream(
            a.corpus, cid, plan, len(chars2), len(sym2), stride=a.sample)
        print(f"adjacency: reference {t_ref:.1f}s, stream "
              f"{time.time() - t:.1f}s", flush=True)
        d = {(int(r), int(c)): float(v) for r, c, v in zip(rows, cols, data)}
        print("bigrams equal:", d == {k: float(v) for k, v in big.items()})
        u1 = np.zeros(len(sym2), np.int64)
        for k, v in uni.items():
            u1[k] = v
        print("unigrams equal:", np.array_equal(u1, u2))


if __name__ == '__main__':
    main()
