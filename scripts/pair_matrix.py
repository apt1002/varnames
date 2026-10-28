#!/usr/bin/env python3
"""Prefix/suffix adjacency matrix M of common substrings, and its low-rank
factorisation M ~ U V^T with L << N.

For every split of every wrapped identifier ^identifier$ (each split being a
position i, the successor T[i]):

    a = longest common substring that is a suffix of the left half  T[..i]
    b = longest common substring that is a prefix of the right half T[i..]

and M[a, b] is incremented.  a is therefore a "left context" (never ending in
'$', since a '$' cannot appear inside a prefix) and b a "right context" (which
may end in '$').  The empty common substring is included, as the backoff
context on either side.

M is then approximated by a rank-L factorisation.  By default the factorisation
is applied to ``sqrt(M)`` elementwise, i.e. in the Hellinger / square-root
domain: for probability vectors ``||sqrt(p) - sqrt(q)||^2 = 2 H^2 ~ 2 KL``, so a
rank-L SVD there minimises the metric that matches KL rather than the count
scale, and squaring the reconstruction back,
``p_hat(b|a) ~ ((U S V^T)[a,b])^2``, is non-negative by construction.  Because
``sqrt(M)[a,b] = sqrt(N_a) sqrt(p(b|a))``, ``sqrt(M)`` is also exactly the
occurrence-weighted Hellinger embedding, so this is the recommended model; pass
``--no-sqrt`` for the old count-space factorisation.  A randomised SVD
(Halko et al., one power iteration) is used throughout.  Each saved
``pair_factors_L*.npy`` records a ``sqrt`` flag so consumers know whether to
square the reconstruction.

Outputs (in --outdir):
    pair_matrix_L<L>.npy   the rank-L factors U (N x L), V (N x L), singular
                           values, and the vocabulary
    pair_stats.txt         N, nnz, density, and relative error vs L, for both
                           the SVD and (optionally) NMF

Usage: pair_matrix.py CORPUS SUBS [--outdir DIR] [--lsvd 2,4,8,16,32,64]
                    [--nmf L] [--nmf-iters 100] [--max-n 6000]
"""
import argparse
import os

import numpy as np

import winhash

B = 0x9E3779B97F4A7C15
NUL = 0
CHUNK = 1 << 21
SYMS = (b"abcdefghijklmnopqrstuvwxyz"
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        b"0123456789_$")


def hash_bytes(s):
    h = 0
    for b in s:
        h = (h * B + b) & 0xFFFFFFFFFFFFFFFF
    return h


def build_text(path):
    buf = bytearray([NUL])
    n = 0
    with open(path, 'rb') as f:
        for line in f:
            ident = line.rstrip(b'\n')
            if not ident:
                continue
            buf += b'^' + ident + b'$'
            buf.append(NUL)
            n += 1
    return bytes(buf), n


def build_matrix(corpus, subs):
    """Return the dense N x N count matrix and the vocabulary."""
    vocab = []
    with open(subs, 'rb') as f:
        for line in f:
            vocab.append(line.rstrip(b'\n'))          # includes the empty string
    idx = {s: i for i, s in enumerate(vocab)}
    empty_idx = idx[b'']
    n = len(vocab)
    max_len = max(len(s) for s in vocab)

    by_len = {}
    for vi, s in enumerate(vocab):
        if s:
            by_len.setdefault(len(s), []).append((winhash.hash_bytes(s), vi))
    Hs, Imap = {}, {}
    for l, lst in by_len.items():
        a = np.array([h for h, _ in lst], dtype=np.uint64)
        ix = np.array([vi for _, vi in lst], dtype=np.int32)
        o = np.argsort(a, kind='stable')
        Hs[l], Imap[l] = a[o], ix[o]
    lengths = sorted(by_len, reverse=True)

    sym_col = np.full(256, -1, dtype=np.int64)
    for i, c in enumerate(SYMS):
        sym_col[c] = i
    Bpow = winhash.bpow_table(max_len)

    text, nlines = build_text(corpus)
    T = np.frombuffer(text, dtype=np.uint8)
    L = T.shape[0]
    Tpad = np.zeros(L + 2 * max_len, dtype=np.uint8)
    Tpad[max_len:max_len + L] = T
    print(f"identifiers: {nlines}  text bytes: {L}  N: {n}  max length: {max_len}",
          flush=True)

    M = np.zeros((n, n), dtype=np.int32)
    for p0 in range(0, L, CHUNK):
        p1 = min(p0 + CHUNK, L)
        m = p1 - p0
        seg = Tpad[p0:p1 + 2 * max_len]
        Q = winhash.prefix_q(seg)
        ai = np.full(m, empty_idx, dtype=np.int32)
        bi = np.full(m, empty_idx, dtype=np.int32)
        with np.errstate(over='ignore'):
            for l in lengths:
                lh = (Q[max_len:max_len + m]
                      - Q[max_len - l:max_len - l + m] * Bpow[l])
                rh = (Q[max_len + l:max_len + l + m]
                      - Q[max_len:max_len + m] * Bpow[l])
                Hl = Hs[l]
                for hw, dest in ((lh, ai), (rh, bi)):
                    pos = np.searchsorted(Hl, hw)
                    np.minimum(pos, Hl.shape[0] - 1, out=pos)
                    hit = (Hl[pos] == hw) & (dest == empty_idx)
                    if hit.any():
                        dest[hit] = Imap[l][pos[hit]]
        valid = sym_col[T[p0:p1]] >= 0
        flat = ai[valid].astype(np.int64) * n + bi[valid]
        np.add.at(M.reshape(-1), flat, 1)
        print(f"  positions processed: {p1}/{L}", flush=True)
    return M, vocab, empty_idx


