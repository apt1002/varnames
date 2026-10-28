#!/usr/bin/env python3
"""Evaluate ways of turning a low-rank factorisation of the prefix/suffix
adjacency matrix M back into a *probability* model, despite the negative
entries a truncated SVD introduces.

Given M (N x N counts of (longest common suffix, longest common prefix) pairs)
we compare, for a rank-L approximation, three ways of producing
p(b | a), and score each against the row-normalised empirical distribution:

  clip     M_hat = (U s) V^T, replace negative entries by 0, renormalise rows
  softmax  p(b|a) ∝ exp(M_hat[a,b] / tau), calibrated over a small grid of tau
  nmf      non-negative factors W H (multiplicative updates) renormalised --
           non-negative by construction, evaluated at its own best rank
  svd-abs  p(b|a) ∝ |M_hat[a,b]| (uses the factorisation only for ranking)
  hell     p(b|a) ∝ (reconstruction of sqrt(M))[a,b]^2 -- the non-negative
           square-root / Hellinger model (docs/HELLINGER_FACTORISATION.md),
           included as the yardstick the count-space remedies are judged by

Metrics over the rows that occur in the corpus: mean KL(P_emp || P_pred)
(bits).  Only rows with a positive empirical count are scored.

Usage: latent_probabilities.py CORPUS SUBS [--outdir DIR] [--L 16]
"""
import argparse
import os

import numpy as np

import pair_matrix


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def kl_rows(P, Q, w=None):
    """Mean KL(P_row || Q_row), in bits.

    P is the row-normalised empirical conditional (unit row sums), so the
    occurrence weight cannot be read off P -- pass the raw row counts as w for
    the occurrence-weighted mean.  With w=None the mean is uniform over rows
    that occur.  (This function previously multiplied by P.sum(1), which is 1
    for every live row, so it silently returned the uniform mean.)
    """
    Qn = np.maximum(Q, 1e-12)
    Qn = Qn / Qn.sum(1, keepdims=True)
    live = P.sum(1) > 0
    kl = (P * (np.log2(np.maximum(P, 1e-12)) - np.log2(Qn))).sum(1)
    if w is None:
        return float(kl[live].mean())
    w = np.asarray(w, dtype=np.float64)
    m = live & (w > 0)
    return float((kl[m] * w[m]).sum() / w[m].sum())


def row_entropy(P):
    """Occurrence-weighted mean row entropy H(p(b|a)) in bits."""
    tot = P.sum(1)
    m = tot > 0
    h = np.array([entropy_bits(r) for r in P[m]])
    return float((h * tot[m]).sum() / tot[m].sum())


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
    P = M.astype(np.float64)
    P = P / np.maximum(P.sum(1, keepdims=True), 1)
    Nw = M.sum(1).astype(np.float64)
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
    Sn = Sh * Sh
    hell = Sn / np.maximum(Sn.sum(1, keepdims=True), 1e-300)
    print(f"sqrt-space  SVD  L={args.L}: latent negatives "
          f"{100*float((Sh < 0).mean()):.1f}%  (model non-negative by "
          f"construction)")

    rows = [("svd-raw(no floor)", np.maximum(Mh, 1e-12))]
    rows.append(("clip", np.maximum(Mh, 0.0)))
    rows.append(("svd-abs", np.abs(Mh)))
    rows.append(("hell (sqrt-SVD)^2", hell))
    rows.append(("simplex-proj", project_simplex_rows(Mh)))
    for tau in (0.25, 1.0, 4.0):
        Z = Mh / tau
        Z -= Z.max(1, keepdims=True)
        rows.append((f"softmax tau={tau}", np.exp(Z)))
    # calibrated softmax: per-row temperature scaled to the row's own dynamic
    # range, so the exponent is O(1) instead of spanning hundreds of bits.
    rowscale = np.maximum(np.abs(Mh).max(1, keepdims=True), 1e-12)
    for c in (0.5, 2.0, 8.0):
        Z = Mh / (rowscale / c)
        Z -= Z.max(1, keepdims=True)
        rows.append((f"softmax cal c={c}", np.exp(Z)))
    # marginal q_b, which is strictly positive -> repairs zero rows and
    # guarantees full support while staying inside the latent model.
    qb = M.sum(0).astype(np.float64)
    qb = np.maximum(qb / max(qb.sum(), 1.0), 1e-12)
    for lam in (0.1, 0.3, 0.6):
        base = np.maximum(Mh, 0.0)
        base = base / np.maximum(base.sum(1, keepdims=True), 1e-12)
        rows.append((f"backoff lambda={lam}", (1 - lam) * base + lam * qb))

    rng = np.random.default_rng(args.seed)
    W, H = pair_matrix.nmf(M, args.L, rng, args.nmf_iters)
    Wh = W @ H
    print(f"NMF  L={args.L}: negative entries {100*float((Wh<0).mean()):.1f}%  "
          f"rel.err {np.linalg.norm(M - Wh)/np.linalg.norm(M):.4f}")
    rows.append(("nmf", Wh))

    print(f"\n{'method':22s} {'KL occ-wtd':>11s} {'KL uniform':>11s}")
    for name, Q in rows:
        print(f"{name:22s} {kl_rows(P, Q, Nw):11.4f} {kl_rows(P, Q):11.4f}")

    print(f"\nempirical row entropy H(p(b|a)) = {row_entropy(P):.4f} bits "
          f"(the KL floor: no factorisation can go below 0 KL, but a "
          f"model with KL > this is worse than uniform)")


if __name__ == '__main__':
    main()
