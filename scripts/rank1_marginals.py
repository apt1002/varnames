#!/usr/bin/env python3
"""Compare the rank-1 SVD of the prefix/suffix adjacency matrix M with the
independence (marginal) model.

The marginal model is the rank-1 *maximum-likelihood* fit:

    M_mar = (r c^T) / T ,  r = M 1,  c = M^T 1,  T = 1^T M 1

i.e. "global distribution over prefixes times global distribution over
suffixes".  The rank-1 *Frobenius* fit is the leading SVD term sigma_1 u_1 v_1^T.
Both give a conditional p(b|a) that is independent of a, but the vectors differ
in general.  This script reports

  * cos(u_1, r/||r||) and cos(v_1, c/||c||)   -- how far the SVD rank-1 is
    from the marginals (1.0 = identical direction),
  * the relative Frobenius error of each rank-1 model,
  * the mean KL(P_emp || p(b|a)) of each as a probability model, showing that
    the objective decides which one wins.

Usage: rank1_marginals.py CORPUS SUBS [--outdir DIR]
"""
import argparse
import os

import numpy as np

import pair_matrix


def _broadcast(Q, n):
    return np.repeat(Q, n, axis=0) if Q.shape[0] == 1 else Q


def kl_rows(P, Q):
    Q = _broadcast(Q, P.shape[0])
    Qn = np.maximum(Q, 1e-12)
    Qn = Qn / Qn.sum(1, keepdims=True)
    tot = P.sum(1)
    m = tot > 0
    kl = (P[m] * (np.log2(np.maximum(P[m], 1e-12)) - np.log2(Qn[m]))).sum(1)
    return float((kl * tot[m]).sum() / tot[m].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common100000')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, vocab, empty_idx = pair_matrix.build_matrix(args.corpus, args.substrings)
    N = len(vocab)
    # work in float32 for the big matrices: at large N the float64 copies of
    # M, its reconstruction and their difference do not fit in memory.
    Mf = M.astype(np.float32)
    fro = float(np.linalg.norm(Mf.astype(np.float64)))
    r = M.sum(1).astype(np.float64)
    c = M.sum(0).astype(np.float64)
    T = float(M.sum())

    # empirical conditional p(b|a)
    rowsum = np.maximum(M.sum(1, keepdims=True), 1).astype(np.float32)
    Pemp = Mf / rowsum

    # --- marginal (independence) model ----------------------------------
    Mmar = (np.outer(r, c) / T).astype(np.float32)
    rel_mar = float(np.linalg.norm(Mf - Mmar)) / fro
    del Mmar
    pmar_row = (c / T)[None, :]                       # p(b|a) = c_b / T

    # --- leading SVD pair -------------------------------------------------
    rng = np.random.default_rng(args.seed)
    U, s, V = pair_matrix.randomized_svd(M, 4, rng)
    u1, v1 = U[:, 0].astype(np.float64), V[0].astype(np.float64)
    if u1.sum() + v1.sum() < 0:                        # make the pair sign-
        u1, v1 = -u1, -v1                              # consistent/non-neg.
    u1 = np.abs(u1) if u1.sum() < 0 else u1
    v1 = np.abs(v1) if v1.sum() < 0 else v1
    Mr1 = (s[0] * np.outer(u1, v1)).astype(np.float32)
    rel_r1 = float(np.linalg.norm(Mf - Mr1)) / fro
    del Mr1
    pr1_row = (np.abs(v1) / np.abs(v1).sum())[None, :]

    ru = r / np.linalg.norm(r)
    cu = c / np.linalg.norm(c)
    cos_u = float(np.dot(u1 / np.linalg.norm(u1), ru))
    cos_v = float(np.dot(v1 / np.linalg.norm(v1), cu))

    print(f"N={N}  ||M||_F={fro:.0f}  T={T:.0f}")
    print(f"  cos(u1, prefix marginal) = {cos_u:.4f}")
    print(f"  cos(v1, suffix marginal) = {cos_v:.4f}")
    print(f"\n{'model':22s} {'Frobenius relerr':>17s} {'mean KL':>9s}")
    for name, rel, P in (("marginal (KL-optimal)", rel_mar, pmar_row),
                         ("SVD rank-1 (LS-optimal)", rel_r1, pr1_row)):
        print(f"{name:22s} {rel:17.4f} {kl_rows(Pemp, P):9.4f}")


if __name__ == '__main__':
    main()
