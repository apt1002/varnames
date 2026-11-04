#!/usr/bin/env python3
"""C23: word-list size vs cluster-matrix budget.

The word x word adjacency matrix `M` is compressed as a `k x k` co-clustered
block table plus per-word linear tables (see `cluster_words.py`).  Its model
size is `store = k^2 + 2V` numbers.  This script sweeps several word lists
(different `V`) and cluster counts `k` and asks the budget question:

    at a fixed model size, is it better to spend on a larger word list (bigger
    `V`) or on a finer block matrix (bigger `k`)?

It prints, per word list, the held-out bits vs `store`, then a matched-size
frontier: for each budget the best `(V, k)` and its held-out bits.

Bit counts are **per held-out identifier** (the full cycle length of the token
sequence), so they are comparable across word lists as long as the validation
corpus is the same.

Usage:
    wordlist_budget.py --dirs work/tw2040 --ks 52,105,210
    wordlist_budget.py --dirs work/tw2040,work/tw4414,work/tw11694 \
        --ks 52,105,210,420 --csv out.csv
"""
import argparse
import csv
import gc
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw


def sweep(d, ks, kappa, validation, stride, seed, need_full_up_to=None):
    """Return `(V, b_full, rows)` for one word list `d`; rows = (k, store, bits)."""
    M, uni, chars, rules, sym = hf.dense_matrix(d)
    V = M.shape[0]
    nchars = len(chars)
    lines = tw.read_lines(validation, stride=stride)
    alpha = kappa * V
    _, P_mar, M_ref = hf.priors(M, alpha)
    del M
    gc.collect()
    b_full = cw.heldout_bits(M_ref, chars, rules, nchars, lines)
    rows = []
    for k in ks:
        if k >= V:
            continue
        rng = np.random.default_rng(seed)
        lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(seed + 1)
        rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
        _, assoc = cw.models(M_ref, lcl, rcl, k, k)
        b = cw.heldout_bits(assoc, chars, rules, nchars, lines)
        rows.append((k, k * k + 2 * V, b))
        print(f"  V={V:6d} k={k:5d} store={k * k + 2 * V:9d}  "
              f"assoc={b:8.3f}  (+{b - b_full:.3f})", flush=True)
        del lcl, rcl, assoc
        gc.collect()
    del M_ref
    gc.collect()
    return V, b_full, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', required=True,
                    help='comma list of word-model dirs (increasing V)')
    ap.add_argument('--ks', required=True, help='comma list of cluster counts')
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=20)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--csv', default=None)
    args = ap.parse_args()

    ks = [int(x) for x in args.ks.split(',')]
    all_rows = []
    for d in args.dirs.split(','):
        print(f"\n{d}", flush=True)
        V, b_full, rows = sweep(d, ks, args.kappa, args.validation,
                                args.stride, args.seed)
        print(f"  full table: V={V}  {b_full:.3f} bits/identifier", flush=True)
        for k, store, b in rows:
            all_rows.append((V, k, store, b, b_full))

    print("\n=== matched-size frontier (best word list k at each budget) ===")
    print("  store   best V   k    bits")
    stores = sorted({r[2] for r in all_rows})
    # dedupe to a coarse grid near the observed stores
    grid = []
    for s in stores:
        if not grid or s >= grid[-1] * 1.15:
            grid.append(s)
    for target in grid:
        cand = [r for r in all_rows if r[2] <= target]
        if not cand:
            continue
        V, k, store, b, _ = min(cand, key=lambda r: r[3])
        print(f"  {target:7d}   {V:6d} {k:5d}  {b:8.3f}")

    if args.csv:
        with open(args.csv, 'w', newline='', encoding='utf-8') as f:
            wr = csv.writer(f)
            wr.writerow(['V', 'k', 'store', 'assoc_bits', 'full_bits'])
            wr.writerows(all_rows)
        print(f"\nwrote {args.csv}")


if __name__ == '__main__':
    main()
