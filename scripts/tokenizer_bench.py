#!/usr/bin/env python3
"""Is a precedence parser a faster tokeniser?  Benchmarks the tree-word
tokeniser two ways and checks they agree.

The production `tokenize` reduces pair blocks with a linked list + heap (O(n log
n)); `tokenize_stack` uses an operator-precedence parser (a stack that reduces
local minima, O(n)).  This script tokenises a sample with both, asserts the
token sequences are identical, and times each.

Usage:
    tokenizer_bench.py work/tw2040 work/camel/merged_validation.txt --n 20000
"""

import argparse
import random
import sys
import time
from os.path import dirname, abspath

sys.path.insert(0, dirname(abspath(__file__)))
import tree_words as tw                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dictionary")
    ap.add_argument("corpus")
    ap.add_argument("--n", type=int, default=20000,
                    help="identifiers to sample (0 = all)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    chars, rules, sym = tw.load_dictionary(args.dictionary)
    plan = tw.make_plan(rules, len(chars))
    char_id = {c: i for i, c in enumerate(chars)}
    nchars = len(chars)

    lines = tw.read_lines(args.corpus)
    if args.n and args.n < len(lines):
        random.Random(args.seed).shuffle(lines)
        lines = lines[:args.n]
    print(f"dictionary {args.dictionary}: {len(rules)} rules; "
          f"{len(lines):,} identifiers")

    t0 = time.time()
    ref = [tw.tokenize_heap(s, char_id, plan, nchars) for s in lines]
    t_ref = time.time() - t0

    t0 = time.time()
    stk = [tw.tokenize_stack(s, char_id, plan, nchars) for s in lines]
    t_stk = time.time() - t0

    t0 = time.time()
    bkt = [tw.tokenize(s, char_id, plan, nchars) for s in lines]
    t_bkt = time.time() - t0

    bad_s = sum(1 for a, b in zip(ref, stk) if a != b)
    bad_b = sum(1 for a, b in zip(ref, bkt) if a != b)
    print(f"heap(ref): {t_ref:6.2f}s   ({1000 * t_ref / len(lines):.4f} ms/id)")
    print(f"stack   : {t_stk:6.2f}s   ({1000 * t_stk / len(lines):.4f} ms/id)"
          f"  speedup {t_ref / t_stk:.2f}x  mismatches {bad_s}")
    print(f"buckets : {t_bkt:6.2f}s   ({1000 * t_bkt / len(lines):.4f} ms/id)"
          f"  speedup {t_ref / t_bkt:.2f}x  mismatches {bad_b}")
    wrong = stk if bad_s else bkt
    if bad_s or bad_b:
        for s, a, b in zip(lines, ref, wrong):
            if a != b:
                print(f"  MISMATCH {s!r}\n    heap {a}\n    fast {b}")
                break


if __name__ == "__main__":
    main()
