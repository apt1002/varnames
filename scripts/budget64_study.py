#!/usr/bin/env python3
"""The 64-bit and 128-bit identifier sets.

Three questions, for a model that actually fits the byte budget
(`docs/MODEL_BUDGET.md`):

1. **Coverage** -- what fraction of real (held-out) identifiers have an ideal
   code of at most 64 / 128 bits?
2. **The boundary in uncompressed length** -- the longest identifier that still
   fits against the shortest identifier that does not.  Code length is not
   monotone in character length, so the interesting quantity is the overlap:
   how many identifiers shorter than the longest fitting one still fail.
3. **A generative view** -- sample identifiers from the model and look at them:
   length distribution, syntactic validity, and how many are real identifiers.
   A random member of the 64-bit set is a sample from this process.

The transition probability is evaluated from the stored numbers `(c, D)` as in
`model_fit_rates.py`; sampling needs only the `k` distinct left-cluster rows.

Usage:
    budget64_study.py --dir work/tw2040 --ks 52 --kappa 300 --stride 10
"""
import argparse
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import model_fit_rates as mfr

VALID = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def build_model(M, k, seed=1):
    rng = np.random.default_rng(seed)
    lcl, _ = cw.cluster_axis(M, k, rng, 0)
    rng = np.random.default_rng(seed + 1)
    rcl, _ = cw.cluster_axis(M, k, rng, 1)
    c, D, Cc = mfr.assoc_numbers(M, lcl, rcl, k)
    den = D @ Cc
    return dict(lcl=lcl, rcl=rcl, c=c, D=D, Cc=Cc, den=den, k=k,
                logc=np.log2(np.maximum(c, 1e-300)),
                logD=np.log2(np.maximum(D, 1e-300)),
                logden=np.log2(np.maximum(den, 1e-300)))


def sample(m, stop, n, rng):
    """Sample identifiers from the model: a cycle starting and ending at the
    stop token.  Returns a list of token sequences."""
    c, D, den, lcl, rcl = m['c'], m['D'], m['den'], m['lcl'], m['rcl']
    Prow = (c[None, :] * D[:, rcl]) / np.maximum(den[:, None], 1e-300)
    Prow = Prow / Prow.sum(1, keepdims=True)
    cum = np.cumsum(Prow, axis=1)
    out = []
    for _ in range(n):
        seq = []
        cur = int(np.searchsorted(cum[lcl[stop]], rng.random()))
        for _ in range(200):
            if cur == stop:
                break
            seq.append(cur)
            cur = int(np.searchsorted(cum[lcl[cur]], rng.random()))
        out.append(seq)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', required=True)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--reference', default='work/camel/merged_validation.txt',
                    help='the set of "real" identifiers used to test generated '
                         'ones (defaults to the whole validation corpus)')
    ap.add_argument('--stride', type=int, default=10)
    ap.add_argument('--sample-n', type=int, default=50000)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = M.shape[0]
    nchars = len(chars)
    stop = nchars
    lines = tw.read_lines(args.validation, stride=args.stride)
    alpha = args.kappa * V
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = alpha * c0 / T0
    for i0 in range(0, V, 512):                  # row-blocked, no V x V temp
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del r0, c0, cb

    seqs = mfr.tokenise(lines, chars, rules, nchars)
    lens = np.array([len(s) for s in lines])
    corpus = set(tw.read_lines(args.reference))
    print(f"{args.dir}: V={V}, n={len(seqs)}, stride={args.stride}, "
          f"kappa={args.kappa}")

    # reference: the full table
    bf = mfr.bits_full(seqs, M)
    lf = lens[bf <= 64]
    print(f"\n[full table] mean {bf.mean():.3f} bits  "
          f"fit<=64 {100 * (bf <= 64).mean():.1f}%  "
          f"fit<=128 {100 * (bf <= 128).mean():.1f}%")

    for k in [int(x) for x in args.ks.split(',')]:
        m = build_model(M, k, args.seed)
        bits = mfr.bits_assoc(seqs, m['logc'], m['logD'], m['logden'],
                              m['lcl'], m['rcl'])
        fit = bits <= 64
        print(f"\n=== V={V}, k={k} ===")
        print(f"mean {bits.mean():.3f} bits  fit<=64 {100 * fit.mean():.1f}%  "
              f"fit<=128 {100 * (bits <= 128).mean():.1f}%")

        # --- boundary in uncompressed length -------------------------------
        maxfit = int(lens[fit].max())
        if (~fit).any():
            minfail = int(lens[~fit].min())
            short_fail = int(np.sum(~fit & (lens < maxfit)))
            print(f"boundary: longest fitting = {maxfit} chars; "
                  f"shortest failing = {minfail} chars; "
                  f"{short_fail} fail at <{maxfit} chars")
        print(f"  {'len':>4} {'n':>7} {'fit<=64':>8}  "
              f"{'len':>4} {'n':>7} {'fit<=64':>8}")
        tbl = []
        for L in range(1, int(lens.max()) + 1):
            s = lens == L
            if s.any():
                tbl.append((L, int(s.sum()), 100.0 * fit[s].mean()))
        half = (len(tbl) + 1) // 2
        for i in range(half):
            a = tbl[i]
            b = tbl[i + half] if i + half < len(tbl) else (None, None, None)
            left = f"  {a[0]:>4} {a[1]:>7} {a[2]:>7.1f}%"
            right = ("" if b[0] is None
                     else f"  {b[0]:>4} {b[1]:>7} {b[2]:>7.1f}%")
            print(left + right)

        # --- generative view ----------------------------------------------
        rng = np.random.default_rng(args.seed + 7)
        gen = sample(m, stop, args.sample_n, rng)
        gstr = [''.join(sym[t] for t in seq) for seq in gen]
        glen = np.array([len(s) for s in gstr])
        valid = np.array([bool(VALID.match(s)) for s in gstr])
        real = np.array([s in corpus for s in gstr])
        gbits = mfr.bits_assoc(gen, m['logc'], m['logD'], m['logden'],
                               m['lcl'], m['rcl'])
        print(f"generated {len(gstr)}: mean len {glen.mean():.2f} "
              f"(corpus {lens.mean():.2f}), valid syntax "
              f"{100 * valid.mean():.1f}%, in the reference set "
              f"{100 * real.mean():.2f}%")
        print(f"  generated: mean {gbits.mean():.3f} bits  "
              f"fit<=64 {100 * (gbits <= 64).mean():.1f}%  "
              f"fit<=128 {100 * (gbits <= 128).mean():.1f}%")
        print("  examples:", ', '.join(gstr[:12]))


if __name__ == '__main__':
    main()
