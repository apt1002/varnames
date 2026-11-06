#!/usr/bin/env python3
"""Cluster quarters, step 1: the pure accounting check (`docs/ENCODING.md` §5).

No sampling and no held-out set.  The question is what the three code layouts
cost *in bits*, computed exactly from the counts, so that the experiment is
priced before it is built:

    flat      one Huffman tree per left cluster over all `V` words   (yardstick)
    CF        cluster step + word step, one tree per right cluster
    CQF(q)    the same bottom trees, **truncated** at `q` survivors, plus a
              top stage with one tree of `k*q` leaves per left cluster

The mechanism in one line, per right cluster:

    in-cell loss avoided = sum of the mass of the `q-1` merges above the stop
    the same tokens in the top stage cost = H(quarter | left cluster) + rounding

so CQF beats CF by (loss avoided - top stage) and loses to flat by the same
amount.  `q = 2` and `q = 4` are both reported; the truncation is the only
grouping considered (an imposed partition would put the expensive unequal merge
*inside* a quarter, which is the loss the truncation exists to avoid).

Bits are the total Huffman cost over every transition of the counted corpus,
divided by the number of identifiers.  Bytes use the accounting of
`docs/ENCODING.md` §5.

Usage:
    quarter_accounting.py --dir work/tw512ns --k 16 --qs 2,4 --kappa 300
"""
import argparse
import heapq
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw


