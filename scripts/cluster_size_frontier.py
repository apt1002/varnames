#!/usr/bin/env python3
"""Turn a k-sweep log into the (model size, entropy) frontier of the study.

Reads a log produced by sweeping ``cluster_substrings.py --k`` over several
thresholds, e.g.::

    ## H(next) etc for 10000
    ## nctx=1950  N=2102
    10000 1950 22 k = 22  H(next|cluster) = 3.8213 bits ...

The model is paid for once and then used on a very large corpus, so the model
size is a *resource*, not a term to be amortised against the data: we do not add
it to a data-coding cost (no MDL).  The study is therefore a pure Pareto
question -- for the cost model

    S(N, k) = 16 N + 128 k    bytes           (dense representation)

report the frontier (min H for a given S) and the ratio k / N along it.

Usage: cluster_size_frontier.py LOG [--bytes-sub 16] [--bytes-cl 128]
"""
import argparse
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cluster_substrings_lib import read_table, h_given_cluster, entropy_bits

HDR_RE = re.compile(r'## H\(next\) etc for (\d+)')
NCTX_RE = re.compile(r'## nctx=(\d+)\s+N=(\d+)')
PT_RE = re.compile(r'^(\d+) (\d+) (\d+) .*H\(next\|cluster\) = ([0-9.]+) bits')


def read_log(path):
    """Return dict T -> {'N','nctx','pts':[(k,H),...]} from a sweep log."""
    d = {}
    cur = None
    for ln in open(path):
        m = HDR_RE.search(ln)
        if m:
            cur = m.group(1)
            d.setdefault(cur, {'N': None, 'nctx': None, 'pts': []})
            continue
        m = NCTX_RE.search(ln)
        if m:
            cur = cur or m.group(2)   # fall back: no header line
            e = d.setdefault(cur, {'N': None, 'nctx': None, 'pts': []})
            e['nctx'], e['N'] = int(m.group(1)), int(m.group(2))
            continue
        m = PT_RE.match(ln)
        if m:
            T, nctx, k, h = m.group(1), int(m.group(2)), int(m.group(3)), float(m.group(4))
            e = d.setdefault(T, {'N': None, 'nctx': nctx, 'pts': []})
            e['nctx'] = nctx
            e['pts'].append((k, h))
    return d


def table_entropies(succ_tsv):
    """(H(next), H(next|substring)) in bits, or (nan, nan) if no table."""
    if not os.path.exists(succ_tsv):
        return float('nan'), float('nan')
    syms, names, C, glob = read_table(succ_tsv)
    p = glob / max(glob.sum(), 1.0)
    h_next = entropy_bits(p)
    h_sub = h_given_cluster(C, np.arange(C.shape[0]))
    return h_next, h_sub


def frontier(points):
    """Lower-left envelope of (S, H): drop points dominated by smaller S,H."""
    pts = sorted(points)
    out, best = [], np.inf
    for s, h, meta in pts:
        if h < best - 1e-12:
            out.append((s, h, meta))
            best = h
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--bytes-sub', type=int, default=16)
    ap.add_argument('--bytes-cl', type=int, default=128)
    ap.add_argument('--budgets', default='20000,50000,100000',
                    help='model-size budgets (bytes) to report the best (N,k)')
    ap.add_argument('--workdir', default='work',
                    help='root holding common$T/successor_distributions.tsv')
    args = ap.parse_args()
    bs, bc = args.bytes_sub, args.bytes_cl

    d = read_log(args.log)
    print(f"cost model: {bs} bytes/substring, {bc} bytes/cluster  "
          f"(ratio {bc/bs:.0f}); model paid once (no data term)\n")
    print(f"{'T':>8} {'N':>6} {'nctx':>6} {'H(next)':>8} {'H|sub':>7} "
          f"{'H@k=nctx':>9} {'S@k=nctx':>9}")
    allpts = []
    for T in sorted(d, key=lambda x: -int(x)):
        e = d[T]
        if e.get('N') is None or not e['pts']:
            continue
        k = e['nctx']
        hmax = min((h for kk, h in e['pts'] if kk == k), default=float('nan'))
        S = bs * e['N'] + bc * k
        hn, hs = table_entropies(
            os.path.join(args.workdir, f'common{T}', 'successor_distributions.tsv'))
        print(f"{T:>8} {e['N']:>6} {k:>6} {hn:>8.3f} {hs:>7.3f} "
              f"{hmax:>9.4f} {S:>9}")
        for kk, h in e['pts']:
            allpts.append((bs * e['N'] + bc * kk, h, (int(T), e['N'], kk)))

    fr = frontier(allpts)
    print(f"\nPareto frontier ({len(fr)} points).  'bits/doubling' = local "
          f"dH/dlog2(S); 'B per 0.01 bit' = extra bytes for the next "
          f"0.01 bits saved:")
    print(f"{'T':>8} {'N':>6} {'k':>6} {'k/N':>6} {'S bytes':>9} {'H bits':>7} "
          f"{'bits/dbl':>9} {'B/0.01b':>8}")
    for i, (s, h, (T, N, k)) in enumerate(fr):
        if i + 1 < len(fr):
            s2, h2, _ = fr[i + 1]
            dlog = np.log2(s2) - np.log2(s)
            slope = (h - h2) / dlog if dlog > 0 else np.nan
            bpc = (s2 - s) / max((h - h2) / 0.01, 1e-12) if h > h2 else np.nan
        else:
            slope = bpc = np.nan
        print(f"{T:>8} {N:>6} {k:>6} {k/N:>6.3f} {s:>9} {h:>7.4f} "
              f"{slope:>9.4f} {bpc:>8.0f}")

    # best (N,k) for a given model-size budget: lowest H with S <= budget
    print(f"\nBest model within a size budget (min H with S <= budget):")
    print(f"{'budget B':>9} {'T':>8} {'N':>6} {'k':>6} {'k/N':>6} {'S':>8} "
          f"{'H':>7}")
    for b in [int(x) for x in args.budgets.split(',')]:
        cand = [p for p in allpts if p[0] <= b]
        if not cand:
            continue
        s, h, (T, N, k) = min(cand, key=lambda p: p[1])
        print(f"{b:>9} {T:>8} {N:>6} {k:>6} {k/N:>6.3f} {s:>8} {h:>7.4f}")

    # summary of the k/N ratio along the frontier
    ratios = [k / N for _, _, (T, N, k) in fr]
    if ratios:
        print(f"\nk/N along the frontier: min {min(ratios):.3f}, "
              f"max {max(ratios):.3f}, first {ratios[0]:.3f}, "
              f"last {ratios[-1]:.3f}")


if __name__ == '__main__':
    main()
