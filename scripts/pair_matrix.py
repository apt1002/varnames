#!/usr/bin/env python3
"""Build the prefix/suffix adjacency matrix M and its low-rank factors.

This is the command-line driver; the library functions live in
``pair_matrix_lib.py``.  For every split of every wrapped identifier, records
the longest common-substring suffix of the left half and prefix of the right
half as an edge in a dense N x N count matrix, then factorises the matrix
(by default in the sqrt/Hellinger domain) and writes the factors.

Outputs (in --outdir):
    pair_matrix_L<L>.npy   the rank-L factors U (N x L), V (N x L), singular
                           values, and the vocabulary
    pair_stats.txt         N, nnz, density, and relative error vs L, for both
                           the SVD and (optionally) NMF

Usage: pair_matrix.py CORPUS SUBS [--outdir DIR] [--lsvd 2,4,8,16,32,64]
                    [--nmf L] [--nmf-iters 100] [--max-n 6000]
                    [--no-sqrt] [--seed 1]
"""
import argparse
import os

import numpy as np

from pair_matrix_lib import (
    load_or_build_matrix,
    randomized_svd,
    nmf,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common10000')
    ap.add_argument('--lsvd', default='2,4,8,16,32,64')
    ap.add_argument('--nmf', type=int, default=0)
    ap.add_argument('--nmf-iters', type=int, default=100)
    ap.add_argument('--max-n', type=int, default=6000)
    ap.add_argument('--no-sqrt', action='store_true',
                    help='factorise M itself instead of sqrt(M) (the old '
                         'count-space behaviour)')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    vocab = [ln.rstrip(b'\n') for ln in open(args.substrings, 'rb')]
    M = load_or_build_matrix(args.corpus, args.substrings, args.outdir)
    n = len(vocab)
    A = M if args.no_sqrt else np.sqrt(M)
    domain = 'count' if args.no_sqrt else 'sqrt'
    fro = float(np.linalg.norm(A))
    nnz = int((M > 0).sum())
    print(f"M: {n} x {n}  nnz {nnz}  density {100 * nnz / n / n:.3f}%  "
          f"||M||_F {float(np.linalg.norm(M)):.1f}  domain={domain}")

    lines = [f"N\t{n}", f"nnz\t{nnz}", f"density\t{nnz / n / n:.6f}",
             f"frobenius\t{fro:.6f}", f"domain\t{domain}",
             "L\tsvd_relerr\tnmf_relerr"]
    rng = np.random.default_rng(args.seed)
    if n > args.max_n:
        print(f"N = {n} exceeds --max-n {args.max_n}: skipping factorisation")
        with open(os.path.join(args.outdir, 'pair_stats.txt'), 'w') as f:
            f.write('\n'.join(lines) + '\n')
        return

    nmf_relerr = {}
    if args.nmf:
        W, H = nmf(A, args.nmf, rng, args.nmf_iters)
        nmf_relerr[args.nmf] = float(np.linalg.norm(A - W @ H)) / fro

    for L in [int(x) for x in args.lsvd.split(',') if int(x) <= n]:
        U, s, Vt = randomized_svd(A, L, rng)
        approx = (U * s) @ Vt
        err = float(np.linalg.norm(A - approx)) / fro
        neg = float((U < 0).mean()), float((Vt < 0).mean())
        print(f"L={L:3d}  svd relerr {err:.4f}  (neg entries U {neg[0]:.2f}, "
              f"V {neg[1]:.2f})", flush=True)
        np.save(os.path.join(args.outdir, f'pair_factors_L{L}.npy'),
                {'U': U, 's': s, 'V': Vt, 'sqrt': (not args.no_sqrt),
                 'vocab': np.array(vocab, dtype=object)})
        lines.append(f"{L}\t{err:.6f}\t"
                     + (f"{nmf_relerr[L]:.6f}" if L in nmf_relerr else ''))
    with open(os.path.join(args.outdir, 'pair_stats.txt'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"wrote {os.path.join(args.outdir, 'pair_stats.txt')}")


if __name__ == '__main__':
    main()
