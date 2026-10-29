"""Prefix/suffix adjacency matrix M of common substrings, and its low-rank
factorisation M ~ U V^T with L << N.  This module is the library half of
``pair_matrix.py``; the executable half (command-line driver) is there.

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
(Halko et al.) is used throughout.  Each saved ``pair_factors_L*.npy`` records a
``sqrt`` flag so consumers know whether to square the reconstruction.
"""
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


def load_or_build_matrix(corpus, subs, outdir):
    """Return the N x N count matrix for `outdir`, caching it as M.npz.

    Building M rescans the whole corpus (~5 min), so every script that needs it
    shares this cache instead of rebuilding.
    """
    cache = os.path.join(outdir, 'M.npz')
    if os.path.exists(cache):
        return np.load(cache)['M']
    M = build_matrix(corpus, subs)[0]
    os.makedirs(outdir, exist_ok=True)
    np.savez_compressed(cache, M=M)
    return M


def randomized_svd(M, rank, rng, n_iter=8):
    """Randomised range finder (Halko-Martinsson-Tropp), range M(MᵀM)^n_iter Ω.

    We only need the top ``rank`` directions, so instead of an O(N^3) exact SVD
    we sample the range: draw a random N x (rank+p) block Ω, form the basis
    Q = qr(A Ω) and do an exact SVD of the small B = QᵀA.  Each power step
    replaces A by (A Aᵀ) A, amplifying the dominant directions by σ_i^{2q+1}
    and so sharpening the subspace when the spectrum decays slowly.

    The range basis is re-orthonormalised (QR) after *every* power step.  The
    earlier version accumulated ``Y = A @ (A.T @ Y)`` without re-orthonormalising
    and then did a single QR, which both lost accuracy at moderate N (a single
    power iteration gave 3.02 vs the exact 3.09 bits at N=2102) and overflowed
    in float32 for n_iter ≳ 8.  With the per-step QR, float32 no longer
    overflows -- and is as accurate as float64, since the error is set by
    n_iter, not the dtype.  At N = 2102 (sqrt domain) the default n_iter = 8
    matches the exact SVD to ~0.001 bits (n_iter = 4 gave ~0.005, the old
    single-iteration routine ~0.07); the count-space factorisation converges a
    little more slowly.
    """
    n = M.shape[0]
    p = min(10, rank)
    A = M.astype(np.float32)
    Om = rng.standard_normal((n, rank + p)).astype(np.float32)
    Q, _ = np.linalg.qr(A @ Om)
    for _ in range(n_iter):
        Z = A.T @ Q
        Q, _ = np.linalg.qr(A @ Z)
    Bm = Q.T @ A
    Ub, s, Vt = np.linalg.svd(Bm, full_matrices=False)
    U = Q @ Ub
    return U[:, :rank], s[:rank], Vt[:rank]


def kl_joint(M, Mhat, eps=1e-12):
    """KL(M/T || Mhat/ΣMhat) in bits -- the relative entropy between the
    empirical *joint* distribution over (prefix, suffix) pairs and a
    non-negative model reconstruction, each normalised to unit total mass.

    The metric is on the joint, so no conditional p(b|a) is ever formed.  This
    loses nothing: by the entropy chain rule

        KL(P(a,b) || Q(a,b)) = KL(P(a) || Q(a))
                               + Σ_a P(a) KL(P(b|a) || Q(b|a))

    and the prefix-marginal term is a model-independent constant, so scoring
    the joint carries exactly the same information as the old row-normalised
    conditional metric -- it just avoids normalising rows of M and of every
    model.  `eps` floors the model so that exact zeros stay finite.
    """
    Mj = M / float(M.sum())
    Mh = np.maximum(Mhat, 0.0)
    s = float(Mh.sum())
    Mh = Mh / s if s > 0 else np.full(Mh.shape, 1.0 / Mh.size)
    Mh = np.maximum(Mh, eps)
    nz = Mj > 0
    return float((Mj[nz] * np.log2(Mj[nz] / Mh[nz])).sum())


def nmf(M, rank, rng, iters=100):
    n = M.shape[0]
    W = rng.random((n, rank)).astype(np.float32) + 1e-3
    H = rng.random((rank, n)).astype(np.float32) + 1e-3
    A = M.astype(np.float32)
    for _ in range(iters):
        H *= (W.T @ A) / (W.T @ W @ H + 1e-9)
        W *= (A @ H.T) / (W @ H @ H.T + 1e-9)
    return W, H
