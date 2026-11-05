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


def huffman_lengths(p, V, zero=None):
    """Huffman code length (bits) of every symbol, as a length-`V` array.

    `zero` is an optional symbol index whose weight is driven to zero before the
    build (the stop token: its bits are never spent, so it must not shape the
    other codes).  The symbol keeps its leaf in a real build; here it simply
    drops out, which gives the lengths of the renormalised code.
    """
    p = np.asarray(p, dtype=np.float64).copy()
    if zero is not None:
        p[zero] = 0.0
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
    ap.add_argument('--zero-stop', action='store_true',
                    help='build the trees with the stop weighted zero and charge '
                         'only the non-stop tokens (the zero-padding terminator)')
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

        stop = nchars
        Larr = np.empty((k, V), dtype=np.int64)
        for i in range(k):
            Larr[i] = huffman_lengths(Prow[i], V,
                                      stop if args.zero_stop else None)
        if args.zero_stop:
            # where the all-zeros codeword lands, i.e. the padding the decoder
            # may have to read; build once more with a vestigial stop weight
            Lzero = np.empty(k, dtype=np.int64)
            for i in range(k):
                q = Prow[i].copy()
                q[stop] = 1e-12
                Lzero[i] = huffman_lengths(q, V)[stop]
        A = lcl[a_all]
        b_ideal = logc[b_all] + logD[A, rcl[b_all]] - logden[A]
        b_huff = Larr[A, b_all]

        # `a` is the token, `b` its successor in the rolled cycle, so the stop
        # appears once as a `b` per identifier.  Under the zero-padding
        # terminator that transition is never paid, so the codec charges every
        # token except it (`keep`); the cyclic model charges both stop edges.
        keep = b_all != stop

        def per_id(x, mask=None):
            out = np.zeros(n_id)
            off = 0
            for j, s in enumerate(seqs):
                m = len(s)
                seg = x[off:off + m]
                if mask is not None:
                    seg = seg[mask[off:off + m]]
                out[j] = seg.sum()
                off += m
            return out

        id_ideal = per_id(-b_ideal)
        id_huff = per_id(b_huff)
        id_ideal_c = per_id(-b_ideal, keep)
        id_huff_c = per_id(b_huff, keep)

        # --- factored: cluster step + word step, two Huffman trees ----------
        Pc = (D * Cc[None, :]) / np.maximum(den[:, None], 1e-300)   # P(j|i)
        Lc = np.empty((k, k), dtype=np.int64)
        for i in range(k):
            Lc[i] = huffman_lengths(Pc[i], k)
        Lw = np.empty((k, V), dtype=np.int64)
        for j in range(k):
            pj = np.zeros(V)
            m = rcl == j
            pj[m] = c[m] / max(Cc[j], 1e-300)
            Lw[j] = huffman_lengths(pj, V)
        Rb = rcl[b_all]
        b_huff2 = Lc[A, Rb] + Lw[Rb, b_all]
        id_huff2 = np.zeros(n_id)
        off = 0
        for jj, ss in enumerate(seqs):
            m = len(ss)
            id_huff2[jj] = b_huff2[off:off + m].sum()
            off += m
        redc = float((Lc[A, Rb] + np.log2(np.maximum(Pc[A, Rb], 1e-300))).sum()) / len(a_all)
        redw = float((Lw[Rb, b_all] + np.log2(np.maximum(c[b_all] / Cc[Rb], 1e-300))).sum()) / len(a_all)
        red2 = float((b_huff2 - (-b_ideal)).sum()) / len(a_all)
        print(f"\n  factored, k={k} (tree per left cluster over k, tree per "
              f"right cluster over its words):")
        print(f"    Huffman {id_huff2.sum() / n_id:8.3f} bits/id, penalty "
              f"{(id_huff2 - id_ideal).sum() / n_id:8.3f} bits/id "
              f"({100 * (id_huff2 - id_ideal).sum() / id_ideal.sum():.2f}%), "
              f"{red2:.3f} bits/token")
        print(f"    split: cluster step {redc:.3f} bits/token, word step "
              f"{redw:.3f} bits/token")
        for name, val in (('fit<=64', 64.0), ('fit<=128', 128.0)):
            print(f"    {name}: arithmetic {100 * (id_ideal <= val).mean():.1f}%"
                  f" -> factored Huffman {100 * (id_huff2 <= val).mean():.1f}%")

        ntok = len(a_all)
        red = float((id_huff - id_ideal).sum()) / ntok
        print(f"\nHuffman vs arithmetic (k={k}, one tree per left cluster, "
              f"{ntok} tokens):")
        print(f"  arithmetic {id_ideal.sum() / n_id:8.3f} bits/id")
        print(f"  Huffman    {id_huff.sum() / n_id:8.3f} bits/id")
        print(f"  penalty    {(id_huff - id_ideal).sum() / n_id:8.3f} bits/id "
              f"({100 * (id_huff - id_ideal).sum() / id_ideal.sum():.2f}%), "
              f"{red:.3f} bits per token over {ntok / n_id:.2f} tokens/id")
        for name, val in (('fit<=64', 64.0), ('fit<=128', 128.0)):
            print(f"  {name}: arithmetic {100 * (id_ideal <= val).mean():.1f}%"
                  f" -> Huffman {100 * (id_huff <= val).mean():.1f}%")
        if args.zero_stop:
            pst = Prow[A, stop]
            saved = float(np.sum(-np.log2(np.maximum(1.0 - pst, 1e-300)))) / n_id
            print(f"\ncodec convention (the stop's own transition is free, "
                  f"{int(keep.sum())} tokens):")
            print(f"  arithmetic {id_ideal_c.sum() / n_id:8.3f} bits/id")
            print(f"  Huffman    {id_huff_c.sum() / n_id:8.3f} bits/id")
            print(f"  penalty    {(id_huff_c - id_ideal_c).sum() / n_id:8.3f} "
                  f"bits/id, {(id_huff_c - id_ideal_c).sum() / keep.sum():.3f} "
                  f"bits/token")
            for name, val in (('fit<=64', 64.0), ('fit<=128', 128.0)):
                print(f"  {name}: arithmetic "
                      f"{100 * (id_ideal_c <= val).mean():.1f}% -> Huffman "
                      f"{100 * (id_huff_c <= val).mean():.1f}%")
            print(f"\nzero-weight stop: longest word code {int(Larr.max())} "
                  f"bits; all-zeros codeword at depth {int(Lzero.max())} "
                  f"(padding bound); renormalisation gives back {saved:.3f} "
                  f"bits/id")
        pen = id_huff - id_ideal
        print(f"  penalty: min {pen.min():.2f}, p50 {np.percentile(pen, 50):.2f}"
              f", p90 {np.percentile(pen, 90):.2f}, max {pen.max():.2f} bits; "
              f"Huffman is *shorter* on {100 * (pen < 0).mean():.1f}% of ids")


if __name__ == '__main__':
    main()
