#!/usr/bin/env python3
"""Test whether the "gain x shape" structure of the rank-L Hellinger cloud is
real or an artefact of the low-rank reconstruction.

`scripts/factor_cloud.py` plots the left/right clouds `U*sqrt(sigma)` and
`V*sqrt(sigma)` of `sqrt(M_ref)`.  Visually the cloud looks like a product of a
radial "gain" (peaked near the origin) and an angular "shape" independent of the
radius, which would suggest separating a scalar gain from a low-dimensional
shape.  This script tests that claim honestly.

Two exact facts frame the test:

* **full rank, the radius is just the mass.**  `||sqrt(M_ref)[a,:]||^2 =
  row mass_a`, so the "radial function" is the word-frequency distribution --
  not itself a low-rank artefact.
* **the SVD radial coordinate is a sigma-weighted norm.**  In the cloud
  `X = U*sqrt(sigma)`, `r_w = sqrt(sum_k sigma_k U[w,k]^2)`; direction and radius
  are independent for *equal* `sigma` (spherical symmetry) but coupled whenever
  the `sigma` differ.  So some radius/direction dependence is *built into the
  SVD scaling*, independently of the data.

Statistic: energy distance between the direction samples in the low- and
high-radius halves, permutation-tested against random halves and normalised by
the mean pairwise distance (`E/MPD`).  `p > 0.05` => independence.

Nulls: matrices that go through the *same* pipeline but have no gain/shape
structure by construction -- `indep` (`M[a,b] = g_a * p_a[b]`, independent gain
and shape), `coupled` (gain drives the concentration of `p_a`), and `iid`
(i.i.d. random).  If the real cloud is no more radius/direction-dependent than
these, the visual structure is generic SVD geometry, not data structure.

Usage:
    shape_gain_test.py --dir work/tw2040
    shape_gain_test.py --dir work/tw2040 --sub 800 --nperm 100 --rank-max 256
"""
import argparse
import os
import sys

import numpy as np
from scipy.sparse.linalg import svds

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_cloud as fc


def topk(A, k, seed=0):
    """Top-`k` SVD, descending (a full SVD of the 2104^2 matrix is ~100 s)."""
    U, s, Vt = svds(A, k=k, random_state=seed)
    order = np.argsort(s)[::-1]
    return U[:, order], s[order], Vt[order]


def distmat(X):
    x2 = (X * X).sum(1)
    D = x2[:, None] + x2[None, :] - 2.0 * (X @ X.T)
    np.maximum(D, 0.0, out=D)
    np.sqrt(D, out=D)
    return D


def within(D, idx):
    n = len(idx)
    if n < 2:
        return 0.0
    return D[np.ix_(idx, idx)].sum() / (n * (n - 1))


def dep_test(radius, direction, nperm=100, seed=0):
    """Return `(E/MPD, p)`: radius-vs-direction dependence (energy distance)."""
    rng = np.random.default_rng(seed)
    n = len(radius)
    D = distmat(direction)
    mpd = D[np.triu_indices(n, 1)].mean()
    med = np.median(radius)
    lo, hi = np.where(radius <= med)[0], np.where(radius > med)[0]

    def stat(a, b):
        return 2.0 * D[np.ix_(a, b)].mean() - within(D, a) - within(D, b)

    obs = stat(lo, hi)
    order = np.arange(n)
    null = np.empty(nperm)
    for k in range(nperm):
        rng.shuffle(order)
        null[k] = stat(order[:len(lo)], order[len(lo):])
    p = (1 + np.sum(null >= obs)) / (1 + nperm)
    return obs / mpd, p


def run_cloud(name, coords, sub=None, seed=0, **kw):
    if sub and len(coords) > sub:
        idx = np.random.default_rng(seed).choice(len(coords), sub, replace=False)
        coords = coords[idx]
    r = np.linalg.norm(coords, axis=1)
    d = coords / np.maximum(r[:, None], 1e-300)
    eff, p = dep_test(r, d, **kw)
    verdict = 'DEPENDENT' if p < 0.05 else 'independent'
    print(f"  {name:14s} radius(median {np.median(r):8.3f})  "
          f"E/MPD={eff:8.4f}  p={p:.3f}  {verdict}", flush=True)


def synthetic(seed, V, coupled=False, iid=False):
    rng = np.random.default_rng(seed)
    if iid:
        return rng.random((V, V))
    g = np.exp(rng.normal(0, 1.0, V))
    conc = (0.5 + 6.0 * (g / g.max())) if coupled else 0.5 * np.ones(V)
    P = np.empty((V, V))
    for i in range(V):
        P[i] = rng.dirichlet(conc[i] * np.ones(V))
    return g[:, None] * P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw2040')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--sub', type=int, default=800,
                    help='subsample points for the O(n^2) energy distance')
    ap.add_argument('--nperm', type=int, default=100)
    ap.add_argument('--rank-max', type=int, default=256)
    args = ap.parse_args()
    kw = dict(nperm=args.nperm)

    M_ref, uni, sym = fc.load_model(args.dir, args.kappa)
    A = np.sqrt(np.maximum(M_ref, 0.0))
    V = A.shape[0]
    U, s, Vt = topk(A, min(args.rank_max, V - 1))
    Etot = (A * A).sum()

    print("=== 1. rank sweep: radius vs direction (both full L-dim) ===",
          flush=True)
    for L in (2, 4, 8, 16, 64, 256):
        if L > len(s):
            break
        left = U[:, :L] * np.sqrt(s[:L])
        right = Vt[:L].T * np.sqrt(s[:L])
        print(f" rank {L}: energy {100 * (s[:L] ** 2).sum() / Etot:.1f}%",
              flush=True)
        run_cloud('left', left, sub=args.sub, **kw)
        run_cloud('right', right, sub=args.sub, **kw)

    print("\n=== 2. full-rank raw test (no SVD): gain = row mass, "
          "direction = row/||row|| ===", flush=True)
    run_cloud('left/raw', A, sub=args.sub, **kw)
    run_cloud('right/raw', A.T, sub=args.sub, **kw)

    print("\n=== 3. controls (same pipeline, no real gain/shape structure) ===",
          flush=True)
    for tag, kwargs in (('indep gain/shape', dict(coupled=False)),
                        ('coupled gain/shape', dict(coupled=True)),
                        ('iid random', dict(iid=True))):
        Mk = synthetic(1, V, **kwargs)
        Mk = Mk / Mk.sum() * M_ref.sum()
        Ak = np.sqrt(Mk)
        Uk, sk, Vkt = topk(Ak, 4)
        print(f" {tag}:", flush=True)
        run_cloud(' left/r4', Uk[:, :4] * np.sqrt(sk[:4]), sub=args.sub, **kw)
        run_cloud(' right/r4', Vkt[:4].T * np.sqrt(sk[:4]), sub=args.sub, **kw)
        print(f" {tag}, full rank:", flush=True)
        run_cloud(' left/raw', Ak, sub=args.sub, **kw)
        run_cloud(' right/raw', Ak.T, sub=args.sub, **kw)


if __name__ == '__main__':
    main()
