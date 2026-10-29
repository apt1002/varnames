#!/usr/bin/env python3
"""Cluster common substrings by successor distribution and write assignments.

This is the command-line driver; the library functions live in
``cluster_substrings_lib.py``.  It reads <outdir>/successor_distributions.tsv,
runs occurrence-weighted K-means (``--method kl`` or ``--method sphere``) with
several restarts, and writes the cluster assignment and a per-cluster profile.

Input : <outdir>/successor_distributions.tsv
Output: <outdir>/clusters.tsv          substring, sample_size, cluster
        <outdir>/cluster_summary.txt   per-cluster profile + members

Usage: cluster_substrings.py --k K [--outdir work/common10000]
                             [--method kl|sphere] [--alpha 1.0]
                             [--restarts 20] [--examples 25] [--seed 1]
"""
import argparse
import os

import numpy as np

from cluster_substrings_lib import (
    read_table,
    kmeans_sphere,
    kmeans_kl,
    h_given_cluster,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default='work/common10000')
    ap.add_argument('--k', type=int, required=True,
                    help='number of clusters (no automatic selection; sweep by '
                         'hand if a H(next|cluster) vs k curve is wanted)')
    ap.add_argument('--method', choices=('kl', 'sphere'), default='kl',
                    help="'kl' minimises occurrence-weighted cross-entropy "
                         "(H(next|cluster)); 'sphere' is Hellinger K-means")
    ap.add_argument('--alpha', type=float, default=1.0)
    ap.add_argument('--restarts', type=int, default=20)
    ap.add_argument('--examples', type=int, default=25)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    syms, names, C, glob = read_table(
        os.path.join(args.outdir, 'successor_distributions.tsv'))
    n = C.shape[0]
    tot = C.sum(1, keepdims=True)
    Ns = tot[:, 0]
    q = glob / glob.sum()
    P = (C + args.alpha * q[None, :]) / (tot + args.alpha)   # smoothed
    X = np.sqrt(P).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    X = np.ascontiguousarray(X)
    print(f"substrings: {n}  successor alphabet: {C.shape[1]}  "
          f"alpha: {args.alpha}  method: {args.method}")

    rng = np.random.default_rng(args.seed)

    k = args.k
    best, best_bits = None, None
    for _ in range(args.restarts):
        if args.method == 'sphere':
            labels, centers, _ = kmeans_sphere(X, Ns, k, rng)
        else:
            labels, centers, _ = kmeans_kl(C, Ns, q, k, rng, args.alpha)
        bits = h_given_cluster(C, labels)
        if best_bits is None or bits < best_bits:
            best_bits, best = bits, (labels, centers)
    labels, centers = best
    print(f"k = {k}  H(next|cluster) = {best_bits:.4f} bits "
          f"(best of {args.restarts} restarts)", flush=True)

    # ---- write assignments ----
    with open(os.path.join(args.outdir, 'clusters.tsv'), 'w') as f:
        f.write('substring\tsample_size\tcluster\n')
        for i in range(n):
            f.write(f"{names[i]}\t{int(tot[i, 0])}\t{int(labels[i])}\n")

    # ---- per-cluster profile (pooled counts = the cluster's predictive dist) ----
    sym_arr = np.array(list(syms))
    with open(os.path.join(args.outdir, 'cluster_summary.txt'), 'w') as f:
        order = sorted(range(len(centers)),
                       key=lambda j: -(labels == j).sum())
        for j in order:
            members = np.nonzero(labels == j)[0]
            agg = C[members].sum(0)
            n_j = agg.sum()
            pj = agg / n_j if n_j > 0 else q
            top = np.argsort(-pj)[:6]
            succ = ' '.join(f"{sym_arr[t]}:{pj[t]:.2f}" for t in top)
            f.write(f"cluster {j}: {members.size} members, "
                    f"{int(n_j)} samples\n")
            f.write(f"  top successors (prob): {succ}\n")
            ex = sorted((names[i] for i in members),
                        key=lambda s: (len(s), s))[:args.examples]
            f.write(f"  examples: {' '.join(repr(e) for e in ex)}\n\n")
    print(f"wrote {os.path.join(args.outdir, 'clusters.tsv')}")
    print(f"wrote {os.path.join(args.outdir, 'cluster_summary.txt')}")


if __name__ == '__main__':
    main()
