#!/usr/bin/env python3
"""Choose the counting-prior strength kappa by held-out predictive likelihood.

The counting fix (`docs/HELLINGER_FACTORISATION.md`) adds an independence-shaped
prior of fixed mass `alpha = kappa * N` to the reference before factorising
(`kappa` is the prior mass per context).  `kappa` cannot be chosen by the
in-sample KL (which is monotone in it), so we choose it by how well the model
predicts *held-out* pairs:

  * binomial-thin the count matrix M into train/test (each (a,b) count split as
    Binomial(n, p), p = --p);
  * fit the sqrtcnt model to the train reference `M_train + kappa*N*P_mar(train)`;
  * score the test counts under the model, as cross-entropy in bits per held-out
    event (lower is better).

The test set contains pairs that are *zero in train but nonzero in test* -- the
unobserved-coverage question -- so this is the criterion that can actually
reward the prior.  The reported curve is the mean over --reps independent splits;
the independence model (predict every test pair by P_mar(train)) is the
no-latent-structure baseline.

Approximation: thinning the (a,b) count matrix treats each co-occurrence as an
independent multinomial draw; a fully faithful split would re-derive (a,b) from
held-out identifiers.

Usage: choose_kappa.py CORPUS --outdirs work/common100000,... [--L 16]
       [--p 0.5] [--reps 5] [--kappas 0,100,...,10000]
"""
import argparse
import os

import numpy as np

import pair_matrix_lib as pair_matrix


EPS = 1e-12   # predictive floor, so an unseen context costs a fixed penalty


def _ce(q, test):
    s = q.sum()
    ntest = float(test.sum())
    if s <= 0 or ntest <= 0:
        return np.inf
    q = np.maximum(q / s, EPS)
    q /= q.sum()
    nz = test > 0
    ll = float((test[nz] * np.log2(q[nz])).sum())
    return -ll / ntest


def _P_mar(train):
    """Independence shape in float32 (low memory for large N)."""
    r = train.sum(1).astype(np.float32)
    c = train.sum(0).astype(np.float32)
    T = float(train.sum())
    return np.outer(r / T, c / T)


def test_crossentropy(train, test, L, alpha, rng):
    """Cross-entropy (bits/event) of the test counts under the sqrtcnt model of
    `train` (floored at EPS, so contexts unseen in train cost a fixed penalty).
    """
    Ma = train.astype(np.float32)
    Ma += np.float32(alpha) * _P_mar(train)
    sh = pair_matrix.randomized_svd(np.sqrt(Ma), L, rng, n_iter=8)
    q = (sh[0] * sh[1]) @ sh[2]
    return _ce(q * q, test)


def independence_crossentropy(train, test):
    return _ce(_P_mar(train), test)


def support_loss(train, test):
    """Fraction of held-out test mass on cells whose row *or* column context was
    never seen in train (marginal 0) -- unpredictable by any `kappa`."""
    seen_a = train.sum(1) > 0
    seen_b = train.sum(0) > 0
    covered = seen_a[:, None] & seen_b[None, :]
    return float(test[~covered].sum()) / max(float(test.sum()), 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('--outdirs', required=True)
    ap.add_argument('--L', type=int, default=16)
    ap.add_argument('--p', type=float, default=0.5, help='train fraction')
    ap.add_argument('--reps', type=int, default=5)
    ap.add_argument('--kappas', default='0,100,300,500,700,1000,1500,2000,3000,5000,10000')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()
    kappas = [float(x) for x in args.kappas.split(',')]

    for outdir in args.outdirs.split(','):
        M = pair_matrix.load_or_build_matrix(
            args.corpus, os.path.join(outdir, 'common_substrings.txt'),
            outdir)
        n = M.shape[0]
        print(f"\n=== {outdir}  N={n}  events={int(M.sum())}  "
              f"p_train={args.p}  reps={args.reps} ===", flush=True)

        ce = np.full((len(kappas), args.reps), np.nan)
        unseen = []
        ind = []
        for rep in range(args.reps):
            rng = np.random.default_rng(args.seed + rep)
            train = rng.binomial(M, args.p).astype(np.int32)
            test = M - train
            unseen.append(support_loss(train, test))
            ind.append(independence_crossentropy(train, test))
            for ki, kappa in enumerate(kappas):
                rng_svd = np.random.default_rng(args.seed * 7919 + rep)
                ce[ki, rep] = test_crossentropy(train, test, args.L, kappa * n,
                                                rng_svd)

        mean = np.nanmean(ce, axis=1)
        std = np.nanstd(ce, axis=1)
        print(f"held-out test mass on contexts unseen in train (unpredictable "
              f"by any kappa): {100*np.mean(unseen):.2f}%")
        print(f"{'kappa':>7} {'alpha':>12} {'CE_test bits/event':>19} {'std':>9}")
        for ki, kappa in enumerate(kappas):
            a = kappa * n
            if not np.isfinite(mean[ki]):
                print(f"{kappa:>7g} {a:>12.4g} {'inf (zero pred.)':>19}")
            else:
                print(f"{kappa:>7g} {a:>12.4g} {mean[ki]:>19.5f} {std[ki]:>9.5f}")
        if np.isfinite(mean).any():
            bi = int(np.nanargmin(np.where(np.isfinite(mean), mean, np.inf)))
            print(f"best kappa = {kappas[bi]:g}  CE = {mean[bi]:.5f} bits/event")
        print(f"independence model CE = {np.mean(ind):.5f} bits/event")


if __name__ == '__main__':
    main()
