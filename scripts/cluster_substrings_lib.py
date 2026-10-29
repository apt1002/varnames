"""Group common substrings by their successor distribution using K-means.
This module is the library half of ``cluster_substrings.py``; the executable
half (command-line driver) is there.

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

Two clustering objectives are provided:

* ``method='kl'`` (default): Lloyd's algorithm for the occurrence-weighted
  cross-entropy, i.e. it directly minimises
      sum_s N_s * H(p_s || P_{cluster(s)}),
  with the centre P_c the count-weighted mean of its members and assignment to
  the smallest cross-entropy (largest sum_x p_s(x) log P_c(x)).  This is exactly
  the quantity behind H(next | cluster), so it optimises what we report.

* ``method='sphere'``: K-means on the Hellinger embedding, assignment by nearest
  Euclidean distance (= largest dot product), update by re-normalising the
  occurrence-weighted mean of the members.  This is the metric surrogate
  discussed above; it minimises the occurrence-weighted squared Hellinger
  distortion sum_s N_s ||x_s - c_{cluster(s)}||^2.

Both weight every point by its occurrence count N_s and use k-means++ style
seeding (the sphere method seeds proportional to N_s * d^2) with several restarts
(the restart with the lowest H(next | cluster) is kept).

The number of clusters k is fixed by the caller.  There is deliberately no
automatic selection: every objective criterion tried (elbow of the bits curve,
mean silhouette, and in principle held-out compression) is either arbitrary or
merely relocates the arbitrariness -- the best compromise depends on how much
pressure one feels to keep the model low-dimensional.  Sweep k by hand if a curve
is wanted.
"""
import numpy as np


def assign(X32, C32, k):
    labels = (X32 @ C32.T).argmax(1).astype(np.int32)
    return labels


def matvec(X32, c32):
    return X32 @ c32


def accumulate(X32, labels, k, w):
    """Count-weighted cluster sums: sums[j,t] = sum_{i in j} w[i] * X32[i,t]."""
    n, d = X32.shape
    sums = np.empty((k, d), dtype=np.float64)
    for t in range(d):
        sums[:, t] = np.bincount(labels, weights=w * X32[:, t], minlength=k)
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


def kmeans_sphere(X32, w, k, rng, iters=100):
    """K-means on the Hellinger embedding, occurrence-weighted.

    Minimises sum_s w_s ||x_s - c_{cluster(s)}||^2 (w_s = the context's occurrence
    count) with c on the unit sphere; the weighted centroid is
    c = sum_{s in C} w_s x_s / ||sum_{s in C} w_s x_s||.  (The assignment step is
    unchanged by the weights: they are a per-point constant.)
    """
    n, d = X32.shape
    w = np.ascontiguousarray(w, dtype=np.float32)
    centers = np.empty((k, d), dtype=np.float32)
    i0 = int(rng.integers(n))
    centers[0] = X32[i0]
    d2 = np.maximum(2.0 - 2.0 * matvec(X32, centers[0]), 0.0).astype(np.float64)
    for j in range(1, k):                       # weighted k-means++ seeding
        p = d2 * w
        tot = p.sum()
        p = p / tot if tot > 0 else np.full(n, 1.0 / n)
        c = int(rng.choice(n, p=p))
        centers[j] = X32[c]
        d2 = np.minimum(d2, np.maximum(2.0 - 2.0 * matvec(X32, centers[j]), 0.0))
    labels = None
    for _ in range(iters):
        new_labels = assign(X32, centers, k)
        sums = accumulate(X32, new_labels, k, w)
        norm = np.linalg.norm(sums, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        new_centers = (sums / norm).astype(np.float32)
        if labels is not None and np.array_equal(new_labels, labels):
            centers, labels = new_centers, new_labels
            break
        centers, labels = new_centers, new_labels
    dot = (X32 * centers[labels]).sum(1)
    inertia = float(((2.0 - 2.0 * dot) * w).sum())
    return labels, centers.astype(np.float64), inertia


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def h_given_cluster(C, labels):
    """Occurrence-weighted H(next | cluster) in bits from pooled counts."""
    total = C.sum()
    h = 0.0
    for c in np.unique(labels):
        agg = C[labels == c].sum(0)
        n = agg.sum()
        if n > 0:
            h += (n / total) * entropy_bits(agg / n)
    return h


def kmeans_kl(C, Ns, q, k, rng, alpha, iters=100):
    """Lloyd's algorithm for occurrence-weighted cross-entropy (a.k.a. KL).

    Directly minimises  sum_s N_s * H(p_s || P_{cluster(s)})  with the centre
    P_c the count-weighted mean of its members -- which is exactly the quantity
    behind H(next | cluster).  Assignment is to the smallest cross-entropy
    (= largest sum_x p_s(x) log P_c(x)); the update is the pooled-count mean.
    Seeded k-means++ style using the Hellinger (2 H^2) distance.
    """
    n, d = C.shape
    P = (C + alpha * q[None, :]) / (Ns[:, None] + alpha)     # smoothed members
    X = np.sqrt(P)
    centers = np.empty((k, d))
    i0 = int(rng.integers(n))
    centers[0] = P[i0]
    d2 = np.maximum(2.0 - 2.0 * (X @ X[i0]), 0.0)
    for j in range(1, k):
        t = d2.sum()
        pj = d2 / t if t > 0 else np.full(n, 1.0 / n)
        c = int(rng.choice(n, p=pj))
        centers[j] = P[c]
        d2 = np.minimum(d2, np.maximum(2.0 - 2.0 * (X @ X[c]), 0.0))
    labels = None
    P32 = np.ascontiguousarray(P, dtype=np.float32)
    for _ in range(iters):
        logPc = np.log(np.maximum(centers, 1e-300))
        new_labels = assign(P32, np.ascontiguousarray(logPc, dtype=np.float32), k)
        aggC = np.zeros((k, d))
        aggN = np.zeros(k)
        for c in range(k):
            m = new_labels == c
            if m.any():
                aggC[c] = C[m].sum(0)
                aggN[c] = Ns[m].sum()
        new_centers = (aggC + alpha * q[None, :]) / (aggN[:, None] + alpha)
        if labels is not None and np.array_equal(new_labels, labels):
            centers, labels = new_centers, new_labels
            break
        centers, labels = new_centers, new_labels
    return labels, centers, h_given_cluster(C, labels)
