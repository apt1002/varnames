#!/usr/bin/env python3
"""Square-root (Hellinger) factorisation of the **word x word** adjacency
matrix, and structural zeros in the independence prior.

This replaces the earlier prefix/suffix study: the matrix is the run-aware
dictionary's cyclic word-bigram matrix (``work/tw*/adj.npz``), so the
vocabulary is the tree-word `word list`, and identifiers are split only at word
boundaries.  No common substrings appear.

Commands
--------
factor  --  the factorisation study.  Build the dense word matrix ``M``,
            form the reference ``M_ref = M + alpha * P_mar`` with the
            independence-shaped counting prior, reconstruct ``M_ref`` by each
            remedy, and score it by the joint KL ``KL(M_ref/T || M_hat/sum)``.
            ``--struct-zeros`` also zeros the structurally impossible cells of
            ``P_mar`` and renormalises before adding it.

score   --  the held-out study.  Tokenise held-out identifiers, code them with
            the first-order word model under ``P_ref`` (the kappa prior), and
            report the mean bits and 64/128-bit fit rates.  With
            ``--struct-zeros`` the prior is corrected first.

Usage:
    hfactor_words.py factor --dirs work/tw96,work/tw512,work/tw2040 \
        --ls 2,4,8,16,32,64 --kappas 0,100,300,1000,3000
    hfactor_words.py score --dir work/tw2040 --corpus work/camel/merged_validation.txt \
        --kappa 1000 --struct-zeros
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import pair_matrix_lib as pml

KL = pml.kl_joint


# ---------------------------------------------------------------- the matrix

def dense_matrix(outdir):
    chars, rules, sym = tw.load_dictionary(outdir)
    big, uni, V = tw.load_adj(outdir)
    M = np.zeros((V, V), dtype=np.float64)
    for (a, b), d in big.items():
        M[a, b] = d
    return M, np.asarray(uni, dtype=np.float64), chars, rules, sym


def structural_mask(rules, nchars, V):
    """Boolean mask of the structurally impossible token adjacencies.

    A cell ``(a, b)`` is structurally zero when the word list contains the
    merged word ``(ab)`` (then ``a`` and ``b`` are never adjacent as tokens).
    For a word ``w`` with left spine ``n0=w, n1=lc(w), ...`` (down to the
    leftmost leaf), ``(a, w)`` is impossible when some ``(a, n_i)`` is a word
    created before ``n_{i-1}`` was (so ``n_i`` is absorbed by ``a`` before
    ``w`` can form); symmetrically for ``(w, b)`` over the right spine.

    Verified: every masked cell is indeed zero in the observed matrix.
    """
    R = {}                 # word id -> creation rank
    lc, rc = {}, {}
    merge_rank = {}        # (x, y) -> rank of the word created by merging x,y
    for r, item in enumerate(rules):
        if item[0] == 'pair':
            _, (a, b), nid = item
            R[nid] = r
            lc[nid], rc[nid] = a, b
            merge_rank[(a, b)] = r
        else:
            _, a, created = item
            for k, nid in created:
                R[nid] = r
                lc[nid] = rc[nid] = a
                if k == 2:                     # (u^2): removes the u,u bigram
                    merge_rank[(a, a)] = r

    def spine(w, child):
        out = []
        while w in child:
            w = child[w]
            out.append(w)
        return out

    mask = np.zeros((V, V), dtype=bool)
    for (a, b) in merge_rank:
        mask[a, b] = True
    for w in R:
        Rw = R[w]
        for sp, child, left in ((spine(w, lc), lc, True),
                                (spine(w, rc), rc, False)):
            for i, ni in enumerate(sp):
                rprev = Rw if i == 0 else R[sp[i - 1]]
                for a in range(V):
                    mr = merge_rank.get((a, ni) if left else (ni, a))
                    if mr is not None and mr < rprev:
                        if left:
                            mask[a, w] = True
                        else:
                            mask[w, a] = True
    return mask


def priors(M, alpha, mask=None):
    """Return ``(M_mar, P_mar, M_ref)``.

    ``M_mar = r c^T / T`` (total mass ``T``).  ``P_mar = (r/T)(c/T)^T`` (sum 1);
    if ``mask`` is given the structurally impossible cells are zeroed and the
    result is renormalised to sum 1.  ``M_ref = M + alpha * P_mar``.
    """
    r = M.sum(1)
    c = M.sum(0)
    T = float(M.sum())
    M_mar = np.outer(r, c) / max(T, 1.0)
    P_mar = np.outer(r / T, c / T)
    if mask is not None:
        P_mar = np.where(mask, 0.0, P_mar)
        P_mar = P_mar / P_mar.sum()
    return M_mar, P_mar, M + alpha * P_mar


# ------------------------------------------------------------- factorisation

METHODS = ('clip', 'abs', 'backoff .1', 'nmf', 'sqrtcnt')


def sq(M):
    return np.sqrt(np.maximum(M, 0.0))


def sqrtcnt(M, L, seed=1):
    """Hellinger reconstruction ``(sqrt(M) ~ U S V^T)_L`` squared back."""
    U, s, Vt = pml.randomized_svd(sq(M), L, np.random.default_rng(seed))
    Sh = (U * s) @ Vt
    return Sh * Sh


def lowrank(M, L, rng, exact):
    if exact:
        U, s, Vt = np.linalg.svd(np.asarray(M, float), full_matrices=False)
        return U[:, :L], s[:L], Vt[:L]
    return pml.randomized_svd(M, L, rng)


def models_for(M, L, alpha, rng, exact, nmf_iters, mask=None):
    M_mar, P_mar, Ma = priors(M, alpha, mask)
    out, neg = {}, {}
    U, s, V = lowrank(Ma, L, rng, exact)
    Mh = (U * s) @ V
    out['clip'] = np.maximum(Mh, 0.0)
    out['abs'] = np.abs(Mh)
    out['backoff .1'] = 0.9 * np.maximum(Mh, 0.0) + 0.1 * M_mar
    neg['clip'] = neg['abs'] = neg['backoff .1'] = float((Mh < 0).mean())

    US, ss, VV = lowrank(sq(Ma), L, rng, exact)
    Sh = (US * ss) @ VV
    out['sqrtcnt'] = Sh * Sh
    neg['sqrtcnt'] = float((Sh < 0).mean())

    W, H = pml.nmf(Ma, L, np.random.default_rng(1), nmf_iters)
    Wh = W @ H
    out['nmf'] = Wh
    neg['nmf'] = float((Wh < 0).mean())
    return out, neg, M_mar, Ma


def cmd_factor(args):
    kappas = [float(x) for x in args.kappas.split(',')]
    Ls = [int(x) for x in args.ls.split(',')]
    for outdir in args.dirs.split(','):
        M, uni, chars, rules, sym = dense_matrix(outdir)
        V = M.shape[0]
        mask = structural_mask(rules, len(chars), V) if args.struct_zeros else None
        print(f"\n=== {outdir}  V={V}  nnz={int((M > 0).sum())}  "
              f"density={100*(M > 0).mean():.1f}%  "
              f"struct-zeros={'on (%d cells)' % mask.sum() if mask is not None else 'off'}  "
              f"svd={'exact' if args.exact else 'randomised'} ===", flush=True)
        for L in Ls:
            tk, negtab = {}, {}
            for k in kappas:
                alpha = k * V
                rng = np.random.default_rng(args.seed)
                out, neg, M_mar, Ma = models_for(M, L, alpha, rng, args.exact,
                                                 args.nmf_iters, mask)
                for name in METHODS:
                    tk.setdefault(name, {})[k] = KL(Ma, out[name])
                    negtab.setdefault(name, {})[k] = neg[name]
            print(f"\n-- L = {L} --  joint KL (bits, lower better)  "
                  f"M_ref = M + kappa*V*P_mar")
            print('method'.ljust(12) + ''.join(f"k={k:<9g}" for k in kappas))
            for name in METHODS:
                print(name.ljust(12) +
                      ''.join(f"{tk[name][k]:<11.4f}" for k in kappas))
        print("\nindependence model KL(M_ref || M_mar) by kappa:")
        for k in kappas:
            M_mar, P_mar, Ma = priors(M, k * V, mask)
            print(f"  kappa={k:<6g}  KL {KL(Ma, M_mar):.4f} bits")


# ----------------------------------------------------------------- scoring

def ref_table(M, alpha, mask=None, rank=0):
    """Return ``log P_ref`` as a dense V x V array."""
    _, _, M_ref = priors(M, alpha, mask)
    if rank:
        Mhat = sqrtcnt(M_ref, rank)
        row = Mhat.sum(1, keepdims=True)
        P = Mhat / np.maximum(row, 1e-300)
        P = np.maximum(P, 1e-12)
        return np.log2(P)
    den = M_ref.sum(1, keepdims=True)
    with np.errstate(divide='ignore'):
        logp = np.log2(np.where(M_ref > 0, M_ref / np.maximum(den, 1e-300), 1e-300))
    return np.asarray(logp, dtype=np.float64)


def score_corpus(M, chars, rules, corpus, alpha, mask, stride, limit, rank=0):
    V = M.shape[0]
    logp = ref_table(M, alpha, mask, rank)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tw.make_plan(rules, len(chars))
    lines = tw.read_lines(corpus, stride=stride, limit=limit)
    stop = len(chars)
    bits = np.empty(len(lines))
    for i, s in enumerate(lines):
        seq = tw.tokenize(s, char_id, plan, len(chars)) + [stop]
        n = len(seq)
        b = 0.0
        for j in range(n):
            b -= logp[seq[j], seq[(j + 1) % n]]
        bits[i] = b
    return bits, V


def cmd_score(args):
    M, uni, chars, rules, sym = dense_matrix(args.dir)
    alpha = args.kappa * M.shape[0]
    if args.struct_zeros:
        mask = structural_mask(rules, len(chars), M.shape[0])
    else:
        mask = None
    bits, V = score_corpus(M, chars, rules, args.corpus, alpha, mask,
                           args.stride, args.limit, args.rank)
    budgets = [int(x) for x in args.budgets.split(',')]
    tag = 'struct-zeros' if mask is not None else 'plain'
    tag += f' rank={args.rank}' if args.rank else ' full-table'
    print(f"{args.dir}  V={V}  kappa={args.kappa}  {tag}  "
          f"n={len(bits)}  mean bits {bits.mean():.2f}")
    for bud in budgets:
        print(f"  fit <= {bud} bits: {100.0*(bits <= bud).mean():.1f}%")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    fa = sub.add_parser('factor')
    fa.add_argument('--dirs', required=True)
    fa.add_argument('--ls', default='16')
    fa.add_argument('--kappas', default='1000')
    fa.add_argument('--nmf-iters', type=int, default=100)
    fa.add_argument('--exact', action='store_true')
    fa.add_argument('--struct-zeros', action='store_true')
    fa.add_argument('--seed', type=int, default=1)
    fa.set_defaults(func=cmd_factor)
    sc = sub.add_parser('score')
    sc.add_argument('--dir', required=True)
    sc.add_argument('--corpus', default='work/camel/merged_validation.txt')
    sc.add_argument('--kappa', type=float, default=1000.0)
    sc.add_argument('--stride', type=int, default=0)
    sc.add_argument('--limit', type=int, default=0)
    sc.add_argument('--budgets', default='64,128')
    sc.add_argument('--rank', type=int, default=0,
                    help='0 = full table; L>0 = Hellinger (sqrtcnt) reconstruction')
    sc.add_argument('--struct-zeros', action='store_true')
    sc.set_defaults(func=cmd_score)
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