def randomized_svd(M, rank, rng, n_iter=1):
    n = M.shape[0]
    p = min(10, rank)
    A = M.astype(np.float32)
    Om = rng.standard_normal((n, rank + p)).astype(np.float32)
    Y = A @ Om
    for _ in range(n_iter):
        Y = A @ (A.T @ Y)
    Q, _ = np.linalg.qr(Y)
    Bm = Q.T @ A
    Ub, s, Vt = np.linalg.svd(Bm, full_matrices=False)
    U = Q @ Ub
    return U[:, :rank], s[:rank], Vt[:rank]


def nmf(M, rank, rng, iters=100):
    n = M.shape[0]
    W = rng.random((n, rank)).astype(np.float32) + 1e-3
    H = rng.random((rank, n)).astype(np.float32) + 1e-3
    A = M.astype(np.float32)
    for _ in range(iters):
        H *= (W.T @ A) / (W.T @ W @ H + 1e-9)
        W *= (A @ H.T) / (W @ H @ H.T + 1e-9)
    return W, H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common10000')
    ap.add_argument('--lsvd', default='2,4,8,16,32,64')
    ap.add_argument('--nmf', type=int, default=0)
    ap.add_argument('--nmf-iters', type=int, default=100)
    ap.add_argument('--max-n', type=int, default=6000)
    ap.add_argument('--no-sqrt', action='store_true',
                    help='factorise M itself instead of sqrt(M) (the old '
                         'count-space behaviour)')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    vocab = [ln.rstrip(b'\n') for ln in open(args.substrings, 'rb')]
    cache = os.path.join(args.outdir, 'M.npz')
    if os.path.exists(cache):
        M = np.load(cache)['M']
    else:
        M = build_matrix(args.corpus, args.substrings)[0]
        np.savez_compressed(cache, M=M)
    n = len(vocab)
    A = M if args.no_sqrt else np.sqrt(M)
    domain = 'count' if args.no_sqrt else 'sqrt'
    fro = float(np.linalg.norm(A))
    nnz = int((M > 0).sum())
    print(f"M: {n} x {n}  nnz {nnz}  density {100 * nnz / n / n:.3f}%  "
          f"||M||_F {float(np.linalg.norm(M)):.1f}  domain={domain}")

    lines = [f"N\t{n}", f"nnz\t{nnz}", f"density\t{nnz / n / n:.6f}",
             f"frobenius\t{fro:.6f}", f"domain\t{domain}",
             "L\tsvd_relerr\tnmf_relerr"]
    rng = np.random.default_rng(args.seed)
    if n > args.max_n:
        print(f"N = {n} exceeds --max-n {args.max_n}: skipping factorisation")
        with open(os.path.join(args.outdir, 'pair_stats.txt'), 'w') as f:
            f.write('\n'.join(lines) + '\n')
        return

    nmf_relerr = {}
    if args.nmf:
        W, H = nmf(A, args.nmf, rng, args.nmf_iters)
        nmf_relerr[args.nmf] = float(np.linalg.norm(A - W @ H)) / fro

    for L in [int(x) for x in args.lsvd.split(',') if int(x) <= n]:
        U, s, Vt = randomized_svd(A, L, rng)
        approx = (U * s) @ Vt
        err = float(np.linalg.norm(A - approx)) / fro
        neg = float((U < 0).mean()), float((Vt < 0).mean())
        print(f"L={L:3d}  svd relerr {err:.4f}  (neg entries U {neg[0]:.2f}, "
              f"V {neg[1]:.2f})", flush=True)
        np.save(os.path.join(args.outdir, f'pair_factors_L{L}.npy'),
                {'U': U, 's': s, 'V': Vt, 'sqrt': (not args.no_sqrt),
                 'vocab': np.array(vocab, dtype=object)})
        lines.append(f"{L}\t{err:.6f}\t"
                     + (f"{nmf_relerr[L]:.6f}" if L in nmf_relerr else ''))
    with open(os.path.join(args.outdir, 'pair_stats.txt'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"wrote {os.path.join(args.outdir, 'pair_stats.txt')}")


if __name__ == '__main__':
    main()
