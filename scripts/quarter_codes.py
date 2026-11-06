#!/usr/bin/env python3
"""Cluster quarters, step 4: build the three codes and score them held-out.

`quarter_accounting.py` prices the layouts as Huffman costs on the *training*
counts, which is optimistic and carries no fit rate.  This script does the two
things the decision rule actually needs:

* it **builds** the codes (flat / CF / CQF(q)) from the training counts, so the
  bits are code lengths rather than an entropy estimate, and
* it **scores them on held-out identifiers** from `merged_validation.txt`,
  reporting mean bits and the fit <=64 / <=128 rates that the product cares
  about, next to the model bytes each layout costs.

Per held-out identifier the cost is the sum over its `m + 1` cyclic transitions
(`stop -> t0`, the `m - 1` interior ones, `t_last -> stop`):

    flat   len_flat[lcl[u], v]                           one k x V table
    CF     len_top[lcl[u], rcl[v]] + len_word[rcl[v], v]
    CQF    len_top[lcl[u], q(v)]   + len_quarter[v, v]   q survivors per cluster
    ref    -log2 P_ref(v | u)                            a full V x V table

`ref` is the arithmetic yardstick: the cheapest any per-transition code can be
given exact conditional probabilities, and it costs `V log V + V (V - 1)` bits
of model, i.e. it is not shippable.  Flat is the yardstick for the *codes*: it
is the best a Huffman code can do at this vocabulary, at `k * V` lengths.

The truncation is the only grouping: quarters are whatever the build leaves when
it halts, so there is no partition to choose.

Usage:
    quarter_codes.py --dir work/tw512ns --k 16 --qs 2,4 --kappa 300 --stride 100
    quarter_codes.py --dir work/tw4096ns --k 32 --qs 2,4 --stride 100
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import model_fit_rates as mfr
from quarter_accounting import huffman


def reference_matrix(M, alpha, block=512):
    """``M_ref = M + alpha (r/T)(c/T)^T`` in place, row-blocked.

    ``hf.priors`` is the readable version but materialises three `V x V`
    temporaries -- 400 MB at `V = 4096`, which is most of this machine's RAM.
    This is the same arithmetic as `quarter_accounting.py`.
    """
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = alpha * c0 / T0
    for i0 in range(0, M.shape[0], block):
        M[i0:i0 + block] += np.outer(r0[i0:i0 + block] / T0, cb)
    return M


def build_flat(G, k, V):
    """One Huffman tree per left cluster over all `V` words (`k x V` lengths)."""
    lens = np.zeros((k, V))
    tree_bits = 0.0
    for L in range(k):
        l, _, _ = huffman(G[L])
        lens[L] = l
        tree_bits += 2 * (V - 1)
    return lens, tree_bits


def build_cf(G, Gc, c, rcl, k, V):
    """Cluster step (per left cluster, `k` leaves) + word step (per right cluster)."""
    top = np.zeros((k, k))
    for L in range(k):
        l, _, _ = huffman(Gc[L])
        top[L] = l
    bot = np.zeros(V)
    for j in range(k):
        w = np.flatnonzero(rcl == j)
        l, _, _ = huffman(c[w])
        bot[w] = l
    return top, bot


def build_cqf(M_ref, c, rcl, lcl, k, V, q):
    """Truncate each right-cluster tree at `q` survivors, then code those."""
    ql = np.empty(V, dtype=np.int64)
    bot = np.zeros(V)
    avoided = 0.0
    for j in range(k):
        w = np.flatnonzero(rcl == j)
        lens, cost_trunc, groups = huffman(c[w], stop_at=q)
        _, cost_full, _ = huffman(c[w])
        avoided += cost_full - cost_trunc
        for gi, g in enumerate(groups):
            ql[w[g]] = j * q + gi
        bot[w] = lens
    kq = k * q
    S = np.zeros((k, kq))
    for a in range(V):
        S[lcl[a]] += np.bincount(ql, weights=M_ref[a], minlength=kq)
    top = np.zeros((k, kq))
    for L in range(k):
        l, _, _ = huffman(S[L])
        top[L] = l
    return top, bot, ql, avoided


def score(seqs, codes, M_ref, rowsum):
    """Per-identifier bits for every scheme.

    A held-out sequence is `[t0, ..., tn, stop]`; the transitions are the pairs
    `(a, roll(a, -1))`, so the identifier's `m` tokens cost `m + 1` transitions
    and the `stop -> t0` one is the wrap -- the same convention as
    `model_fit_rates.bits_assoc`, which keeps these bits comparable to the
    assoc numbers in NEWLINE_CLUSTER.md."""
    m = len(seqs)
    names = (['flat', 'CF'] + ['CQF q=%d' % q for q in codes['cqf']]
             + ['ref'])
    out = {name: np.zeros(m) for name in names}
    lcl, rcl = codes['lcl'], codes['rcl']
    for i, toks in enumerate(seqs):
        u = np.asarray(toks, dtype=np.int64)
        v = np.roll(u, -1)
        out['flat'][i] = codes['flat'][lcl[u], v].sum()
        out['CF'][i] = (codes['CF_top'][lcl[u], rcl[v]].sum()
                        + codes['CF_bot'][v].sum())
        for q, (top, bot, ql) in codes['cqf'].items():
            out['CQF q=%d' % q][i] = (top[lcl[u], ql[v]].sum() + bot[v].sum())
        out['ref'][i] = float(-np.log2(M_ref[u, v] / rowsum[u]).sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--k', type=int, default=16)
    ap.add_argument('--qs', default='2,4')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=100)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V, nchars = M.shape[0], len(chars)
    stop = nchars
    alpha = args.kappa * V
    M_ref = reference_matrix(M, alpha)
    del M, uni
    N = float(M_ref[:, stop].sum())
    c = M_ref.sum(0)
    rowsum = M_ref.sum(1)
    k = args.k

    rng = np.random.default_rng(args.seed)
    lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
    rng = np.random.default_rng(args.seed + 1)
    rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)

    lines = tw.read_lines(args.validation, stride=args.stride)
    seqs = mfr.tokenise(lines, chars, rules, nchars)
    del lines

    # ---- the counts the codes are built from --------------------------------
    G = np.zeros((k, V))
    np.add.at(G, lcl, M_ref)
    Gc = np.zeros((k, k))
    for j in range(k):
        Gc[:, j] = G[:, rcl == j].sum(1)

    codes = {'lcl': lcl, 'rcl': rcl, 'cqf': {}}
    codes['flat'], flat_tree_bits = build_flat(G, k, V)
    codes['CF_top'], codes['CF_bot'] = build_cf(G, Gc, c, rcl, k, V)
    qs = [int(x) for x in args.qs.split(',')]
    avoided = {}
    for q in qs:
        top, bot, ql, av = build_cqf(M_ref, c, rcl, lcl, k, V, q)
        codes['cqf'][q] = (top, bot, ql)
        avoided[q] = av
    del G, Gc

    bits = score(seqs, codes, M_ref, rowsum)

    # ---- model bytes, ENCODING.md section 5 --------------------------------
    def bytes_for(kk):
        return (kk * (2 * (kk - 1) + kk * np.log2(kk))
                + (2 * (V - kk) + V * np.log2(V))) / 8.0

    vb = bytes_for(k)
    vw = k * (2 * (V - 1) + V * np.log2(V)) / 8.0
    ref_bytes = (V * (V - 1) + V * np.log2(V)) / 8.0

    print(f"{args.dir}: V={V}, k={k}, kappa={args.kappa}, "
          f"held-out n={len(seqs)} (stride {args.stride}), "
          f"mean length {np.mean([len(s) for s in seqs]) - 1:.2f} tokens")
    print(f"codes built on {N:.0f} training identifiers, "
          f"{M_ref.sum():.0f} transitions")
    print(f"{'scheme':<16} {'bits/id':>8} {'vs flat':>8} {'fit<=64':>8} "
          f"{'fit<=128':>9} {'bytes':>9}")

    order = ['flat', 'CF'] + ['CQF q=%d' % q for q in qs] + ['ref']
    base = bits['flat'].mean()
    rows = {}
    for name in order:
        b = bits[name]
        if name == 'flat':
            by = vw
        elif name == 'CF':
            by = vb
        elif name.startswith('CQF'):
            q = int(name.split('=')[1])
            by = bytes_for(k * q)
        else:
            by = ref_bytes
        rows[name] = (b.mean(), (b <= 64).mean(), (b <= 128).mean(), by,
                      b.std() / np.sqrt(len(b)))
        print(f"{name:<16} {b.mean():>8.3f} {b.mean() - base:>+8.3f} "
              f"{100 * (b <= 64).mean():>7.1f}% {100 * (b <= 128).mean():>8.1f}% "
              f"{by:>9.0f}")

    cf_mean = rows['CF'][0]
    pen = cf_mean - base
    print()
    for q in qs:
        name = 'CQF q=%d' % q
        gain = cf_mean - rows[name][0]
        av = avoided[q] / N
        print(f"{name}: {gain:.3f} of the {pen:.3f}-bit flat->CF penalty "
              f"recovered ({100 * gain / pen:.0f}%), fit<=64 "
              f"{100 * rows[name][1]:.1f}% vs CF {100 * rows['CF'][1]:.1f}%, "
              f"+{rows[name][3] - vb:.0f} B")
        print(f"  training-count accounting said the merges avoided are "
              f"{av:.3f} bits/id; held-out recovers {gain:+.3f}")
    print(f"flat is a yardstick: {k} trees of {V} leaves, {vw:.0f} B")
    print(f"ref is the arithmetic bound at exact P(v|u), {ref_bytes:.0f} B")


if __name__ == '__main__':
    main()
