#!/usr/bin/env python3
"""Exploring a better low-rank prefix/suffix model: square-root (Hellinger)
factorisation of the count matrix, and a prior on unobserved pairs.

Idea 1 -- Hellinger factorisation
---------------------------------
A truncated SVD minimises squared L2 error, but the model is scored by KL.  For
probability vectors the sqrt map is an isometry,

    ||sqrt(p) - sqrt(q)||^2 = 2 H^2(p, q)  ~  2 KL(p || q)   for p ~ q,

so we factorise the Hellinger embedding sqrt(M) of the *count* matrix and square
the reconstruction back:

    M_hat  =  (U Sigma V^T)_L^2 ,   sqrt(M) ~ (U Sigma V^T)_L .

The square is non-negative however signed the reconstruction is, so the *model*
never has negative probabilities -- the negatives stay in the latent scores,
where they only affect the Hellinger-space fit.  This is the single Hellinger
model, `sqrtcnt`.

Working in count space is the point.  sqrt(M)[a,b] = sqrt(N_a) sqrt(p(b|a)), so
rooting the counts already builds in the occurrence weighting: this model is
identical to rooting a row-normalised p(b|a) and weighting by sqrt(N_a) (the
`hellw` of earlier versions).  We therefore never form the conditional p(b|a);
the model and the empirical matrix are both compared as *joints*.

Idea 2 -- a prior on unobserved pairs (the counting fix)
--------------------------------------------------------
M counts only observed (a, b) pairs; a structural zero is not an impossibility.
We add a fixed amount of pseudo-count mass, shaped like the independence model,

    M_ref = M + alpha * P_mar ,   P_mar = (r/T)(c/T)^T   (sum 1),

with ``alpha = kappa * N`` (``kappa`` is the prior mass *per context*;
``--kappas`` sweeps it, default 1000 -- the held-out optimum is ~10^3, constant
across N; see docs/HELLINGER_FACTORISATION.md).  The correction has a *fixed*
total mass, not a fraction of the corpus ``T``: that makes it a genuine prior on
unseen pairs which washes out as the corpus grows (adding ``alpha * M_mar`` with
``M_mar`` unnormalised would instead inject ``alpha * T`` and never vanish).

M_ref *is* the reference for the whole analysis: every model is a
reconstruction of M_ref and is scored against M_ref.  Results are therefore not
comparable across ``kappa`` -- by design.  ``kappa`` is a *counting* fix, not a
reconstruction knob; the reconstruction version of "mix in the independence
model" already exists as the ``backoff`` remedy below.

Scored by KL(M_ref/ΣM_ref || M_hat/sum M_hat) in bits, plus the negative
fraction of the latent reconstruction (the model itself is non-negative for the
sqrt variant).

Usage: sqrt_and_smooth.py CORPUS --outdirs work/common100000,... [--ls 8,16,32]
       [--kappas 1000] [--exact]
"""
import argparse
import os

import numpy as np

import pair_matrix_lib as pair_matrix

KL = pair_matrix.kl_joint


def sq(M):
    return np.sqrt(np.maximum(M, 0.0))


def lowrank(M, L, rng, exact):
    if exact:
        U, s, Vt = np.linalg.svd(np.asarray(M, dtype=np.float64),
                                 full_matrices=False)
        return U[:, :L], s[:L], Vt[:L]
    return pair_matrix.randomized_svd(M, L, rng)


METHODS = ('clip', 'abs', 'backoff .1', 'nmf', 'sqrtcnt')


def priors(M, alpha):
    """Return (M_mar, P_mar, M_ref).

    ``M_mar = r c^T / T`` has total mass ``T`` and is kept for the convex
    ``backoff`` mixture.  ``P_mar = (r/T)(c/T)^T`` has total mass 1 and is the
    shape of the counting prior.  ``M_ref = M + alpha * P_mar`` is the
    corrected reference for scoring.
    """
    r = M.sum(1)
    cc = M.sum(0)
    T = float(M.sum())
    M_mar = np.outer(r, cc) / max(T, 1.0)
    P_mar = np.outer(r / T, cc / T)
    return M_mar, P_mar, M.astype(np.float64) + alpha * P_mar


