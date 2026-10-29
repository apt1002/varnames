#!/usr/bin/env python3
"""Turn a k-sweep log into the (model size, entropy) frontier of the study.

Reads a log of the form produced by sweeping ``cluster_substrings.py --k`` over
several thresholds, e.g.::

    ## H(next) etc for 10000
    substrings: 1950   ...
    H(next)             = 4.966 bits
    H(next | substring) = 3.070 bits
    ## nctx=1950  N=2102
    10000 1950 22 k = 22  H(next|cluster) = 3.8213 bits ...

and reports, for the cost model

    S(N, k) = 16 N + 128 k    bytes           (dense representation)

the Pareto frontier of (S, H) and the ratio k / N along it, plus the MDL
optimum for a corpus of C split positions.

Usage: cluster_size_frontier.py LOG [--C 41272149] [--bytes-sub 16] [--bytes-cl 128]
"""
import argparse
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cluster_substrings import read_table, h_given_cluster, entropy_bits

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
    ap.add_argument('--C', type=float, default=41_272_149.0,
                    help='number of split positions coded (corpus size)')
    ap.add_argument('--bytes-sub', type=int, default=16)
    ap.add_argument('--bytes-cl', type=int, default=128)
    ap.add_argument('--workdir', default='work',
                    help='root holding common$T/successor_distributions.tsv')
    args = ap.parse_args()
    bs, bc = args.bytes_sub, args.bytes_cl

    d = read_log(args.log)
    print(f"cost model: {bs} bytes/substring, {bc} bytes/cluster  "
          f"(ratio {bc/bs:.0f});  corpus C = {args.C:.3g} positions\n")
    print(f"{'T':>8} {'N':>6} {'nctx':>6} {'H(next)':>8} {'H|sub':>7} "
          f"{'k=nctx H':>9} {'S@k=nctx':>9}")
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
    print(f"\nPareto frontier ({len(fr)} points):")
    print(f"{'T':>8} {'N':>6} {'k':>6} {'k/N':>6} {'S bytes':>9} {'H bits':>7}")
    for s, h, (T, N, k) in fr:
        print(f"{T:>8} {N:>6} {k:>6} {k/N:>6.3f} {s:>9} {h:>7.4f}")

    # MDL optimum for a few corpus sizes
    print("\nMDL optimum  argmin[8 S + C H]:")
    print(f"{'C':>12} {'T':>8} {'N':>6} {'k':>6} {'k/N':>6} {'S':>8} "
          f"{'H':>7} {'model%':>7}")
    for C in (1e5, 1e6, 1e7, args.C, 1e8, 1e9):
        best = min(allpts, key=lambda p: 8 * p[0] + C * p[1])
        s, h, (T, N, k) = best
        tot = 8 * s + C * h
        print(f"{C:>12.0e} {T:>8} {N:>6} {k:>6} {k/N:>6.3f} {s:>8} "
              f"{h:>7.4f} {100*8*s/tot:>6.2f}%")


if __name__ == '__main__':
    main()
