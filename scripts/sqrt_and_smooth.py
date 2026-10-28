#!/usr/bin/env python3
"""Exploring a better low-rank prefix/suffix model: square-root (Hellinger)
factorisation, and smoothing towards the independence model.

Idea 1 -- Hellinger factorisation
---------------------------------
A truncated SVD minimises squared L2 error, but the model is scored by KL.  For
probability vectors the sqrt map is an isometry,

    ||sqrt(p) - sqrt(q)||^2 = 2 H^2(p, q)  ~  2 KL(p || q)   for p ~ q,

so we factorise the Hellinger embeddings sqrt(P) (P = row-normalised M) rather
than M, and square the reconstruction back:

    p_hat(b|a)  ∝  x_hat[a,b]^2 ,   x_hat = (U Sigma V^T)_L .

The square is non-negative however signed x_hat is, so the *model* never has
negative probabilities -- the negatives stay in the latent scores, where they
only affect the Hellinger-space fit.  Variants:

    hell    SVD of sqrt(P)
    hellw   SVD of diag(sqrt(N_a)) sqrt(P) then divide by sqrt(N_a); the exact
            minimiser of the occurrence-weighted sum_a N_a ||x_a - xhat_a||^2
    hellbk  hell mixed with the column marginal, (1-lam) p_hat + lam q_b
    sqrtcnt the count-scale analogue: SVD of sqrt(M) elementwise, squared back

Idea 2 -- smoothing towards independence
----------------------------------------
M counts only observed (a, b) pairs; a structural zero is not an impossibility.
Add alpha * M_mar = alpha * r c^T / T before factorising (rank 1 and
non-negative, so it lifts the floor without adding much rank).

Scored as in latent_probabilities.py: occurrence-weighted mean
KL(P_emp || p_hat) in bits over rows with a positive count, plus the negative
fraction of the latent reconstruction (the model itself is non-negative for the
sqrt variants).

Usage: sqrt_and_smooth.py CORPUS --outdirs work/common100000,... [--ls 8,16,32]
       [--alphas 0,0.01,0.05,0.2,1.0] [--exact]
"""
import argparse
import os

import numpy as np

import pair_matrix


def rownorm(X):
    s = X.sum(1, keepdims=True)
    return X / np.maximum(s, 1e-300)


def kl_rows(P, Q, w=None):
    """Mean KL(P_row || Q_row) in bits, weighted by w (default uniform).

    P must be row-normalised (it is the empirical conditional p(b|a)); pass the
    *raw* row counts as w to get the occurrence-weighted mean (a row-normalised
    P has unit row sums, so the weights cannot be recovered from P itself).
    """
    Qn = np.maximum(Q, 1e-12)
    Qn = Qn / Qn.sum(1, keepdims=True)
    kl = (P * (np.log2(np.maximum(P, 1e-12)) - np.log2(Qn))).sum(1)
    live = P.sum(1) > 0
    if w is None:
        return float(kl[live].mean())
    w = np.asarray(w, dtype=np.float64)
    m = live & (w > 0)
    return float((kl[m] * w[m]).sum() / w[m].sum())


def sq(M):
    return np.sqrt(np.maximum(M, 0.0))


def lowrank(M, L, rng, exact):
    if exact:
        U, s, Vt = np.linalg.svd(np.asarray(M, dtype=np.float64),
                                 full_matrices=False)
        return U[:, :L], s[:L], Vt[:L]
    return pair_matrix.randomized_svd(M, L, rng)


METHODS = ('clip', 'abs', 'backoff .1', 'nmf', 'sqrtcnt', 'hell', 'hellw',
           'hellbk')


