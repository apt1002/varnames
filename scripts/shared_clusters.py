#!/usr/bin/env python3
"""One cluster assignment for both sides (`docs/SHARED_CLUSTERS.md`).

The co-clustered model stores two membership tables: a *left* cluster from each
word's successor distribution `p(.|a)` and a *right* one from its predecessor
distribution `p(a|.)`.  The membership is the second-largest object in the model
after the word list -- `2V log2 k` bits -- and one assignment would halve it.
This script asks what that costs in held-out bits.

Design (as in the doc): row profile `u_a = sqrt p(.|a)` and column profile
`v_a = sqrt p(a|.)`, concatenate `x_a = [u_a ; w v_a]` (unit-normalised),
spherical `k`-means with occurrence weights, and use the one label as both
`lcl` and `rcl`.  `D` stays `k x k`: `M` is not symmetric, so symmetrising would
change the model, not just its storage.

Controls reported for each `k`:

    asymmetric(k)   the current two-sided clustering
    asymmetric(2k)  the same model with doubled `k` -- the natural way to spend
                    the ~V log2 k bits the shared assignment frees
    shared(k)       one assignment, weight w

Bytes use the accounting of `docs/CLUSTER_QUARTERS.md`: bit-coded parts in
bits/8, stored numbers at one byte each (the quantisation of
`model_fit_rates.py`).  Membership is `V log2 k` bits per side.  The word list
is charged at the price the packed file pays for it (`model_size.pack_rules`),
not at a formula: the dictionary is the largest object in the model, and a
`V log2 V` estimate misprices it by kilobytes.

Usage:
    shared_clusters.py --dir work/tw512ns --ks 16 --stride 100 --half-weight 1
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import cluster_substrings_lib as csl
import model_fit_rates as mfr
import model_size as msz


def profiles(M_ref):
    """Unit Hellinger embeddings of the row and column distributions."""
    r = M_ref.sum(1)
    c = M_ref.sum(0)
    Pr = M_ref / np.maximum(r[:, None], 1e-300)
    Pc = (M_ref.T / np.maximum(c[:, None], 1e-300))
    return (np.sqrt(np.maximum(Pr, 0.0)).astype(np.float32),
            np.sqrt(np.maximum(Pc, 0.0)).astype(np.float32))


def cluster_shared(M_ref, w, k, rng):
    U, Vp = profiles(M_ref)
    X = np.concatenate([U, np.float32(w) * Vp], axis=1)
    X /= np.sqrt(1.0 + w * w)
    wt = M_ref.sum(1)                       # occurrence weights
    labels, _, _ = csl.kmeans_sphere(np.ascontiguousarray(X), wt, k, rng)
    return labels


def model_bytes(V, k, n_assign, dict_bytes=0.0):
    """Word list + unigram + memberships + block, in bytes."""
    word = float(dict_bytes)
    uni = float(V)
    mem = n_assign * V * np.log2(k) / 8.0
    blk = float(k * k)
    return dict(word=word, uni=uni, mem=mem, blk=blk,
                total=word + uni + mem + blk)


def score(M_ref, lcl, rcl, k, seqs):
    c, D, Cc = mfr.assoc_numbers(M_ref, lcl, rcl, k)
    den = D @ Cc
    bits = mfr.bits_assoc(seqs, np.log2(np.maximum(c, 1e-300)),
                          np.log2(np.maximum(D, 1e-300)),
                          np.log2(np.maximum(den, 1e-300)), lcl, rcl)
    asym = float(np.linalg.norm(D - D.T) / max(np.linalg.norm(D), 1e-300))
    return bits, D, asym


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--ks', default='16')
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=100)
    ap.add_argument('--weights', default='0.7071,1,1.4142',
                    help='w in x = [u ; w v] for the weight sweep')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V, nchars = M.shape[0], len(chars)
    alpha = args.kappa * V
    _, P_mar, M_ref = hf.priors(M, alpha)
    lines = tw.read_lines(args.validation, stride=args.stride)
    seqs = mfr.tokenise(lines, chars, rules, nchars)
    print(f"{args.dir}: V={V}, kappa={args.kappa}, held-out n={len(seqs)}")

    bf = mfr.bits_full(seqs, M_ref)
    print(f"[full table] mean {bf.mean():.3f} bits  "
          f"fit<=64 {100 * (bf <= 64).mean():.1f}%  "
          f"fit<=128 {100 * (bf <= 128).mean():.1f}%")
    ks = [int(x) for x in args.ks.split(',')]
    frule = [(msz.to_file_id(a, nchars), msz.to_file_id(b, nchars))
             for _kind, (a, b), _nid in rules]
    dict_bytes = len(msz.pack_rules(frule, V, nchars)[0])
    print(f"word list: {dict_bytes} B packed (Zipf-coded rules)")
    print("asymmetric bytes: " +
          ", ".join(f"k={k}: {model_bytes(V, k, 2, dict_bytes)['total']:.0f} B"
                    for k in ks))

    hdr = (f"  {'model':<16} {'k':>4} {'bits':>8} {'fit64':>7} {'fit128':>7} "
           f"{'bytes':>7} {'D asym':>7}")
    print(hdr)
    for k in [int(x) for x in args.ks.split(',')]:
        rng = np.random.default_rng(args.seed)
        lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
        bits, D, asym = score(M_ref, lcl, rcl, k, seqs)
        bb = model_bytes(V, k, 2, dict_bytes)['total']
        print(f"  {'asymmetric':<16} {k:>4} {bits.mean():>8.3f} "
              f"{100 * (bits <= 64).mean():>6.1f}% "
              f"{100 * (bits <= 128).mean():>6.1f}% {bb:>7.0f} {asym:>7.3f}")
        for w in [float(x) for x in args.weights.split(',')]:
            rng = np.random.default_rng(args.seed)
            lab = cluster_shared(M_ref, w, k, rng)
            bits2, D2, asym2 = score(M_ref, lab, lab, k, seqs)
            bs = model_bytes(V, k, 1, dict_bytes)['total']
            print(f"  {'shared w=%.3f' % w:<16} {k:>4} {bits2.mean():>8.3f} "
                  f"{100 * (bits2 <= 64).mean():>6.1f}% "
                  f"{100 * (bits2 <= 128).mean():>6.1f}% {bs:>7.0f} "
                  f"{asym2:>7.3f}")
    for k in [2 * ks[0]]:
        rng = np.random.default_rng(args.seed)
        lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(args.seed + 1)
        rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
        bits, D, asym = score(M_ref, lcl, rcl, k, seqs)
        bb = model_bytes(V, k, 2, dict_bytes)['total']
        print(f"  {'asymmetric 2k':<16} {k:>4} {bits.mean():>8.3f} "
              f"{100 * (bits <= 64).mean():>6.1f}% "
              f"{100 * (bits <= 128).mean():>6.1f}% {bb:>7.0f} {asym:>7.3f}")


if __name__ == '__main__':
    main()
