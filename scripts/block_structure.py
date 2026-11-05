#!/usr/bin/env python3
"""Structure of a high-loss cluster-pair block.

`cluster_loss_attribution.py` attributes the `assoc`-vs-table loss to the
`(left cluster, right cluster)` cells.  This script opens the worst cells and
asks what the model is missing there: inside a cell the model says

    P(v | u) = c[v] / Cc[j]      for every u in the left cluster, v in the
                                 right cluster j

i.e. a **row-independent** shape (each left-word gets the global unigram
restricted to the right cluster).  So the questions are whether the true block
`P(v|u)` is (a) low-rank, and (b) a sparse deviation from that row-independent
marginal -- either would make a per-cell correction cheap to store.

For each cell it reports the block shape and density, the singular-value decay
of the true block, and the concentration of the deviation
`D[u,v] = P(v|u) - c[v]/C[j]`.

Usage:
    block_structure.py --dir work/tw2040 --ks 105 --auto-top 6 --stride 40
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


def rank_report(X, weights=None):
    """Energy captured by the leading ranks (squared singular values)."""
    s = np.linalg.svd(X, compute_uv=False)
    e = s ** 2
    tot = e.sum()
    if tot <= 0:
        return [0.0] * 4
    return [float(e[:r].sum() / tot) for r in (1, 2, 4, 8)]


def _conc(D, fracs):
    ad = np.abs(D).ravel()
    s = ad.sum()
    if s <= 0:
        return [0.0] * len(fracs)
    sd = np.sort(ad)[::-1]
    return [float(sd[:max(1, int(f * ad.size))].sum() / s) for f in fracs]


def analyse(Mraw, Mref, c, Cc, lcl, rcl, i, j, rng,
            top_fracs=(0.01, 0.10)):
    A = np.where(lcl == i)[0]
    B = np.where(rcl == j)[0]
    Bk = Mref[np.ix_(A, B)]
    raw = Mraw[np.ix_(A, B)]
    rs = Bk.sum(1, keepdims=True)
    P = Bk / np.maximum(rs, 1e-300)               # rows: u, cols: v
    marg = c[B] / max(Cc[j], 1e-300)              # the model's row-independent shape
    Dev = P - marg[None, :]
    out = dict(shape=(len(A), len(B)), mass=float(Bk.sum()),
               density=float((raw > 0).mean()),
               nbig=float(raw.sum()),
               rank=rank_report(Bk),
               tv=float(np.abs(Dev).sum(1).mean() / 2.0),
               rowspread=float(np.abs(Dev).mean()))
    out['conc'] = _conc(Dev, top_fracs)
    # permutation null: same block masses, row structure destroyed
    Bn = rng.permutation(Bk.ravel()).reshape(Bk.shape)
    Pn = Bn / np.maximum(Bn.sum(1, keepdims=True), 1e-300)
    out['null_rank'] = rank_report(Bn)
    out['null_conc'] = _conc(Pn - marg[None, :], top_fracs)
    return out, A, B, P, marg, Dev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', required=True)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=40)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--auto-top', type=int, default=6,
                    help='analyse this many worst cells by held-out loss')
    ap.add_argument('--cells', default='',
                    help='explicit cells "L,R;L,R" (overrides --auto-top)')
    args = ap.parse_args()

    Mraw, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = Mraw.shape[0]
    nchars = len(chars)
    lines = tw.read_lines(args.validation, stride=args.stride)
    r0, c0 = Mraw.sum(1), Mraw.sum(0)
    T0 = float(Mraw.sum())
    Mref = Mraw + args.kappa * V * np.outer(r0 / T0, c0 / T0)
    del r0, c0

    seqs = mfr.tokenise(lines, chars, rules, nchars)
    a_all = np.concatenate([np.asarray(s, dtype=np.int64) for s in seqs])
    b_all = np.concatenate([np.roll(np.asarray(s, dtype=np.int64), -1)
                            for s in seqs])
    logm = np.log2(np.maximum(Mref, 1e-300))
    logr = np.log2(np.maximum(Mref.sum(1), 1e-300))
    b_full = logm[a_all, b_all] - logr[a_all]
    print(f"{args.dir}: V={V}, n={len(seqs)} ids, {len(a_all)} bigrams")

    for k in [int(x) for x in args.ks.split(',')]:
        rng = np.random.default_rng(args.seed)
        lcl, _ = cw.cluster_axis(Mref, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, _ = cw.cluster_axis(Mref, k, rng, 1)
        c, D, Cc = mfr.assoc_numbers(Mref, lcl, rcl, k)
        den = D @ Cc
        logc = np.log2(np.maximum(c, 1e-300))
        logD = np.log2(np.maximum(D, 1e-300))
        logden = np.log2(np.maximum(den, 1e-300))
        A_ = lcl[a_all]
        B_ = rcl[b_all]
        loss_t = b_full - (logc[b_all] + logD[A_, B_] - logden[A_])
        L = np.zeros((k, k))
        Ms = np.zeros((k, k))
        np.add.at(L, (A_, B_), loss_t)
        np.add.at(Ms, (A_, B_), 1.0)

        rng = np.random.default_rng(args.seed + 99)
        if args.cells:
            cells = [tuple(int(x) for x in cc.split(','))
                     for cc in args.cells.split(';')]
        else:
            cells = [divmod(int(x), k) for x in np.argsort(-L.ravel())[:args.auto_top]]

        print(f"\n=== k={k} ===")
        print(f"  {'cell':>10} {'|A|x|B|':>11} {'bigrms':>8} {'dens':>6} "
              f"{'tv':>6} {'rank1':>6} {'rank2':>6} {'rank4':>6} {'r8':>6} "
              f"{'dev1%':>7} {'dev10%':>7}")
        for (i, j) in cells:
            o, A, B, P, marg, Dev = analyse(Mraw, Mref, c, Cc, lcl, rcl, i, j, rng)
            print(f"  {i:>4},{j:<5} {o['shape'][0]:>5}x{o['shape'][1]:<5} "
                  f"{int(o['nbig']):>8} {o['density']:>6.2f} {o['tv']:>6.3f} "
                  f"{o['rank'][0]:>6.3f} {o['rank'][1]:>6.3f} "
                  f"{o['rank'][2]:>6.3f} {o['rank'][3]:>6.3f} "
                  f"{o['conc'][0]:>7.3f} {o['conc'][1]:>7.3f} "
                  f"  (loss {L[i, j]:.0f})")
            print(f"  {'':>10} {'null:':>11} {'':>8} {'':>6} {'':>6} "
                  f"{o['null_rank'][0]:>6.3f} {o['null_rank'][1]:>6.3f} "
                  f"{o['null_rank'][2]:>6.3f} {o['null_rank'][3]:>6.3f} "
                  f"{o['null_conc'][0]:>7.3f} {o['null_conc'][1]:>7.3f}")
        # a median-mass cell as a control
        pos = np.argsort(-Ms.ravel())
        med = pos[len(pos) // 2]
        i, j = divmod(int(med), k)
        if (i, j) not in cells and Ms[i, j] > 0:
            o, *_ = analyse(Mraw, Mref, c, Cc, lcl, rcl, i, j, rng)
            print(f"  {i:>4},{j:<5} {o['shape'][0]:>5}x{o['shape'][1]:<5} "
                  f"{int(o['nbig']):>8} {o['density']:>6.2f} {o['tv']:>6.3f} "
                  f"{o['rank'][0]:>6.3f} {o['rank'][1]:>6.3f} "
                  f"{o['rank'][2]:>6.3f} {o['rank'][3]:>6.3f} "
                  f"{o['conc'][0]:>7.3f} {o['conc'][1]:>7.3f}"
                  f"  (median-mass control)")


if __name__ == '__main__':
    main()
