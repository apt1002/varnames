#!/usr/bin/env python3
"""Evaluate ways of turning a low-rank factorisation of the prefix/suffix
adjacency matrix M back into a *probability* model, despite the negative
entries a truncated SVD introduces.

Given M (N x N counts of (longest common suffix, longest common prefix) pairs)
we compare, for a rank-L approximation, several non-negative reconstructions
M_hat, and score each as a *joint* distribution over (prefix, suffix) pairs:

  clip     M_hat = (U s) V^T, replace negative entries by 0
  softmax  M_hat ∝ exp(M_hat[a,b] / tau), calibrated over a small grid of tau
  nmf      non-negative factors W H (multiplicative updates) --
           non-negative by construction, evaluated at its own best rank
  svd-abs  M_hat = |M_hat[a,b]| (uses the factorisation only for ranking)
  sqrtcnt  M_hat = (reconstruction of sqrt(M))[a,b]^2 -- the non-negative
           square-root / Hellinger model (docs/HELLINGER_FACTORISATION.md),
           included as the yardstick the count-space remedies are judged by

Metric: KL(M/T || M_hat/sum M_hat) in bits -- the relative entropy between the
empirical joint and the (normalised) model (see pair_matrix.kl_joint).  No
conditional p(b|a) is formed.

Usage: latent_probabilities.py CORPUS SUBS [--outdir DIR] [--L 16]
"""
import argparse
import os

import numpy as np

import pair_matrix


KL = pair_matrix.kl_joint


def project_simplex_rows(Z, iters=50):
    """Row-wise Euclidean projection of Z onto the probability simplex.

    Duchi et al. (2008) sort-and-threshold, vectorised over rows.
    Guarantees non-negative rows that sum to one: the closest genuine
    probability matrix to the (possibly signed) factorisation.
    """
    Z = np.array(Z, dtype=np.float64)
    n, d = Z.shape
    out = np.empty_like(Z)
    for i in range(n):
        u = np.sort(Z[i])[::-1]
        css = np.cumsum(u) - 1.0
        k = np.arange(1, d + 1)
        cond = u - css / k > 0
        rho = np.nonzero(cond)[0][-1]
        theta = css[rho] / (rho + 1.0)
        out[i] = np.maximum(Z[i] - theta, 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common100000')
    ap.add_argument('--L', type=int, default=16)
    ap.add_argument('--nmf-iters', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    cache = os.path.join(args.outdir, 'M.npz')
    if os.path.exists(cache):
        M = np.load(cache)['M']
    else:
        M, vocab, empty_idx = pair_matrix.build_matrix(args.corpus, args.substrings)
        np.savez_compressed(cache, M=M)
    n = M.shape[0]
    T = float(M.sum())
    r = M.sum(1).astype(np.float64)
    c = M.sum(0).astype(np.float64)
    M_mar = np.outer(r, c) / max(T, 1.0)          # independence model
    nrows = int((M.sum(1) > 0).sum())
    print(f"N={n}  rows with counts: {nrows}  rank L={args.L}\n")

    # Count-space SVD of M (the "coping with negatives" analysis).
    U, s, V = pair_matrix.randomized_svd(M, args.L,
                                         np.random.default_rng(args.seed))
    Mh = (U * s) @ V
    neg = float((Mh < 0).mean())
    print(f"count-space SVD  L={args.L}: negative entries {100*neg:.1f}%  "
          f"rel.err {np.linalg.norm(M - Mh)/np.linalg.norm(M):.4f}")

    # Hellinger / square-root SVD of sqrt(M) -- the recommended model
    # (docs/HELLINGER_FACTORISATION.md).  Squaring the reconstruction back
    # gives a non-negative model, so no remedy is needed.
    Us, ss, Vs = pair_matrix.randomized_svd(np.sqrt(M), args.L,
                                            np.random.default_rng(args.seed))
    Sh = (Us * ss) @ Vs
    print(f"sqrt-space  SVD  L={args.L}: latent negatives "
          f"{100*float((Sh < 0).mean()):.1f}%  (model non-negative by "
          f"construction)")

    rows = [("svd-raw(no floor)", np.maximum(Mh, 1e-12))]
    rows.append(("clip", np.maximum(Mh, 0.0)))
    rows.append(("svd-abs", np.abs(Mh)))
    rows.append(("sqrtcnt (sqrt-SVD)^2", Sh * Sh))
    rows.append(("simplex-proj", project_simplex_rows(Mh)))
    for tau in (0.25, 1.0, 4.0):
        Z = Mh / tau
        Z -= Z.max()
        rows.append((f"softmax tau={tau}", np.exp(Z)))
    # calibrated softmax: temperature scaled to the matrix's own dynamic
    # range, so the exponent is O(1) instead of spanning hundreds of bits.
    for c in (0.5, 2.0, 8.0):
        Z = Mh / (np.abs(Mh).max() / c)
        Z -= Z.max()
        rows.append((f"softmax cal c={c}", np.exp(Z)))
    # mixing with the rank-1 independence model repairs zero rows and
    # guarantees full support while staying inside the latent model.
    for lam in (0.1, 0.3, 0.6):
        rows.append((f"backoff lambda={lam}",
                     (1 - lam) * np.maximum(Mh, 0.0) + lam * M_mar))
    rows.append(("marginal (independence)", M_mar))

    rng = np.random.default_rng(args.seed)
    W, H = pair_matrix.nmf(M, args.L, rng, args.nmf_iters)
    Wh = W @ H
    print(f"NMF  L={args.L}: negative entries {100*float((Wh<0).mean()):.1f}%  "
          f"rel.err {np.linalg.norm(M - Wh)/np.linalg.norm(M):.4f}")
    rows.append(("nmf", Wh))

    print(f"\n{'method':22s} {'KL (bits)':>11s}")
    for name, Q in rows:
        print(f"{name:22s} {KL(M, Q):11.4f}")

    print("\nKL(M/T || M_hat/sum M_hat): no conditional p(b|a) is formed; the "
          "floor is 0 (M itself).")


if __name__ == '__main__':
    main()
