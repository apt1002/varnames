#!/usr/bin/env python3
"""Shared 64-bit rolling-hash helpers for the substring / successor scripts.

Window hashes are computed with the standard polynomial hash

    hash(s) = sum_{k=0}^{l-1} s[k] * B^{l-1-k}   (mod 2^64),

the same convention as common_substrings.py.  To get every window length in
O(1) per (position, length) -- rather than O(length) -- we use a prefix-hash
Q with  Q[end] - Q[start] * B^(end-start) = hash(T[start:end]).  Q is built from
a cumsum, using the modular inverse of B (B is odd, so invertible mod 2^64):

    Q[m] = B^(m-1) * sum_{k<m} T[k] * B^-k .
"""
import numpy as np

B = 0x9E3779B97F4A7C15
BINV = pow(B, -1, 1 << 64)


def hash_bytes(s):
    h = 0
    for b in s:
        h = (h * B + b) & 0xFFFFFFFFFFFFFFFF
    return h


def bpow_table(max_len):
    t = np.ones(max_len + 1, dtype=np.uint64)
    for l in range(1, max_len + 1):
        t[l] = np.uint64((int(t[l - 1]) * B) & 0xFFFFFFFFFFFFFFFF)
    return t


def prefix_q(seg):
    """Prefix hashes Q of seg (uint64), Q[0]=0, len(Q)=len(seg)+1."""
    L = seg.shape[0]
    with np.errstate(over='ignore', invalid='ignore'):
        t1 = np.full(L, np.uint64(BINV), dtype=np.uint64)
        t1[0] = 1
        w = seg.astype(np.uint64) * np.cumprod(t1)
        S = np.empty(L + 1, dtype=np.uint64)
        S[0] = 0
        S[1:] = np.cumsum(w)
        t2 = np.full(L, np.uint64(B), dtype=np.uint64)
        t2[0] = 1
        Q = np.empty(L + 1, dtype=np.uint64)
        Q[0] = 0
        Q[1:] = S[1:] * np.cumprod(t2)
    return Q
