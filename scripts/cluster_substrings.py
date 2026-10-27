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
The silhouette of every candidate k is estimated on a fixed random subsample of
the points (all points are still used as the reference set); this keeps the
O(n^2) distance work bounded as k grows.

Performance
-----------
The three hot operations (k-means assignment/accumulation and the silhouette
distance sweep) are O(n*k*d) and O(n^2*d).  The host BLAS is reference (netlib)
BLAS, which is far too slow for n ~ 1e4, so these are done by a small OpenMP
kernel compiled from scripts/fastkern.c (falling back to NumPy if gcc is
missing).

Input : <outdir>/successor_distributions.tsv
Output: <outdir>/clusters.tsv          substring, sample_size, cluster
        <outdir>/cluster_summary.txt   per-cluster profile + members
        <outdir>/cluster_selection.txt inertia/silhouette for a range of k

Usage: cluster_substrings.py [--outdir work/common10000] [--k K] [--alpha 1.0]
                             [--restarts 20] [--kmax 15] [--sil-sample 4000]
                             [--examples 25]
"""
import argparse
import ctypes
import os
import subprocess
import sys

import numpy as np

KERN = None

F32P = ctypes.POINTER(ctypes.c_float)
I32P = ctypes.POINTER(ctypes.c_int32)
F64P = ctypes.POINTER(ctypes.c_double)


def _f(a):
    return a.ctypes.data_as(F32P)


def _i(a):
    return a.ctypes.data_as(I32P)


def _d(a):
    return a.ctypes.data_as(F64P)


def load_kernel(dest):
    """Compile and load scripts/fastkern.c; return None on failure."""
    csrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fastkern.c')
    try:
        if not os.path.exists(dest) or os.path.getmtime(dest) < os.path.getmtime(csrc):
            subprocess.run(['gcc', '-O3', '-march=native', '-ffast-math', '-fopenmp',
                            '-shared', '-fPIC', '-o', dest, csrc],
                           check=True, capture_output=True)
        lib = ctypes.CDLL(dest)
    except Exception as exc:                                     # pragma: no cover
        print(f"fastkern unavailable ({exc}); falling back to NumPy",
              file=sys.stderr)
        return None
    lib.assign.argtypes = [F32P, ctypes.c_int, ctypes.c_int, F32P, ctypes.c_int, I32P]
    lib.matvec.argtypes = [F32P, ctypes.c_int, ctypes.c_int, F32P, F32P]
    lib.accumulate.argtypes = [F32P, ctypes.c_int, ctypes.c_int, I32P, ctypes.c_int, F64P]
    lib.silhouette_rows.argtypes = [F32P, ctypes.c_int, F32P, ctypes.c_int, ctypes.c_int,
                                    I32P, I32P, ctypes.c_int, I32P, F32P]
    return lib


# ---------------------------------------------------------------- core ops ---
def assign(X32, C32, k):
    n, d = X32.shape
    labels = np.empty(n, dtype=np.int32)
    if KERN is not None:
        KERN.assign(_f(X32), n, d, _f(C32), k, _i(labels))
    else:
        labels[:] = (X32 @ C32.T).argmax(1).astype(np.int32)
    return labels


def matvec(X32, c32):
    n, d = X32.shape
    out = np.empty(n, dtype=np.float32)
    if KERN is not None:
        KERN.matvec(_f(X32), n, d, _f(c32), _f(out))
    else:
        out[:] = X32 @ c32
    return out


def accumulate(X32, labels, k):
    n, d = X32.shape
    if KERN is not None:
        sums = np.empty((k, d), dtype=np.float64)
        KERN.accumulate(_f(X32), n, d, _i(labels), k, _d(sums))
        return sums
    sums = np.empty((k, d), dtype=np.float64)
    for t in range(d):
        sums[:, t] = np.bincount(labels, weights=X32[:, t], minlength=k)
    return sums


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


def kmeans_sphere(X32, k, rng, iters=100):
    n, d = X32.shape
    centers = np.empty((k, d), dtype=np.float32)
    i0 = int(rng.integers(n))
    centers[0] = X32[i0]
    d2 = np.maximum(2.0 - 2.0 * matvec(X32, centers[0]), 0.0).astype(np.float64)
    for j in range(1, k):                       # k-means++ style seeding
        tot = d2.sum()
        p = d2 / tot if tot > 0 else np.full(n, 1.0 / n)
        c = int(rng.choice(n, p=p))
        centers[j] = X32[c]
        d2 = np.minimum(d2, np.maximum(2.0 - 2.0 * matvec(X32, centers[j]), 0.0))
    labels = None
    for _ in range(iters):
        new_labels = assign(X32, centers, k)
        sums = accumulate(X32, new_labels, k)
        norm = np.linalg.norm(sums, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        new_centers = (sums / norm).astype(np.float32)
        if labels is not None and np.array_equal(new_labels, labels):
            centers, labels = new_centers, new_labels
            break
        centers, labels = new_centers, new_labels
    dot = (X32 * centers[labels]).sum(1)
    inertia = float((2.0 - 2.0 * dot).sum())
    return labels, centers.astype(np.float64), inertia


def silhouette(X32, labels, qidx=None, chunk=1024):
    """Mean silhouette on the sphere (over qidx if given)."""
    n, d = X32.shape
    if qidx is None:
        Q, lq = X32, labels
    else:
        Q = np.ascontiguousarray(X32[qidx])
        lq = labels[qidx]
    nq = Q.shape[0]
    k = int(labels.max()) + 1
    n_c = np.bincount(labels, minlength=k).astype(np.int32)
    if KERN is not None:
        out = np.empty(nq, dtype=np.float32)
        KERN.silhouette_rows(_f(Q if Q.flags['C_CONTIGUOUS'] else np.ascontiguousarray(Q)),
                             nq, _f(X32), n, d, _i(lq), _i(labels), k, _i(n_c), _f(out))
        return float(out.mean())
    # ---- NumPy fallback ----
    n_cf = np.maximum(n_c.astype(np.float64), 1.0)
    M = np.zeros((n, k), dtype=np.float64)
    M[np.arange(n), labels] = 1.0
    M /= n_cf[None, :]
    scores = np.empty(nq, dtype=np.float64)
    for s in range(0, nq, chunk):
        e = min(s + chunk, nq)
        D = 2.0 - 2.0 * (Q[s:e] @ X32.T)
        np.maximum(D, 0.0, out=D)
        np.sqrt(D, out=D)
        S = D @ M
        ri = np.arange(e - s)
        own = lq[s:e]
        a = np.where(n_c[own] > 1,
                     S[ri, own] * n_c[own] / np.maximum(n_c[own] - 1.0, 1.0), 0.0)
        S[ri, own] = np.inf
        b = S.min(1)
        m = np.maximum(a, b)
        scores[s:e] = np.where(m > 0, (b - a) / m, 0.0)
    return float(scores.mean())


def main():
    global KERN
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default='work/common10000')
    ap.add_argument('--k', type=int, default=0)
    ap.add_argument('--alpha', type=float, default=1.0)
    ap.add_argument('--restarts', type=int, default=20)
    ap.add_argument('--kmax', type=int, default=15)
    ap.add_argument('--sil-sample', type=int, default=4000,
                    help='points used to estimate silhouette for k selection '
                         '(0 = all)')
    ap.add_argument('--examples', type=int, default=25)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    KERN = load_kernel(os.path.join(args.outdir, 'fastkern.so'))
    if KERN is not None:
        print("using compiled OpenMP kernel scripts/fastkern.c")

    syms, names, C, glob = read_table(
        os.path.join(args.outdir, 'successor_distributions.tsv'))
    n = C.shape[0]
    tot = C.sum(1, keepdims=True)
    q = glob / glob.sum()
    P = (C + args.alpha * q[None, :]) / (tot + args.alpha)   # smoothed
    X = np.sqrt(P).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    X = np.ascontiguousarray(X)
    print(f"substrings: {n}  successor alphabet: {C.shape[1]}  alpha: {args.alpha}")

    rng = np.random.default_rng(args.seed)

    if args.k:
        ks = [args.k]
    else:
        ks = list(range(2, args.kmax + 1))

    if args.sil_sample and n > args.sil_sample:
        qidx = np.sort(rng.choice(n, args.sil_sample, replace=False))
    else:
        qidx = None

    results = {}
    for k in ks:
        best = None
        for _ in range(args.restarts):
            labels, centers, inertia = kmeans_sphere(X, k, rng)
            if best is None or inertia < best[2]:
                best = (labels, centers, inertia)
        sil = silhouette(X, best[0], qidx)
        results[k] = (best, sil)
        print(f"k={k:3d}  inertia={best[2]:9.2f}  silhouette={sil:+.4f}", flush=True)

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
