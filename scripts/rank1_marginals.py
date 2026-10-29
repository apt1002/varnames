#!/usr/bin/env python3
"""Compare the rank-1 SVD of the prefix/suffix adjacency matrix M with the
independence (marginal) model.

The marginal model is the rank-1 *maximum-likelihood* fit:

    M_mar = (r c^T) / T ,  r = M 1,  c = M^T 1,  T = 1^T M 1

i.e. "global distribution over prefixes times global distribution over
suffixes".  The rank-1 *Frobenius* fit is the leading SVD term sigma_1 u_1 v_1^T.
Both give a model that is (in conditional terms) independent of a, but the
vectors differ in general.  This script reports

  * cos(u_1, r/||r||) and cos(v_1, c/||c||)   -- how far the SVD rank-1 is
    from the marginals (1.0 = identical direction),
  * the relative Frobenius error of each rank-1 model,
  * the joint KL(M/T || M_hat/sum M_hat) of each as a probability model,
    showing that the objective decides which one wins.

Usage: rank1_marginals.py CORPUS SUBS [--outdir DIR]
"""
import argparse

import numpy as np

import pair_matrix_lib as pair_matrix

KL = pair_matrix.kl_joint


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common100000')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M = pair_matrix.load_or_build_matrix(args.corpus, args.substrings, args.outdir)
    N = M.shape[0]
    # work in float32 for the big matrices: at large N the float64 copies of
    # M, its reconstruction and their difference do not fit in memory.
    Mf = M.astype(np.float32)
    fro = float(np.linalg.norm(Mf.astype(np.float64)))
    r = M.sum(1).astype(np.float64)
    c = M.sum(0).astype(np.float64)
    T = float(M.sum())

    # --- marginal (independence) model ----------------------------------
    Mmar = (np.outer(r, c) / T).astype(np.float32)
    rel_mar = float(np.linalg.norm(Mf - Mmar)) / fro
    kl_mar = KL(Mf, Mmar)

    # --- leading SVD pair -------------------------------------------------
    rng = np.random.default_rng(args.seed)
    U, s, V = pair_matrix.randomized_svd(M, 4, rng)
    u1, v1 = U[:, 0].astype(np.float64), V[0].astype(np.float64)
    if u1.sum() + v1.sum() < 0:                        # make the pair sign-
        u1, v1 = -u1, -v1                              # consistent/non-neg.
    u1 = np.abs(u1) if u1.sum() < 0 else u1
    v1 = np.abs(v1) if v1.sum() < 0 else v1
    Mr1 = (s[0] * np.outer(np.abs(u1), np.abs(v1))).astype(np.float32)
    rel_r1 = float(np.linalg.norm(Mf - Mr1)) / fro
    kl_r1 = KL(Mf, Mr1)

    ru = r / np.linalg.norm(r)
    cu = c / np.linalg.norm(c)
    cos_u = float(np.dot(u1 / np.linalg.norm(u1), ru))
    cos_v = float(np.dot(v1 / np.linalg.norm(v1), cu))

    print(f"N={N}  ||M||_F={fro:.0f}  T={T:.0f}")
    print(f"  cos(u1, prefix marginal) = {cos_u:.4f}")
    print(f"  cos(v1, suffix marginal) = {cos_v:.4f}")
    print(f"\n{'model':22s} {'Frobenius relerr':>17s} {'KL (bits)':>11s}")
    for name, rel, kl in (("marginal (KL-optimal)", rel_mar, kl_mar),
                          ("SVD rank-1 (LS-optimal)", rel_r1, kl_r1)):
        print(f"{name:22s} {rel:17.4f} {kl:11.4f}")


if __name__ == '__main__':
    main()