def huffman(weights, stop_at=1):
    """Huffman code lengths for `weights`, optionally truncating the build.

    Returns `(lengths, cost, groups)`: `lengths[i]` is the depth of item `i`
    **inside its surviving subtree**, `cost` is the total cost of the merges
    actually performed (so `stop_at=q` gives the bottom stage only), and `groups`
    lists the items of each survivor.

    `stop_at=1` builds the whole tree, so every length is the ordinary Huffman
    length and `cost` is the ordinary Huffman cost.
    """
    n = len(weights)
    w = [float(x) for x in weights]
    if n == 0:
        return np.zeros(0), 0.0, []
    if n <= stop_at:
        return np.zeros(n), 0.0, [list(range(n))]
    nodes = {i: None for i in range(n)}       # node -> (left, right), None = leaf
    heap = [(w[i], i) for i in range(n)]
    heapq.heapify(heap)
    cost = 0.0
    tag = n
    while len(heap) > stop_at:
        wa, a = heapq.heappop(heap)
        wb, b = heapq.heappop(heap)
        nodes[tag] = (a, b)
        cost += wa + wb
        heapq.heappush(heap, (wa + wb, tag))
        tag += 1
    lengths = np.zeros(n)
    groups = []
    for _, root in heap:
        g = []
        stack = [(root, 0)]
        while stack:
            node, d = stack.pop()
            ch = nodes[node]
            if ch is None:
                lengths[node] = d
                g.append(node)
            else:
                stack.append((ch[0], d + 1))
                stack.append((ch[1], d + 1))
        groups.append(sorted(g))
    return lengths, cost, groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--k', type=int, default=16)
    ap.add_argument('--qs', default='2,4')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V, nchars = M.shape[0], len(chars)
    stop = nchars
    alpha = args.kappa * V
    # M_ref = M + alpha * (r/T)(c/T)^T, row-blocked so no V x V temporaries.
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = alpha * c0 / T0
    for i0 in range(0, V, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del r0, cb
    M_ref = M
    N = float(M_ref[:, stop].sum())          # number of identifiers
    c = M_ref.sum(0)                         # unigram (column mass)

    rng = np.random.default_rng(args.seed)
    lcl, _ = cw.cluster_axis(M_ref, args.k, rng, 0)
    rng = np.random.default_rng(args.seed + 1)
    rcl, _ = cw.cluster_axis(M_ref, args.k, rng, 1)
    k = args.k

    # G[L, b] = sum_{a in L} M_ref[a, b]  -- the cell's word masses
    G = np.zeros((k, V))
    np.add.at(G, lcl, M_ref)

    # ---- flat: one tree per left cluster over all V words -------------------
    flat_cost = 0.0
    for L in range(k):
        _, cf_, _ = huffman(G[L])
        flat_cost += cf_

    # ---- CF: cluster step (k weights) + word step (one tree per rcl) --------
    Gc = np.zeros((k, k))
    for j in range(k):
        Gc[:, j] = G[:, rcl == j].sum(1)
    cf_top = 0.0
    for L in range(k):
        _, cc, _ = huffman(Gc[L])
        cf_top += cc
    cf_bot = 0.0
    for j in range(k):
        words = np.flatnonzero(rcl == j)
        _, cj, _ = huffman(c[words])
        cf_bot += cj

    print(f"{args.dir}: V={V}, k={k}, kappa={args.kappa}, "
          f"N={N:.0f} identifiers, {M_ref.sum():.0f} transitions")
    print(f"{'scheme':<18} {'bits/id':>9} {'=-flat':>8} {'bytes':>8}")
    vb = k * (2 * (k - 1) + k * np.log2(k)) + (2 * (V - k) + V * np.log2(V))
    vw = k * (2 * (V - 1) + V * np.log2(V))          # the flat table: k*V lengths
    print(f"{'flat':<18} {flat_cost / N:>9.3f} {0.0:>8.3f} {vw / 8:>8.0f}")
    _ = vb

    qs = [int(x) for x in args.qs.split(',')]
    # ---- CQF(q) per q ------------------------------------------------------
    for q in qs:
        ql = np.empty(V, dtype=np.int64)
        bot_len = np.zeros(V)
        avoided = 0.0
        for j in range(k):
            words = np.flatnonzero(rcl == j)
            lens, cost_trunc, groups = huffman(c[words], stop_at=q)
            _, cost_full, _ = huffman(c[words], stop_at=1)
            avoided += cost_full - cost_trunc
            for gi, g in enumerate(groups):
                ql[words[g]] = j * q + gi
            bot_len[words] = lens
        kq = k * q
        # top stage: mass of each quarter in each left cluster
        S = np.zeros((k, kq))
        for a in range(V):
            S[lcl[a]] += np.bincount(ql, weights=M_ref[a], minlength=kq)
        top = 0.0
        top_ent = 0.0
        for L in range(k):
            _, cc, _ = huffman(S[L])
            top += cc
            p = S[L][S[L] > 0]
            p = p / p.sum()
            top_ent += float(np.sum(S[L])) * float(-(p * np.log2(p)).sum())
        bot = 0.0
        for J in range(kq):
            words = np.flatnonzero(ql == J)
            bot += float(np.sum(c[words] * bot_len[words]))
        cqf = top + bot
        vbq = (k * (2 * (k * q - 1) + k * q * np.log2(k * q))
               + (2 * (V - k * q) + V * np.log2(V)))
        print(f"{'CQF q=%d' % q:<18} {cqf / N:>9.3f} {(cqf - flat_cost) / N:>8.3f} "
              f"{vbq / 8:>8.0f}")
        print(f"  top stage {top / N:.3f} bits/id (entropy-optimal "
              f"{top_ent / N:.3f}) vs CF's cluster step {cf_top / N:.3f}, "
              f"so the top stage costs {(top - cf_top) / N:+.3f} more;")
        print(f"  in-cell merges avoided {avoided / N:.3f} bits/id "
              f"=> net {(avoided - (top - cf_top)) / N:+.3f} bits/id "
              f"for {(vbq - vb) / 8:+.0f} B")

    cfb = k * (2 * (k - 1) + k * np.log2(k)) + (2 * (V - k) + V * np.log2(V))
    print(f"{'CF':<18} {(cf_top + cf_bot) / N:>9.3f} "
          f"{(cf_top + cf_bot - flat_cost) / N:>8.3f} {cfb / 8:>8.0f}")
    print(f"  cluster step {cf_top / N:.3f}, word step {cf_bot / N:.3f} bits/id")
    print("model bytes are ENCODING.md section 5's accounting; the flat column "
          "is a yardstick, not a shippable table.")


if __name__ == '__main__':
    main()