def models_for(M, L, alpha, rng, exact, nmf_iters):
    """Return (name -> model matrix M_hat, name -> latent negative fraction,
    M_mar, M_ref).

    All models are non-negative count-scale reconstructions of ``M_ref``; the
    metric normalises them, so their absolute scale does not matter.
    """
    M_mar, P_mar, Ma = priors(M, alpha)
    out, neg = {}, {}

    U, s, V = lowrank(Ma, L, rng, exact)
    Mh = (U * s) @ V
    out['clip'] = np.maximum(Mh, 0.0)
    out['abs'] = np.abs(Mh)
    out['backoff .1'] = 0.9 * np.maximum(Mh, 0.0) + 0.1 * M_mar
    neg['clip'] = neg['abs'] = neg['backoff .1'] = float((Mh < 0).mean())

    Sh = (lambda US, ss, VV: (US * ss) @ VV)(*lowrank(sq(Ma), L, rng, exact))
    out['sqrtcnt'] = Sh * Sh
    neg['sqrtcnt'] = float((Sh < 0).mean())

    W, H = pair_matrix.nmf(Ma, L, np.random.default_rng(1), nmf_iters)
    Wh = W @ H
    out['nmf'] = Wh
    neg['nmf'] = float((Wh < 0).mean())
    return out, neg, M_mar, Ma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('--outdirs', required=True)
    ap.add_argument('--ls', default='16', help='comma-separated ranks')
    ap.add_argument('--kappas', default='1000',
                    help='prior mass as multiples of N (mass per context, '
                         'independence-shaped); alpha = kappa * N.  The '
                         'held-out optimum is ~10^3 (constant across N).')
    ap.add_argument('--nmf-iters', type=int, default=200)
    ap.add_argument('--exact', action='store_true',
                    help='use the exact SVD (small N only)')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    kappas = [float(x) for x in args.kappas.split(',')]
    Ls = [int(x) for x in args.ls.split(',')]

    for outdir in args.outdirs.split(','):
        M = pair_matrix.load_or_build_matrix(
            args.corpus, os.path.join(outdir, 'common_substrings.txt'), outdir)
        n = M.shape[0]
        krows = int((M.sum(1) > 0).sum())
        print(f"\n=== {outdir}  N={n}  rows={krows}  "
              f"svd={'exact' if args.exact else 'randomised'} ===", flush=True)
        for L in Ls:
            hdr = 'method'.ljust(12) + ''.join(f"k={k:<9g}" for k in kappas)
            tk, negtab = {}, {}
            for k in kappas:
                alpha = k * n
                rng = np.random.default_rng(args.seed)
                out, neg, M_mar, Ma = models_for(M, L, alpha, rng, args.exact,
                                                 args.nmf_iters)
                for name in METHODS:
                    tk.setdefault(name, {})[k] = KL(Ma, out[name])
                    negtab.setdefault(name, {})[k] = neg[name]

            print(f"\n-- L = {L} --  KL(M_ref || M_hat/sum M_hat) in bits "
                  f"(lower is better); M_ref = M + kappa*N*P_mar")
            print(hdr)
            for name in METHODS:
                print(name.ljust(12) +
                      ''.join(f"{tk[name][k]:<11.4f}" for k in kappas))
            print("   latent negative fraction (%)")
            for name in METHODS:
                print(name.ljust(12) +
                      ''.join(f"{100*negtab[name][k]:<11.4f}" for k in kappas))

        print("\nindependence model KL(M_ref || P_mar) by kappa:")
        for k in kappas:
            alpha = k * n
            M_mar, P_mar, Ma = priors(M, alpha)
            print(f"  kappa={k:<6g}  alpha={alpha:<12.4g}  "
                  f"KL {KL(Ma, M_mar):.4f} bits")


if __name__ == '__main__':
    main()
