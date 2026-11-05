#!/usr/bin/env python3
"""How many words per identifier, and what a Huffman code would cost.

An arithmetic code spends a *fractional* number of bits per token,
`-log2 P(b|a)`; a Huffman code must spend a whole number, and the price of that
rounding is paid once per token.  So the number of words per identifier is the
multiplier on the Huffman penalty, and the two numbers together say how much
switching from arithmetic to Huffman coding would cost.

Because the `assoc` model's transition probability depends on the left *cluster*
only, a per-cluster Huffman tree is exactly realisable; the code lengths are
computed for each left cluster and the held-out identifiers are charged with
them.

Usage:
    words_per_identifier.py --dir work/tw2040 --ks 52 --stride 10
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
import model_fit_rates as mfr


def huffman_lengths(p, V):
    """Huffman code length (bits) of every symbol, as a length-`V` array."""
    p = np.asarray(p, dtype=np.float64)
    pos = np.where(p > 0)[0]
    n = len(pos)
    out = np.zeros(V, dtype=np.int64)
    if n == 0:
        return out
    if n == 1:
        out[pos[0]] = 1
        return out
    parent = [-1] * (2 * n - 1)
    heap = [(float(p[pos[k]]), k) for k in range(n)]
    heapq.heapify(heap)
    nxt = n
    while len(heap) > 1:
        wa, a = heapq.heappop(heap)
        wb, b = heapq.heappop(heap)
        parent[a] = nxt
        parent[b] = nxt
        heapq.heappush(heap, (wa + wb, nxt))
        nxt += 1
    for k in range(n):
        d, x = 0, k
        while parent[x] != -1:
            x = parent[x]
            d += 1
        out[pos[k]] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', required=True)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=10)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = M.shape[0]
    nchars = len(chars)
    lines = tw.read_lines(args.validation, stride=args.stride)
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = args.kappa * V * c0 / T0
    for i0 in range(0, V, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del r0, c0, cb

    seqs = mfr.tokenise(lines, chars, rules, nchars)
    n_id = len(seqs)
    nw = np.array([len(s) - 1 for s in seqs])      # words, excluding the stop
    ntok = int(sum(len(s) for s in seqs))
    print(f"{args.dir}: V={V}, n={n_id} identifiers, {ntok} tokens "
          f"(kappa={args.kappa})")

    # --- histogram of words per identifier ----------------------------------
    print("\nwords per identifier (excluding the stop token):")
    hi = int(nw.max())
    counts = np.bincount(nw, minlength=hi + 1)
    cum, rows = 0, []
    for i in range(1, hi + 1):
        if counts[i]:
            cum += counts[i]
            rows.append((i, int(counts[i]), 100.0 * cum / n_id))
    half = (len(rows) + 1) // 2
    for k in range(half):
        a = rows[k]
        b = rows[k + half] if k + half < len(rows) else (None, None, None)
        left = f"  {a[0]:>4} words {a[1]:>7} ({a[2]:>5.1f}%)"
        right = ("" if b[0] is None
                 else f"    {b[0]:>4} words {b[1]:>7} ({b[2]:>5.1f}%)")
        print(left + right)
    q = np.percentile(nw, [50, 90, 99, 100])
    print(f"  mean {nw.mean():.2f} words/id, median {q[0]:.0f}, p90 {q[1]:.0f}, "
          f"p99 {q[2]:.0f}, max {q[3]:.0f}")

    # --- Huffman vs arithmetic ----------------------------------------------
    a_all = np.concatenate([np.asarray(s, dtype=np.int64) for s in seqs])
    b_all = np.concatenate([np.roll(np.asarray(s, dtype=np.int64), -1)
                            for s in seqs])
    logm = np.log2(np.maximum(M, 1e-300))
    logr = np.log2(np.maximum(M.sum(1), 1e-300))
    b_full = logm[a_all, b_all] - logr[a_all]

    for k in [int(x) for x in args.ks.split(',')]:
        rng = np.random.default_rng(args.seed)
        lcl, _ = cw.cluster_axis(M, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, _ = cw.cluster_axis(M, k, rng, 1)
        c, D, Cc = mfr.assoc_numbers(M, lcl, rcl, k)
        den = D @ Cc
        logc = np.log2(np.maximum(c, 1e-300))
        logD = np.log2(np.maximum(D, 1e-300))
        logden = np.log2(np.maximum(den, 1e-300))
        Prow = (c[None, :] * D[:, rcl]) / np.maximum(den[:, None], 1e-300)
        Prow = Prow / Prow.sum(1, keepdims=True)

        Larr = np.empty((k, V), dtype=np.int64)
        for i in range(k):
            Larr[i] = huffman_lengths(Prow[i], V)
        A = lcl[a_all]
        b_ideal = logc[b_all] + logD[A, rcl[b_all]] - logden[A]
        b_huff = Larr[A, b_all]

        id_ideal = np.zeros(n_id)
        id_huff = np.zeros(n_id)
        off = 0
        for j, s in enumerate(seqs):
            m = len(s)
            id_ideal[j] = -b_ideal[off:off + m].sum()
            id_huff[j] = b_huff[off:off + m].sum()
            off += m

        red = float((b_huff - (-b_ideal)).sum()) / len(a_all)
        print(f"\nHuffman vs arithmetic (k={k}, one tree per left cluster, "
              f"{len(a_all)} tokens):")
        print(f"  arithmetic {id_ideal.sum() / n_id:8.3f} bits/id")
        print(f"  Huffman    {id_huff.sum() / n_id:8.3f} bits/id")
        print(f"  penalty    {(id_huff - id_ideal).sum() / n_id:8.3f} bits/id "
              f"({100 * (id_huff - id_ideal).sum() / id_ideal.sum():.2f}%), "
              f"{red:.3f} bits per token over {len(a_all) / n_id:.2f} tokens/id")
        for name, val in (('fit<=64', 64.0), ('fit<=128', 128.0)):
            print(f"  {name}: arithmetic {100 * (id_ideal <= val).mean():.1f}%"
                  f" -> Huffman {100 * (id_huff <= val).mean():.1f}%")
        pen = id_huff - id_ideal
        print(f"  penalty: min {pen.min():.2f}, p50 {np.percentile(pen, 50):.2f}"
              f", p90 {np.percentile(pen, 90):.2f}, max {pen.max():.2f} bits; "
              f"Huffman is *shorter* on {100 * (pen < 0).mean():.1f}% of ids")


if __name__ == '__main__':
    main()
