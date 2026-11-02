#!/usr/bin/env python3
"""Direct compression of the word x word matrix (PLAN C19).

Two questions, both about the largest table of the word model:

1. **Residual sparsity.**  Is `M_ref - (low-rank / marginal) fit` concentrated on
   a few cells?  If so, a "codewords for the probable entries, fit for the rest"
   scheme would be compact.  `--residual` prints the concentration of the raw
   matrix and of the residual after a rank-`L` Hellinger fit.

2. **Compression curve.**  Store the `N` largest observed cells verbatim and
   model the rest with a fallback, then measure the held-out code length as the
   number of stored cells grows (`--max-cells`).  The fallback is either the
   counting prior `M_mar` (`--fallback mar`, the "probable entries + prior"
   scheme) or the `k x k` co-clustered `assoc` table (`--fallback cluster`).

Outcome (see `docs/HELLINGER_FACTORISATION.md`): the residual is *not* sparse,
and the compression is only mild -- within ~1 bit of the full table needs
`N ~ 300K` (~7 % of `V^2`) for `tw2040`.

Usage:
    matrix_compress.py --dir work/tw2040 --residual
    matrix_compress.py --dir work/tw2040 --fallback mar
    matrix_compress.py --dir work/tw2040 --fallback cluster --k 105
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw


def cum_desc(x):
    s = np.sort(x)[::-1]
    c = np.cumsum(s) / s.sum()
    return s, c


def frac_at(c, f):
    """Fraction of cells needed to reach cumulative mass fraction `f`."""
    return (np.searchsorted(c, f) + 1) / len(c)


def residual_report(d, kappa):
    M, uni, chars, rules, sym = hf.dense_matrix(d)
    V = M.shape[0]
    T = float(M.sum())
    _, _, M_ref = hf.priors(M, kappa * V)
    nz = M[M > 0]
    print(f"{d}: V={V}  N={T:.0f}  nonzero={nz.size} "
          f"({100 * nz.size / (V * V):.2f}% of cells)")
    print("\nObserved cells M (nonzero):  mass fraction -> cells")
    s, c = cum_desc(nz)
    for f in (0.25, 0.5, 0.8, 0.9, 0.99):
        fn = frac_at(c, f)
        print(f"  {100 * f:5.1f}% of mass in the top {100 * fn:5.1f}% of "
              f"nonzero cells ({fn * nz.size:8.0f}); = "
              f"{100 * fn * nz.size / (V * V):5.2f}% of V^2")
    print("\nResidual M_ref - rank-L Hellinger fit:"
          "  |rel Fro| and cells holding 90/99/99.9% of |resid|")
    for L in (1, 4, 16, 64, 256):
        Ms = hf.sqrtcnt(M_ref, min(L, V))
        R = np.abs(M_ref - Ms)
        rel = np.linalg.norm(M_ref - Ms) / np.linalg.norm(M_ref)
        _, cf = cum_desc(R.ravel())
        cells = [frac_at(cf, f) * R.size for f in (0.9, 0.99, 0.999)]
        print(f"  L={L:<4d} |{rel:7.4f}|  "
              + " / ".join(f"{x:9.0f}" for x in cells)
              + f"   ({100 * cells[0] / (V * V):5.2f}% of V^2 for 90%)")
    R1 = np.abs(M_ref - np.outer(M_ref.sum(1), M_ref.sum(0)) / M_ref.sum())
    _, c1 = cum_desc(R1.ravel())
    print(f"\nResidual M_ref - rank-1 marginals: |rel Fro| "
          f"{np.linalg.norm(R1) / np.linalg.norm(M_ref):.4f};  cells for "
          "90/99/99.9% of |resid|: "
          + " / ".join(f"{frac_at(c1, f) * R1.size:.0f}" for f in (0.9, 0.99, 0.999)))


def compression_curve(d, kappa, fallback, k, validation, stride, max_cells):
    M, uni, chars, rules, sym = hf.dense_matrix(d)
    V = M.shape[0]
    nchars = len(chars)
    alpha = kappa * V
    _, P_mar, M_ref = hf.priors(M, alpha)
    lines = tw.read_lines(validation, stride=stride)

    if fallback == 'cluster':
        rng = np.random.default_rng(1)
        lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(2)
        rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
        _, fall = cw.models(M_ref, lcl, rcl, k, k)
        print(f"{d}: V={V} fallback=cluster(k={k}, store={k * k + 2 * V})",
              flush=True)
    else:
        fall = alpha * P_mar
        print(f"{d}: V={V} fallback=M_mar (the independence prior)", flush=True)

    b_full = cw.heldout_bits(M_ref, chars, rules, nchars, lines)
    b_fall = cw.heldout_bits(fall, chars, rules, nchars, lines)
    print(f"  full table {b_full:.3f} bits   fallback only {b_fall:.3f} bits",
          flush=True)

    flat = M.ravel()
    order = np.argsort(flat)[::-1]
    nz = int(np.count_nonzero(flat))
    print("\n  N coded   bits   +vs full   (% of V^2)", flush=True)
    for N in max_cells:
        N = min(N, nz)
        coded = np.zeros(V * V, dtype=bool)
        coded[order[:N]] = True
        Mhat = np.where(coded.reshape(V, V), M_ref, fall)
        b = cw.heldout_bits(Mhat, chars, rules, nchars, lines)
        print(f"  {N:7d}  {b:7.3f}  {b - b_full:+8.3f}   "
              f"({100 * N / (V * V):5.2f}%)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw2040')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=20)
    ap.add_argument('--residual', action='store_true')
    ap.add_argument('--fallback', choices=['mar', 'cluster'], default='mar')
    ap.add_argument('--k', type=int, default=105)
    ap.add_argument('--max-cells', default='100,1000,4000,10000,30000,100000,300000,800000')
    args = ap.parse_args()

    if args.residual:
        residual_report(args.dir, args.kappa)
    else:
        cells = [int(x) for x in args.max_cells.split(',')]
        compression_curve(args.dir, args.kappa, args.fallback, args.k,
                          args.validation, args.stride, cells)


if __name__ == '__main__':
    main()
