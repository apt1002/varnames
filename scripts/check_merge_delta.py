#!/usr/bin/env python3
"""Regression test for the per-merge change in the tree-words score.

`docs/TREE_WORDS.md` derives, for merging one word pair `uv -> w`,

    CS' - CS = delta_formula(...)

in terms of the unigram and bigram counts plus three context aggregates
(A, B, Q).  This script checks that formula against a brute-force merge: build a
random cyclic corpus, merge `uv` by actually replacing the occurrences, recount,
recompute the score, and compare.

The corpora are random over a small alphabet and deliberately include the
awkward cases:
  * `u = v`  (merging a doubled word, which consumes two copies of it);
  * `A(v) > 0` and `B(u) > 0` (the `vuv` / `uvu` contexts);
  * `Q > 0`   (adjacent `uvuv` occurrences, which produce a `(w,w)` bigram).

Usage: check_merge_delta.py [--trials 3000] [--seed 1]
"""
import argparse
import math
import random
from collections import Counter


def L(x):
    """z log z, with 0 log 0 = 0."""
    return 0.0 if x == 0 else x * math.log(x)


def ngram_counts(seq, k):
    n = len(seq)
    c = Counter()
    for i in range(n):
        c[tuple(seq[(i + j) % n] for j in range(k))] += 1
    return c


def score(seq):
    """CS = sum_u N(u) log N(u) - sum_{u,v} N(u,v) log N(u,v)."""
    U = Counter(seq)
    B = ngram_counts(seq, 2)
    return sum(L(v) for v in U.values()) - sum(L(v) for v in B.values())


def merge(seq, u, v, w):
    """Replace every non-overlapping occurrence of the pair (u, v) by w."""
    n = len(seq)
    out = []
    i = 0
    while i < n:
        if seq[i] == u and seq[(i + 1) % n] == v:
            out.append(w)
            i += 2
        else:
            out.append(seq[i])
            i += 1
    return out


def delta_formula(seq, u, v):
    """CS(after merge) - CS(before merge), from the counts of `seq`."""
    B2 = ngram_counts(seq, 2)
    T3 = ngram_counts(seq, 3)
    F4 = ngram_counts(seq, 4)
    U = Counter(seq)
    m = B2.get((u, v), 0)
    if m == 0:
        return 0.0

    alpha = sorted(set(seq) | {u, v})
    A = lambda x: T3.get((x, u, v), 0)      # occurrences with predecessor x
    B = lambda y: T3.get((u, v, y), 0)      # occurrences with successor y
    Q = F4.get((u, v, u, v), 0)             # adjacent uvuv patterns

    if u == v:                               # merging a doubled word (z, z)
        z = u
        dU = L(U[z] - 2 * m) - L(U[z]) + L(m)
        dB = L(0) - L(m)                                    # (z,z) -> gone
        for x in alpha:
            if x != z:
                dB += L(B2.get((x, z), 0) - A(x)) - L(B2.get((x, z), 0))
        for y in alpha:
            if y != z:
                dB += L(B2.get((z, y), 0) - B(y)) - L(B2.get((z, y), 0))
        for a in alpha:
            if a != z:
                dB += L(A(a))
        for b in alpha:
            if b != z:
                dB += L(B(b))
        return dU - dB

    dU = (L(U[u] - m) - L(U[u])
          + L(U[v] - m) - L(U[v]) + L(m))
    dB = L(0) - L(m)                                        # (u,v) -> gone
    for x in alpha:
        if x != v:
            dB += L(B2.get((x, u), 0) - A(x)) - L(B2.get((x, u), 0))
    dB += L(B2.get((v, u), 0) - A(v) - B(u) + Q) - L(B2.get((v, u), 0))
    for y in alpha:
        if y != u:
            dB += L(B2.get((v, y), 0) - B(y)) - L(B2.get((v, y), 0))
    for a in alpha:
        if a != v:
            dB += L(A(a))
    dB += L(A(v) - Q)
    dB += L(B(u) - Q)
    for b in alpha:
        if b != u:
            dB += L(B(b))
    dB += L(Q)                                              # (w,w)
    return dU - dB


def usable(seq, u, v):
    """Skip corpora where the merge is ill-defined for this pair."""
    n = len(seq)
    if seq[n - 1] == u and seq[0] == v:      # match straddles the wrap
        return False
    if u == v:                                # overlapping occurrences (uuu)
        s = seq + [seq[0], seq[1]]
        return not any(s[i] == u == s[i + 1] == s[i + 2] for i in range(n))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    w = -1                                   # a token outside the alphabet

    tested = bad = n_uvuv = n_eq = 0
    for _ in range(args.trials):
        n = rng.randint(6, 20)
        k = rng.randint(2, 5)
        seq = [rng.randrange(k) for _ in range(n)]
        F4 = ngram_counts(seq, 4)
        B2 = ngram_counts(seq, 2)
        for u in range(k):
            for v in range(k):
                if not usable(seq, u, v) or B2.get((u, v), 0) == 0:
                    continue
                brute = score(merge(seq, u, v, w)) - score(seq)
                form = delta_formula(seq, u, v)
                tested += 1
                n_uvuv += F4.get((u, v, u, v), 0) > 0
                n_eq += u == v
                if abs(brute - form) > 1e-9 * max(1.0, abs(brute)):
                    bad += 1
                    if bad <= 5:
                        print(f"MISMATCH seq={seq} u={u} v={v} "
                              f"brute={brute!r} formula={form!r}")
    print(f"tested {tested} (u==v: {n_eq}, Q>0: {n_uvuv}), mismatches {bad}")
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
