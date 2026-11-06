#!/usr/bin/env python3
"""The bytes-for-fit frontier as a curve, not two points.

Every pricing decision so far -- C26's +0.08 pt, C27's recovery estimate, C28's
nets -- was referred to a frontier slope obtained from two or three measured
configurations: `k = 32 -> 64` at `V = 4096` (4,088 B for 0.733 bits) and
`V = 4096 -> 8192` at `k = 64` (18,432 B for 3.34 bits).  Both gave ≈5.5 kB per
bit, which was comforting, but a two-point slope cannot say whether the frontier
is straight, where it bends, or whether a candidate sits above or below it
locally.

This sweeps `k` at fixed `V` with the *same* accounting and the *same* held-out
set, so the curve and its local slope fall out:

    model bytes = word (2(V-k) + V log V) + uni V
                + mem 2 V log k             (two labellings)
                + block k*k                 (the D table)
    bits        = assoc model, held-out, `model_fit_rates.bits_assoc`

That is the accounting used in `SHARED_CLUSTERS.md` (17,400 B at 4096/32), so
the slopes are directly comparable with the 5.5 kB/bit figure.  Note it differs
from the code-bytes-only accounting in `ENCODING.md` §5 by the unigram table,
the assignment map and the block -- a roughly `k`-independent offset, so *within
a sweep* the two agree and only absolute levels move.

Usage:
    k_frontier.py --dir work/tw512ns --ks 8,12,16,24,32 --stride 100
    k_frontier.py --dir work/tw4096ns --ks 16,24,32,48,64,96 --stride 100
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import model_fit_rates as mfr
from newline_cluster import model_from, plain_labels


def model_bytes(V, k):
    word = (2 * (V - k) + V * np.log2(V)) / 8.0
    uni = float(V)
    mem = 2.0 * V * np.log2(k) / 8.0
    blk = float(k * k)
    return word + uni + mem + blk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', default='8,12,16,24,32')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=100)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V, nchars = M.shape[0], len(chars)
    stop = nchars
    _, _, M_ref = hf.priors(M, args.kappa * V)
    del M, uni

    lines = tw.read_lines(args.validation, stride=args.stride)
    seqs = mfr.tokenise(lines, chars, rules, nchars)
    del lines

    ks = [int(x) for x in args.ks.split(',')]
    rows = []
    print(f"{args.dir}: V={V}, kappa={args.kappa}, held-out n={len(seqs)} "
          f"(stride {args.stride})")
    print(f"{'k':>4} {'bits/id':>9} {'fit<=64':>8} {'fit<=128':>9} "
          f"{'bytes':>9}")
    for k in ks:
        lcl, rcl = plain_labels(M_ref, k, stop, args.seed)
        m = model_from(M_ref, lcl, rcl, k)
        bits = mfr.bits_assoc(seqs, m['logc'], m['logD'], m['logden'],
                              lcl, rcl)
        by = model_bytes(V, k)
        rows.append(dict(k=k, bits=bits.mean(), f64=(bits <= 64).mean() * 100,
                         f128=(bits <= 128).mean() * 100, by=by))
        print(f"{k:>4} {bits.mean():>9.3f} {rows[-1]['f64']:>7.1f}% "
              f"{rows[-1]['f128']:>8.1f}% {by:>9.0f}")

    # ---- local slopes: each step, and the Pareto steps only -------------------
    print(f"\n{'step':>10} {'dB':>8} {'dbytes':>8} {'kB/bit':>8} "
          f"{'d fit64':>8} {'kB/pt':>8}")
    for a, b in zip(rows, rows[1:]):
        db = b['bits'] - a['bits']
        dby = b['by'] - a['by']
        dfit = b['f64'] - a['f64']
        kb_bit = (dby / 1000) / (-db) if db < 0 else float('nan')
        kb_pt = (dby / 1000) / dfit if dfit > 0 else float('nan')
        s_bit = f"{kb_bit:8.2f}" if np.isfinite(kb_bit) else '       -'
        s_pt = f"{kb_pt:8.2f}" if np.isfinite(kb_pt) else '       -'
        print(f"{a['k']:>4}->{b['k']:<5} {db:>+8.3f} {dby:>+8.0f} {s_bit} "
              f"{dfit:>+7.1f}pt {s_pt}")

    # ---- Pareto set (fewer bytes AND worse bits is dominated) ----------------
    keep = []
    for r in sorted(rows, key=lambda r: r['by']):
        if not keep or r['bits'] < keep[-1]['bits'] - 1e-9:
            keep.append(r)
    print("\nfrontier points: " +
          ', '.join(f"k={r['k']} ({r['bits']:.2f} bits, {r['by']:.0f} B)"
                    for r in keep))
    if len(keep) > 2:
        base, last = keep[0], keep[-1]
        print(f"end-to-end {last['by'] - base['by']:.0f} B for "
              f"{base['bits'] - last['bits']:.3f} bits = "
              f"{(last['by'] - base['by']) / (base['bits'] - last['bits']):.0f} "
              f"B/bit over k={base['k']}..{last['k']}")


if __name__ == '__main__':
    main()
