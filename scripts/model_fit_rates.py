#!/usr/bin/env python3
"""Held-out fit rates for the clustered word model, and the cost of
quantising its stored probabilities to one byte per number.

The clustered (``assoc``) model's transition probability is

    P(b | a) = c[b] * D[lcl(a), rcl(b)] / sum_j D[lcl(a), j] * C[j]

(``C[j]`` = unigram mass of right cluster ``j``), so the only stored numbers
that matter are the unigram ``c`` (``V`` of them) and the cluster-pair table
``D`` (``k^2`` of them); the row marginal cancels, exactly as in
``docs/CLUSTER_WORDS.md``.  The bit length is therefore evaluated straight
from ``(log c, log D, lcl, rcl)`` without ever materialising a ``V x V``
probability matrix.

Reported for each ``(dir, k)``:

* the per-identifier held-out bits of the full table, the raw clustered model
  and the same model with ``c`` and ``D`` quantised onto a one-byte
  logarithmic grid ``P ~ exp(byte/resolution) - 1`` (``--resolution``,
  default 12), the scale inferred per array from its smallest positive entry;
* the **fit rates** -- fraction of held-out identifiers whose ideal code is no
  longer than 64 / 128 bits.

Usage:
    model_fit_rates.py --dir work/tw2040 --ks 26,52,105 --kappa 300 --stride 40
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw


def quantise(x, resolution=12.0, levels=256):
    """One byte per number on a log grid: x ~ exp(b/res) - 1, scale inferred
    from the smallest positive entry.  Exact zeros stay zero."""
    x = np.asarray(x, dtype=np.float64)
    out = np.zeros_like(x)
    pos = x > 0
    if not pos.any():
        return out
    s = x[pos].min()
    b = np.clip(np.round(resolution * np.log1p(x[pos] / s)), 0, levels - 1)
    out[pos] = s * np.expm1(b / resolution)
    return out


def tokenise(lines, chars, rules, nchars):
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tw.make_plan(rules, nchars)
    stop = nchars
    return [tw.tokenize(s, char_id, plan, nchars) + [stop] for s in lines]


def bits_full(seqs, Mref):
    """Full-table bits: P(b|a) = Mref[a,b] / rowsum[a]."""
    rs = Mref.sum(1)
    logm = np.log2(np.maximum(Mref, 1e-300))
    logr = np.log2(np.maximum(rs, 1e-300))
    out = np.empty(len(seqs))
    for j, seq in enumerate(seqs):
        a = np.asarray(seq)
        b = np.roll(a, -1)
        out[j] = float(np.sum(logr[a] - logm[a, b]))
    return out


def bits_assoc(seqs, logc, logD, logden, lcl, rcl):
    """Clustered bits from the stored numbers, no V x V matrix."""
    out = np.empty(len(seqs))
    for j, seq in enumerate(seqs):
        a = np.asarray(seq)
        b = np.roll(a, -1)
        A = lcl[a]
        out[j] = float(np.sum(logden[A] - logc[b] - logD[A, rcl[b]]))
    return out


def stats(bits):
    return (bits.mean(), (bits <= 64).mean() * 100.0,
            (bits <= 128).mean() * 100.0)


def assoc_numbers(Mref, lcl, rcl, k):
    """Return the stored pair (unigram c, cluster-pair table D) of the assoc
    model, using block sums of Mref and of the independent prior."""
    V = Mref.shape[0]
    r = Mref.sum(1)
    c = Mref.sum(0)
    T = float(Mref.sum())
    Rc = np.bincount(lcl, weights=r, minlength=k)
    Cc = np.bincount(rcl, weights=c, minlength=k)
    G = np.zeros((k, V))
    np.add.at(G, lcl, Mref)                       # G[i,:] = sum_{a in i} Mref[a,:]
    S = np.zeros((k, k))
    np.add.at(S, (np.arange(k)[:, None], rcl[None, :]), G)
    Se = np.outer(Rc, Cc) / T                     # block sums of the prior
    D = S / np.maximum(Se, 1e-300)
    return c, D, Cc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', required=True)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=40)
    ap.add_argument('--resolution', type=float, default=12.0)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = M.shape[0]
    nchars = len(chars)
    lines = tw.read_lines(args.validation, stride=args.stride)
    alpha = args.kappa * V
    r0 = M.sum(1)
    c0 = M.sum(0)
    T0 = float(M.sum())
    M += alpha * np.outer(r0 / T0, c0 / T0)
    del r0, c0

    seqs = tokenise(lines, chars, rules, nchars)
    del lines

    bf = bits_full(seqs, M)
    m, f64, f128 = stats(bf)
    print(f"{args.dir}: V={V}, n={len(seqs)}, kappa={args.kappa}, "
          f"resolution={args.resolution}")
    print(f"  {'full table':>10} {'':>8} {m:>8.3f} {'':>7} {f64:>6.1f}% "
          f"{f128:>6.1f}%")
    print(f"  {'k':>5} {'model':>8} {'bits':>8}  {'':>6} {'fit<=64':>8} "
          f"{'fit<=128':>9} {'dBits':>7} {'d64':>6}")

    for k in [int(x) for x in args.ks.split(',')]:
        rng = np.random.default_rng(args.seed)
        lcl, _ = cw.cluster_axis(M, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, _ = cw.cluster_axis(M, k, rng, 1)

        c, D, Cc = assoc_numbers(M, lcl, rcl, k)
        den = D @ Cc
        br = bits_assoc(seqs, np.log2(np.maximum(c, 1e-300)),
                        np.log2(np.maximum(D, 1e-300)),
                        np.log2(np.maximum(den, 1e-300)), lcl, rcl)
        m0, g0, h0 = stats(br)

        cq = quantise(c, args.resolution)
        Dq = quantise(D, args.resolution)
        Ccq = np.bincount(rcl, weights=cq, minlength=k)
        denq = Dq @ Ccq
        bq = bits_assoc(seqs, np.log2(np.maximum(cq, 1e-300)),
                        np.log2(np.maximum(Dq, 1e-300)),
                        np.log2(np.maximum(denq, 1e-300)), lcl, rcl)
        m1, g1, h1 = stats(bq)

        print(f"  {k:>5} {'raw':>8} {m0:>8.3f}  {'':>6} {g0:>7.1f}% "
              f"{h0:>8.1f}% {0.0:>7.3f} {0.0:>6.1f}")
        print(f"  {k:>5} {'quant':>8} {m1:>8.3f}  {'':>6} {g1:>7.1f}% "
              f"{h1:>8.1f}% {m1 - m0:>7.3f} {g1 - g0:>+6.1f}")


if __name__ == '__main__':
    main()
