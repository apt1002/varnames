#!/usr/bin/env python3
"""Compress the word x word adjacency matrix by left/right K-means clustering.

The word bigram matrix ``M`` (``V x V``) is the largest table in the model.
Following the word-level analogue of ``docs/CLUSTER_SIZE_STUDY.md``, pool the
words into clusters and describe the matrix by two small objects:

* a ``k_L x k_R`` **block matrix** (the piecewise-constant part), and
* the per-word **linear tables**: the row and column marginals ``r, c`` and the
  ``word -> cluster`` labels.

Predecessors (rows) are clustered by their successor distribution ``p(.|a)``
and successors (columns) by their predecessor distribution ``p(.|b)``, both in
the **Hellinger** embedding ``sqrt(p)`` with occurrence weights (helpers of
``cluster_substrings_lib``).

Two block models are reported:

* **block** -- the plain block mean of ``M`` (constant on each cluster pair);
* **assoc** -- the marginal-factored block model
  ``M_hat[a,b] = r[a] c[b]/T * D[lcl(a), rcl(b)]``, where ``D`` is the block mean
  of ``M`` over the block mean of ``r c^T / T`` (equivalently the ratio of their
  block sums, the block sizes cancelling), so each block's mass is preserved
  exactly.

They are scored by the joint KL against the ``kappa`` reference and by the
**held-out** code length, against the full table and the rank-``L`` Hellinger
factorisation.  Also reported: the "removable" words ``(uv)`` whose left-cluster
equals ``v``'s and right-cluster equals ``u``'s, whose labels are redundant.

Usage:
    cluster_words.py --dir work/tw2040 --ks 26,52,105,210 --stride 20
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import pair_matrix_lib as pml
import cluster_substrings_lib as csl


def cluster_axis(M, k, rng, axis):
    """Cluster rows (axis=0) or columns (axis=1) in Hellinger space."""
    if axis == 0:
        w = M.sum(1)
        P = M / np.maximum(w[:, None], 1e-300)
    else:
        w = M.sum(0)
        P = M.T / np.maximum(w[:, None], 1e-300)
    X = np.ascontiguousarray(np.sqrt(np.maximum(P, 0.0)), dtype=np.float32)
    labels, centers, inertia = csl.kmeans_sphere(X, w, k, rng)
    return labels, centers


def block_sum(M, lcl, rcl, kL, kR, W):
    # lcl / rcl = left / right cluster label of each word (not lc/rc = children).
    idx = (lcl[:, None] * kR + rcl[None, :]).ravel()
    return np.bincount(idx, weights=W.ravel(),
                       minlength=kL * kR).reshape(kL, kR)


def models(M, lcl, rcl, kL, kR):
    r = M.sum(1)
    c = M.sum(0)
    T = float(M.sum())
    e = np.outer(r, c) / T
    nL = np.bincount(lcl, minlength=kL).astype(float)
    nR = np.bincount(rcl, minlength=kR).astype(float)
    blk = block_sum(M, lcl, rcl, kL, kR, M) / np.maximum(np.outer(nL, nR), 1.0)
    # D = (block mean of M) / (block mean of e) = ratio of their block sums.
    D = (block_sum(M, lcl, rcl, kL, kR, M)
         / np.maximum(block_sum(M, lcl, rcl, kL, kR, e), 1e-300))
    assoc = e * D[lcl][:, rcl]
    return blk[lcl][:, rcl], assoc


def bits_of(P, chars, rules, nchars, lines):
    """Held-out mean bits given a V x V matrix of transition probabilities."""
    logp = np.log2(np.maximum(P, 1e-12))
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tw.make_plan(rules, nchars)
    stop = nchars
    bits = np.empty(len(lines))
    for j, s in enumerate(lines):
        seq = tw.tokenize(s, char_id, plan, nchars) + [stop]
        n = len(seq)
        b = 0.0
        for i in range(n):
            b -= logp[seq[i], seq[(i + 1) % n]]
        bits[j] = b
    return float(bits.mean())


def heldout_bits(Mhat, chars, rules, nchars, lines, P_mar=None, alpha=0.0):
    Ms = Mhat if P_mar is None else Mhat + alpha * P_mar
    P = Ms / np.maximum(Ms.sum(1, keepdims=True), 1e-300)
    return bits_of(P, chars, rules, nchars, lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', default='',
                    help='comma list of clusters per side (default V/20)')
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=20)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = M.shape[0]
    nchars = len(chars)
    ks = ([int(x) for x in args.ks.split(',')] if args.ks
          else [max(2, V // 20)])
    lines = tw.read_lines(args.validation, stride=args.stride)
    alpha = args.kappa * V
    _, P_mar, M_ref = hf.priors(M, alpha)
    b_full = heldout_bits(M_ref, chars, rules, nchars, lines)
    print(f"{args.dir}: V={V}, held-out n={len(lines)}, "
          f"full table {b_full:.3f} bits", flush=True)
    print("  k     store(cc)  assoc-bits  1sided-bits  drop/V   | "
          "sqrtcnt-match: L store bits")
    for k in ks:
        rng = np.random.default_rng(args.seed)
        lcl, CL = cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, CR = cluster_axis(M_ref, k, rng, 1)
        blk, assoc = models(M_ref, lcl, rcl, k, k)
        ba = heldout_bits(assoc, chars, rules, nchars, lines)
        # one-sided: predict p(.|a) by the pooled row distribution of lcl(a)
        P1 = np.maximum(CL.astype(np.float64), 0.0) ** 2
        P1 = P1 / np.maximum(P1.sum(1, keepdims=True), 1e-300)
        b1 = bits_of(P1[lcl], chars, rules, nchars, lines)
        store = k * k + 2 * V
        drop = 0
        npair = 0
        for r, item in enumerate(rules):
            if item[0] == 'pair':
                npair += 1
                _, (a, b), _ = item
                wid = nchars + 1 + r
                if lcl[wid] == lcl[b] and rcl[wid] == rcl[a]:
                    drop += 1
        L = max(1, int(round(store / (2.0 * V))))
        Ms = hf.sqrtcnt(M_ref, min(L, V))
        bs = heldout_bits(Ms, chars, rules, nchars, lines)
        print(f"  {k:<5d} {store:<10d} {ba:<12.3f} {b1:<12.3f} "
              f"{drop:>3d}/{npair:<3d} | L={L:<3d} {2*V*L:<6d} {bs:.3f}",
              flush=True)


if __name__ == '__main__':
    main()
