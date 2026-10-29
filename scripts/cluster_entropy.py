#!/usr/bin/env python3
"""Entropy (in bits) of the successor character for each cluster.

For a cluster, P(next character | cluster) is estimated by pooling the successor
counts of all of its member substrings:

    p_c = ( sum_{s in cluster} n_{s,c} ) / ( sum_{s in cluster} N_s )

and its Shannon entropy H = -sum_c p_c log2 p_c is reported in bits.  A low
entropy means the cluster is a good predictor of the next character; a high
entropy means the successors are near-uniform.

Also reported, for context:
  * H(next)            - entropy of the successor over all analysable
                         substrings (the reference distribution);
  * H(next | substring)- occurrence-weighted mean of the per-substring
                         successor entropies;
  * H(next | cluster)   - occurrence-weighted mean of the per-cluster
                         entropies = the conditional entropy given the cluster,
                         and the information the clustering retains,
                         H(next) - H(next | cluster).

Input : <outdir>/successor_distributions.tsv, <outdir>/clusters.tsv
Output: <outdir>/cluster_entropy.tsv  (cluster, size, samples, entropy_bits)
        and a report on stdout.

Usage: cluster_entropy.py [--outdir work/common10000]
"""
import argparse
import os

import numpy as np


def read_distributions(path):
    with open(path) as f:
        header = f.readline().rstrip('\n').split('\t')
        syms = header[2:]
        names, counts, glob = [], [], None
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if parts[0] == '#global':
                glob = np.array([int(x) for x in parts[2:]], dtype=np.float64)
                continue
            names.append(parts[0])
            counts.append([int(x) for x in parts[2:]])
    return syms, names, np.array(counts, dtype=np.float64), glob


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default='work/common10000')
    args = ap.parse_args()

    syms, names, C, glob = read_distributions(
        os.path.join(args.outdir, 'successor_distributions.tsv'))
    labels = []
    with open(os.path.join(args.outdir, 'clusters.tsv')) as f:
        f.readline()
        for line in f:
            labels.append(int(line.rstrip('\n').split('\t')[2]))
    labels = np.array(labels)
    Nrow = C.sum(1)

    # reference entropies over all analysable substrings
    pooled = C.sum(0)
    H_next = entropy_bits(pooled / pooled.sum())
    H_given_sub = float((Nrow * np.array([entropy_bits(row / row.sum())
                                          for row in C])).sum() / Nrow.sum())

    rows = []
    H_given_cluster = 0.0
    for j in sorted(set(labels), key=lambda j: -(labels == j).sum()):
        m = labels == j
        agg = C[m].sum(0)
        n = agg.sum()
        p = agg / n
        h = entropy_bits(p)
        H_given_cluster += (n / Nrow.sum()) * h
        rows.append((j, int(m.sum()), int(n), h))

    print(f"substrings: {len(names)}   clusters: {len(rows)}")
    print(f"H(next)             = {H_next:.3f} bits")
    print(f"H(next | substring) = {H_given_sub:.3f} bits")
    print(f"H(next | cluster)   = {H_given_cluster:.3f} bits")
    print(f"information retained by clustering = "
          f"{H_next - H_given_cluster:.3f} bits "
          f"({100 * (H_next - H_given_cluster) / H_next:.1f}% of H(next))\n")
    print(f"{'cluster':>7} {'size':>5} {'samples':>10} {'entropy(bits)':>13}")
    for j, size, n, h in rows:
        print(f"{j:>7} {size:>5} {n:>10} {h:>13.3f}")

    path = os.path.join(args.outdir, 'cluster_entropy.tsv')
    with open(path, 'w') as f:
        f.write('cluster\tsize\tsamples\tentropy_bits\n')
        for j, size, n, h in rows:
            f.write(f"{j}\t{size}\t{n}\t{h:.6f}\n")
    print(f"\nwrote {path}")


if __name__ == '__main__':
    main()