def models_for(M, L, alpha, rng, exact, nmf_iters):
    """Return (name -> model matrix p_hat, name -> latent negative fraction)."""
    n = M.shape[0]
    r = M.sum(1)
    c = M.sum(0)
    T = float(M.sum())
    M_mar = np.outer(r, c) / max(T, 1.0)
    Ns = r.copy()
    qb = c / max(c.sum(), 1.0)
    wsqrt = np.maximum(np.sqrt(Ns), 1e-12)[:, None]

    Ma = M.astype(np.float64) + alpha * M_mar
    out, neg = {}, {}

    U, s, V = lowrank(Ma, L, rng, exact)
    Mh = (U * s) @ V
    out['clip'] = rownorm(np.maximum(Mh, 0.0))
    out['abs'] = rownorm(np.abs(Mh))
    out['backoff .1'] = rownorm(0.9 * rownorm(np.maximum(Mh, 0.0)) + 0.1 * qb)
    neg['clip'] = neg['abs'] = neg['backoff .1'] = float((Mh < 0).mean())

    Sh = (lambda US, ss, VV: (US * ss) @ VV)(*lowrank(sq(Ma), L, rng, exact))
    out['sqrtcnt'] = rownorm(Sh * Sh)
    neg['sqrtcnt'] = float((Sh < 0).mean())

    Xh = (lambda US, ss, VV: (US * ss) @ VV)(*lowrank(sq(rownorm(Ma)), L, rng, exact))
    phell = rownorm(Xh * Xh)
    out['hell'] = phell
    neg['hell'] = float((Xh < 0).mean())
    out['hellbk'] = rownorm(0.9 * phell + 0.1 * qb)
    neg['hellbk'] = neg['hell']

    Z = (lambda US, ss, VV: (US * ss) @ VV)(*lowrank(wsqrt * sq(rownorm(Ma)), L, rng, exact))
    Xw = Z / wsqrt
    out['hellw'] = rownorm(Xw * Xw)
    neg['hellw'] = float((Z < 0).mean())

    W, H = pair_matrix.nmf(Ma, L, np.random.default_rng(1), nmf_iters)
    Wh = W @ H
    out['nmf'] = rownorm(Wh)
    neg['nmf'] = float((Wh < 0).mean())
    return out, neg, M_mar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('--outdirs', required=True)
    ap.add_argument('--ls', default='16', help='comma-separated ranks')
    ap.add_argument('--alphas', default='0,0.01,0.05,0.2,1.0')
    ap.add_argument('--nmf-iters', type=int, default=200)
    ap.add_argument('--exact', action='store_true',
                    help='use the exact SVD (small N only)')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    alphas = [float(a) for a in args.alphas.split(',')]
    Ls = [int(x) for x in args.ls.split(',')]

    for outdir in args.outdirs.split(','):
        cache = os.path.join(outdir, 'M.npz')
        if os.path.exists(cache):
            M = np.load(cache)['M']
        else:
            M, _, _ = pair_matrix.build_matrix(
                args.corpus, os.path.join(outdir, 'common_substrings.txt'))
            np.savez_compressed(cache, M=M)
        n = M.shape[0]
        P = rownorm(M.astype(np.float64))
        Nw = M.sum(1).astype(np.float64)
        krows = int((M.sum(1) > 0).sum())
        print(f"\n=== {outdir}  N={n}  rows={krows}  "
              f"svd={'exact' if args.exact else 'randomised'} ===", flush=True)
        for L in Ls:
            hdr = 'method'.ljust(12) + ''.join(f"a={a:<9g}" for a in alphas)
            tw, tu, negtab = {}, {}, {}
            for alpha in alphas:
                rng = np.random.default_rng(args.seed)
                out, neg, M_mar = models_for(M, L, alpha, rng, args.exact,
                                             args.nmf_iters)
                for name in METHODS:
                    tw.setdefault(name, {})[alpha] = kl_rows(P, out[name], Nw)
                    tu.setdefault(name, {})[alpha] = kl_rows(P, out[name])
                    negtab.setdefault(name, {})[alpha] = neg[name]

            def table(tab):
                print(hdr)
                for name in METHODS:
                    print(name.ljust(12) + ''.join(f"{tab[name][a]:<11.4f}"
                                                   for a in alphas))

            print(f"\n-- L = {L} --  mean KL (bits), OCCURRENCE-WEIGHTED "
                  f"(lower is better)")
            table(tw)
            print("   ... the same, uniform over rows (the metric reported "
                  "until now)")
            table(tu)
            print("   latent negative fraction (%)")
            table({k: {a: 100 * v for a, v in d.items()}
                   for k, d in negtab.items()})

        ind_mar = rownorm(M_mar)
        print(f"\nindependence model: KL "
              f"{kl_rows(P, ind_mar, Nw):.4f} (weighted) / "
              f"{kl_rows(P, ind_mar):.4f} (uniform) bits")


if __name__ == '__main__':
    main()
