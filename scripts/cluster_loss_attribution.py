#!/usr/bin/env python3
"""Where the co-clustering loss lives.

The `assoc` model replaces the word x word matrix by a `k x k` table `D`: every
word in a left cluster gets the same distribution over right clusters, and the
word within the right cluster is drawn from that cluster's own marginal
(`docs/CLUSTER_WORDS.md`).  The cost of that constraint is

    loss(a->b) = log2 P_full(b|a) - log2 P_assoc(b|a) >= 0

per observed word bigram.  This script attributes the total held-out loss to
each `(left cluster, right cluster)` cell -- the storage unit the constraint
actually acts on -- and asks whether it is concentrated in the high-mass cells,
spread over the tail, or parked in the small ("junk") clusters.

Usage:
    cluster_loss_attribution.py --dir work/tw2040 --ks 52 --stride 40
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', required=True)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=40)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--top', type=int, default=15)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V = M.shape[0]
    nchars = len(chars)
    lines = tw.read_lines(args.validation, stride=args.stride)
    alpha = args.kappa * V
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = alpha * c0 / T0
    for i0 in range(0, V, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del r0, c0, cb

    seqs = mfr.tokenise(lines, chars, rules, nchars)
    a_all = np.concatenate([np.asarray(s, dtype=np.int64) for s in seqs])
    b_all = np.concatenate([np.roll(np.asarray(s, dtype=np.int64), -1)
                            for s in seqs])
    n_id = len(seqs)
    print(f"{args.dir}: V={V}, n={n_id} ids, {len(a_all)} bigrams, "
          f"kappa={args.kappa}, stride={args.stride}")

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

        A = lcl[a_all]
        B = rcl[b_all]
        loss_t = (b_full - (logc[b_all] + logD[A, B] - logden[A]))
        b_assoc = logc[b_all] + logD[A, B] - logden[A]

        print(f"\n=== k={k} ===")
        pos = loss_t[loss_t > 0].sum() / n_id
        neg = loss_t[loss_t < 0].sum() / n_id
        print(f"full {(-b_full).sum() / n_id:.3f} bits/id, "
              f"assoc {(-b_assoc).sum() / n_id:.3f} bits/id, "
              f"net loss {loss_t.sum() / n_id:.3f} bits/id")
        print(f"  gross: +{pos:.3f} bits/id on "
              f"{100 * (loss_t > 0).mean():.1f}% of bigrams, "
              f"{neg:.3f} bits/id on {100 * (loss_t < 0).mean():.1f}% "
              f"(the model *beats* the table where it pools a sparse row)")

        L = np.zeros((k, k))
        Ms = np.zeros((k, k))
        np.add.at(L, (A, B), loss_t)
        np.add.at(Ms, (A, B), 1.0)

        tot = L.sum()
        flat_mass = Ms.ravel()
        flat_loss = L.ravel()
        ord_mass = np.argsort(-flat_mass)
        cum_m = np.cumsum(flat_mass[ord_mass]) / flat_mass.sum()
        cum_l = np.cumsum(flat_loss[ord_mass]) / tot
        print(f"  cells used: {int((flat_mass > 0).sum())} of {k * k}")
        for frac in (0.01, 0.05, 0.10, 0.25, 0.50):
            n_cells = max(1, int(round(frac * k * k)))
            print(f"  top {100 * frac:4.0f}% of cells by mass carry "
                  f"{100 * cum_l[n_cells - 1]:5.1f}% of the loss "
                  f"(mass {100 * cum_m[n_cells - 1]:5.1f}%)")
        ord_loss = np.argsort(-flat_loss)
        cum_l2 = np.cumsum(flat_loss[ord_loss]) / tot
        for frac in (0.01, 0.10, 0.50):
            n_cells = max(1, int(round(frac * k * k)))
            print(f"  top {100 * frac:4.0f}% of cells by loss carry "
                  f"{100 * cum_l2[n_cells - 1]:5.1f}% of the loss "
                  f"(mass {100 * flat_mass[ord_loss][:n_cells].sum() / flat_mass.sum():5.1f}%)")

        # loss per bigram by mass decile
        print(f"  {'mass decile':>12} {'cells':>6} {'bigrams':>10} "
              f"{'loss share':>11} {'loss/bigram':>12}")
        pos = flat_mass > 0
        idx = np.argsort(-flat_mass[pos])
        mm = flat_mass[pos][idx]
        ll = flat_loss[pos][idx]
        ch = np.array_split(np.arange(len(idx)), 10)
        for d, part in enumerate(ch):
            print(f"  {d + 1:>12} {len(part):>6} {int(mm[part].sum()):>10} "
                  f"{100 * ll[part].sum() / tot:>10.1f}% "
                  f"{ll[part].sum() / mm[part].sum():>12.3f}")

        # cluster sizes: is the loss parked in small clusters?
        nl = np.bincount(lcl, minlength=k)
        nr = np.bincount(rcl, minlength=k)
        row_mass = Ms.sum(1)
        row_loss = L.sum(1)
        ord_r = np.argsort(row_mass)
        print(f"  smallest 5 left clusters (size, bigrams, loss share): " +
              ', '.join(f"({nl[i]},{int(row_mass[i])},{100 * row_loss[i] / tot:.1f}%)"
                        for i in ord_r[:5]))
        print(f"  largest 5 left clusters  (size, bigrams, loss share): " +
              ', '.join(f"({nl[i]},{int(row_mass[i])},{100 * row_loss[i] / tot:.1f}%)"
                        for i in ord_r[-5:][::-1]))
        print(f"  right-cluster sizes: min {nr.min()}, median "
              f"{int(np.median(nr))}, max {nr.max()}")

        # top cells by loss
        print(f"  top {args.top} cells by loss:")
        print(f"    {'L':>4} {'R':>4} {'|L|':>4} {'|R|':>4} {'bigrams':>8} "
              f"{'loss':>9} {'loss/bigr':>10} {'D':>10}")
        for i in np.argsort(-flat_loss)[:args.top]:
            li, ri = divmod(int(i), k)
            print(f"    {li:>4} {ri:>4} {nl[li]:>4} {nr[ri]:>4} "
                  f"{int(Ms[li, ri]):>8} {L[li, ri]:>9.1f} "
                  f"{L[li, ri] / max(Ms[li, ri], 1):>10.3f} {D[li, ri]:>10.3f}")


if __name__ == '__main__':
    main()
