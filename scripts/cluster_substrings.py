#!/usr/bin/env python3
"""Group common substrings by their successor distribution using K-means.

Model
-----
Each analysable common substring has an empirical successor distribution
p = (p_c).  Following the discussion, each distribution is embedded on the unit
sphere by the square root map

    x = ( sqrt(p_c) )_c ,      ||x|| = 1

so that the squared Euclidean distance between two embedded distributions is
    ||x - y||^2 = 2 (1 - sum_c sqrt(p_c q_c)) = 2 * H^2(p, q),
twice the squared Hellinger distance.  This is a genuine metric and, for p
close to q, it locally equals the KL divergence KL(p||q) (which is the average
extra code length when coding samples of p with a model q): the non-metric
"compression distance" is thus approximated by a metric in the region where it
matters.

Missing data is handled by empirical-Bayes Dirichlet smoothing towards the
global successor distribution q (the '#global' row of the input):

    p_c = (n_c + alpha * q_c) / (N + alpha)

K-means is run on the sphere: assignment by nearest Euclidean distance
(= largest dot product with the centre), update by re-normalising the mean of
the assigned points, several restarts, and the best inertia is kept.  The
number of clusters is chosen by the mean silhouette score unless --k is given.

Input : <outdir>/successor_distributions.tsv
Output: <outdir>/clusters.tsv          substring, sample_size, cluster
        <outdir>/cluster_summary.txt   per-cluster profile + members
        <outdir>/cluster_selection.txt inertia/silhouette for a range of k

Usage: cluster_substrings.py [--outdir work/camel] [--k K] [--alpha 1.0]
                             [--restarts 20] [--kmax 15] [--examples 25]
"""
import argparse
import os

import numpy as np


def read_table(path):
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


def kmeans_sphere(X, k, rng, iters=200):
    n, d = X.shape
    centers = np.empty((k, d))
    i0 = int(rng.integers(n))
    centers[0] = X[i0]
    d2 = np.maximum(2.0 - 2.0 * (X @ centers[0]), 0.0)
    for j in range(1, k):
        tot = d2.sum()
        p = d2 / tot if tot > 0 else np.full(n, 1.0 / n)
        c = int(rng.choice(n, p=p))
        centers[j] = X[c]
        d2 = np.minimum(d2, np.maximum(2.0 - 2.0 * (X @ centers[j]), 0.0))
    labels = None
    for _ in range(iters):
        sim = X @ centers.T
        new_labels = sim.argmax(1)
        new_centers = np.zeros((k, d))
        for j in range(k):
            m = new_labels == j
            if m.any():
                new_centers[j] = X[m].sum(0)
        norm = np.linalg.norm(new_centers, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        new_centers /= norm
        if labels is not None and np.array_equal(new_labels, labels) and \
                np.allclose(new_centers, centers):
            centers = new_centers
            labels = new_labels
            break
        centers, labels = new_centers, new_labels
    sim = X @ centers.T
    inertia = float((2.0 - 2.0 * sim[np.arange(n), labels]).sum())
    return labels, centers, inertia


def silhouette(D, labels):
    n = D.shape[0]
    uniq = np.unique(labels)
    if uniq.size < 2:
        return -1.0
    scores = np.empty(n)
    for i in range(n):
        same = labels == labels[i]
        same[i] = False
        a = D[i, same].mean() if same.any() else 0.0
        b = np.inf
        for c in uniq:
            if c == labels[i]:
                continue
            other = labels == c
            if other.any():
                b = min(b, D[i, other].mean())
        scores[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
    return float(scores.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default='work/camel')
    ap.add_argument('--k', type=int, default=0)
    ap.add_argument('--alpha', type=float, default=1.0)
    ap.add_argument('--restarts', type=int, default=20)
    ap.add_argument('--kmax', type=int, default=15)
    ap.add_argument('--examples', type=int, default=25)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    syms, names, C, glob = read_table(
        os.path.join(args.outdir, 'successor_distributions.tsv'))
    n = C.shape[0]
    tot = C.sum(1, keepdims=True)
    q = glob / glob.sum()
    P = (C + args.alpha * q[None, :]) / (tot + args.alpha)   # smoothed
    X = np.sqrt(P)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    print(f"substrings: {n}  successor alphabet: {C.shape[1]}  alpha: {args.alpha}")

    rng = np.random.default_rng(args.seed)

    if args.k:
        ks = [args.k]
    else:
        ks = list(range(2, args.kmax + 1))

    D = np.sqrt(np.maximum(2.0 - 2.0 * (X @ X.T), 0.0))     # metric distances
    results = {}
    for k in ks:
        best = None
        for _ in range(args.restarts):
            labels, centers, inertia = kmeans_sphere(X, k, rng)
            if best is None or inertia < best[2]:
                best = (labels, centers, inertia)
        sil = silhouette(D, best[0])
        results[k] = (best, sil)
        print(f"k={k:2d}  inertia={best[2]:9.2f}  silhouette={sil:+.4f}")

    with open(os.path.join(args.outdir, 'cluster_selection.txt'), 'w') as f:
        f.write('k\tinertia\tsilhouette\n')
        for k in ks:
            f.write(f"{k}\t{results[k][0][2]:.2f}\t{results[k][1]:.4f}\n")

    if args.k:
        chosen = args.k
    else:
        chosen = max(ks, key=lambda k: results[k][1])
    labels, centers, inertia = results[chosen][0]
    print(f"\nchosen k = {chosen}  (silhouette {results[chosen][1]:+.4f}, "
          f"inertia {inertia:.2f})")

    # ---- write assignments ----
    with open(os.path.join(args.outdir, 'clusters.tsv'), 'w') as f:
        f.write('substring\tsample_size\tcluster\n')
        for i in range(n):
            f.write(f"{names[i]}\t{int(tot[i, 0])}\t{int(labels[i])}\n")

    # ---- per-cluster profile ----
    sym_arr = np.array(list(syms))
    with open(os.path.join(args.outdir, 'cluster_summary.txt'), 'w') as f:
        order = sorted(range(len(centers)),
                       key=lambda j: -(labels == j).sum())
        for j in order:
            members = np.nonzero(labels == j)[0]
            top = np.argsort(-centers[j])[:6]
            succ = ' '.join(f"{sym_arr[t]}:{centers[j][t]**2:.2f}" for t in top)
            f.write(f"cluster {j}: {members.size} members\n")
            f.write(f"  top successors (prob): {succ}\n")
            ex = sorted((names[i] for i in members),
                        key=lambda s: (len(s), s))[:args.examples]
            f.write(f"  examples: {' '.join(repr(e) for e in ex)}\n\n")
    print(f"wrote {os.path.join(args.outdir, 'clusters.tsv')}")
    print(f"wrote {os.path.join(args.outdir, 'cluster_summary.txt')}")
    print(f"wrote {os.path.join(args.outdir, 'cluster_selection.txt')}")


if __name__ == '__main__':
    main()
