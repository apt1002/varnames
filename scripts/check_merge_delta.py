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

It also checks the `m = 1` part of the same document, `delta^(1)`:
  * rebuilt by substitution (`delta_first_order`) it matches a closed form in
    the four counts `N(u), N(v), N(u,v), N(v,u)` (`delta_first_order_closed`);
  * that closed form is identically zero for a distinct-pair merge, and for a
    doubled word it is the two-count form `delta_first_order_doubled_closed`;
  * a perfectly bigram-Markov corpus has `delta = 0` for every merge.

and the `m != 1` part (`delta = delta^(m)`):
  * the exact conditional-entropy form (`delta_entropy`) matches the brute force;
  * the sum rule `sum_x N(x,u)(m(x,u,v)-1) = 0` holds exactly;
  * scaling every `m - 1` by `eps`, the linear term vanishes and the quadratic
    coefficient matches `delta_quadratic` (the manifestly non-positive form).

With `--exhaustive` it additionally enumerates every small cyclic corpus and
checks that `delta <= 0`, separating distinct-pair merges from doubled words
(the doubled words are non-positive whenever the corpus has no run `uuu`).

Usage: check_merge_delta.py [--trials 3000] [--seed 1]
"""
import argparse
import math
import random
from collections import Counter


def L(x):
    """z log z, with 0 log 0 = 0 (tiny round-off negatives clamp to 0)."""
    return 0.0 if x < 1e-12 else x * math.log(x)


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
    n_uv = B2.get((u, v), 0)
    if n_uv == 0:
        return 0.0

    alpha = sorted(set(seq) | {u, v})
    A = lambda x: T3.get((x, u, v), 0)      # occurrences with predecessor x
    B = lambda y: T3.get((u, v, y), 0)      # occurrences with successor y
    Q = F4.get((u, v, u, v), 0)             # adjacent uvuv patterns

    if u == v:                               # merging a doubled word (z, z)
        z = u
        dU = L(U[z] - 2 * n_uv) - L(U[z]) + L(n_uv)
        dB = L(0) - L(n_uv)                                 # (z,z) -> gone
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

    dU = (L(U[u] - n_uv) - L(U[u])
          + L(U[v] - n_uv) - L(U[v]) + L(n_uv))
    dB = L(0) - L(n_uv)                                     # (u,v) -> gone
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


def h_bin(lam):
    """h(lam) = (1-lam) log(1-lam) + lam log lam, with 0 log 0 = 0."""
    a = (1 - lam) * math.log(1 - lam) if lam < 1 else 0.0
    b = lam * math.log(lam) if lam > 0 else 0.0
    return a + b


def delta_first_order(seq, u, v):
    """delta with every trigram/4-gram factor `m` set to 1 (delta^(1)).

    Rebuilt from the bigram table alone (A(x) = N(x,u)N(u,v)/N(u), and so on).
    `docs/TREE_WORDS.md` proves this is identically zero for a merge of two
    *distinct* words; for a doubled word it reduces to the two-count form
    `delta_first_order_doubled_closed`.
    """
    B2 = ngram_counts(seq, 2)
    U = Counter(seq)
    alpha = sorted(set(seq) | {u, v})

    if u == v:                                # doubled word (z, z)
        z = u
        n_zz = B2.get((z, z), 0)
        if n_zz == 0:
            return 0.0
        nz = U[z]
        lam = n_zz / nz
        A = lambda x: B2.get((x, z), 0) * lam
        B = lambda y: B2.get((z, y), 0) * lam
        dU = L(nz - 2 * n_zz) - L(nz) + L(n_zz)
        dB = L(0) - L(n_zz)
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

    n_uv = B2.get((u, v), 0)
    if n_uv == 0:
        return 0.0
    nu, nv = U[u], U[v]
    n_vu = B2.get((v, u), 0)
    lam, mu = n_uv / nu, n_uv / nv
    A = lambda x: B2.get((x, u), 0) * lam       # m(x,u,v) = 1
    B = lambda y: B2.get((v, y), 0) * mu        # m(u,v,y) = 1
    Q = n_vu * n_uv * n_uv / (nu * nv)          # m(u,v,u,v) = 1

    dU = (L(nu - n_uv) - L(nu) + L(nv - n_uv) - L(nv) + L(n_uv))
    dB = L(0) - L(n_uv)
    for x in alpha:
        if x != v:
            dB += L(B2.get((x, u), 0) - A(x)) - L(B2.get((x, u), 0))
    dB += L(n_vu - A(v) - B(u) + Q) - L(n_vu)
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
    dB += L(Q)
    return dU - dB


def delta_first_order_closed(U, V, M, R):
    """delta^(1) from the four counts N(u), N(v), N(u,v), N(v,u) alone.

    The context sums collapse (log N(x,u) and log N(v,y) cancel) to binary
    entropies; this is the collapsed form of `delta_first_order`.
    """
    lam, mu = M / U, M / V
    dS1 = L(U - M) - L(U) + L(V - M) - L(V) + L(M)
    dS2 = (-L(M) + L(R * (1 - lam) * (1 - mu)) - L(R)
           + L(R * lam * (1 - mu)) + L(R * mu * (1 - lam)) + L(R * lam * mu)
           + (U - R) * h_bin(lam) + (V - R) * h_bin(mu))
    return dS1 - dS2


def delta_first_order_doubled_closed(nz, n_zz):
    """delta^(1) for a doubled-word merge, in N(z) and N(z,z) only."""
    lam = n_zz / nz
    return (L(nz - 2 * n_zz) - L(nz) + 2 * L(n_zz)
            - 2 * (nz - n_zz) * h_bin(lam))


def H_sh(q):
    """Binary Shannon entropy, with 0 log 0 = 0."""
    return 0.0 if not (0.0 < q < 1.0) else -q * math.log(q) - (1 - q) * math.log(1 - q)


def delta_entropy(seq, u, v):
    """Exact merge delta as conditional-entropy differences (docs eq.).

    `D = sum_{x!=v} N(x,u)[H(P(v|x,u))-H(P(v|u))] + (y analogue)
        - N(v,u)[H(P(v|u))+H(P(u|v))-H(p)]`,
    the `log N(x,u)` terms having cancelled.
    """
    B2 = ngram_counts(seq, 2); T3 = ngram_counts(seq, 3); F4 = ngram_counts(seq, 4)
    U = Counter(seq); alpha = sorted(set(seq) | {u, v})
    M = B2.get((u, v), 0)
    if M == 0 or u == v:
        return None
    nu, nv = U[u], U[v]
    R = B2.get((v, u), 0); lam, mu = M / nu, M / nv
    S = 0.0
    for x in alpha:
        nxu = B2.get((x, u), 0)
        if x != v and nxu > 0:
            S += nxu * (H_sh(T3.get((x, u, v), 0) / nxu) - H_sh(lam))
    for y in alpha:
        nvy = B2.get((v, y), 0)
        if y != u and nvy > 0:
            S += nvy * (H_sh(T3.get((u, v, y), 0) / nvy) - H_sh(mu))
    if R > 0:
        a = T3.get((v, u, v), 0); b = T3.get((u, v, u), 0); q = F4.get((u, v, u, v), 0)
        parts = [(R - a - b + q) / R, (a - q) / R, (b - q) / R, q / R]
        Hp = -sum(p * math.log(p) for p in parts if p > 0)
        S -= R * (H_sh(lam) + H_sh(mu) - Hp)
    return S


def delta_quadratic(seq, u, v):
    """Leading O((m-1)^2) term of the merge delta (docs eq.).

    `-1/2 [ lam/(1-lam) sum N(x,u)(m(x,u,v)-1)^2
           + mu/(1-mu) sum N(v,y)(m(u,v,y)-1)^2 + N(v,u) chi^2 ]`.
    The linear term vanishes (exact sum rule `sum_x N(x,u)(m-1) = 0`).
    """
    B2 = ngram_counts(seq, 2); T3 = ngram_counts(seq, 3); F4 = ngram_counts(seq, 4)
    U = Counter(seq); alpha = sorted(set(seq) | {u, v})
    M = B2.get((u, v), 0)
    if M == 0 or u == v:
        return None
    nu, nv = U[u], U[v]
    R = B2.get((v, u), 0); lam, mu = M / nu, M / nv
    if lam >= 1 or mu >= 1:
        return None
    Sx = 0.0
    for x in alpha:
        nxu = B2.get((x, u), 0)
        if x != v and nxu > 0:
            f = T3.get((x, u, v), 0) * nu / (nxu * M) - 1
            Sx += nxu * f * f
    Sy = 0.0
    for y in alpha:
        nvy = B2.get((v, y), 0)
        if y != u and nvy > 0:
            g = T3.get((u, v, y), 0) * nv / (nvy * M) - 1
            Sy += nvy * g * g
    out = -0.5 * (lam / (1 - lam) * Sx + mu / (1 - mu) * Sy)
    if R > 0:
        a = T3.get((v, u, v), 0); b = T3.get((u, v, u), 0); q = F4.get((u, v, u, v), 0)
        if a > 0 and b > 0:
            fa = a * nu / (R * M) - 1
            gb = b * nv / (R * M) - 1
            h = q * R / (a * b) - 1
            A = lam * fa; B = mu * gb; Hq = lam * mu * h
            dp = [-A - B + Hq, A - Hq, B - Hq, Hq]
            p0 = [(1 - lam) * (1 - mu), lam * (1 - mu), mu * (1 - lam), lam * mu]
            out -= 0.5 * R * sum(dp[i] ** 2 / p0[i] for i in range(4))
    return out


def delta_scaled(seq, u, v, eps):
    """Exact entropy delta with every (m - 1) scaled by eps; eps = 0 -> 0."""
    B2 = ngram_counts(seq, 2); T3 = ngram_counts(seq, 3); F4 = ngram_counts(seq, 4)
    U = Counter(seq); alpha = sorted(set(seq) | {u, v})
    M = B2.get((u, v), 0)
    if M == 0 or u == v:
        return None
    nu, nv = U[u], U[v]
    R = B2.get((v, u), 0); lam, mu = M / nu, M / nv
    S = 0.0
    for x in alpha:
        nxu = B2.get((x, u), 0)
        if x != v and nxu > 0:
            q = lam * (1 + eps * (T3.get((x, u, v), 0) * nu / (nxu * M) - 1))
            if not (0 < q < 1):
                return None
            S += nxu * (H_sh(q) - H_sh(lam))
    for y in alpha:
        nvy = B2.get((v, y), 0)
        if y != u and nvy > 0:
            q = mu * (1 + eps * (T3.get((u, v, y), 0) * nv / (nvy * M) - 1))
            if not (0 < q < 1):
                return None
            S += nvy * (H_sh(q) - H_sh(mu))
    if R > 0:
        a = T3.get((v, u, v), 0); b = T3.get((u, v, u), 0); q4 = F4.get((u, v, u, v), 0)
        ma = a * nu / (R * M); mb = b * nv / (R * M)
        mq = (q4 * R / (a * b)) if (a and b) else 0.0
        aa = R * lam * (1 + eps * (ma - 1))
        bb = R * mu * (1 + eps * (mb - 1))
        qq = R * lam * mu * (1 + eps * (mq - 1))
        parts = [(R - aa - bb + qq) / R, (aa - qq) / R, (bb - qq) / R, qq / R]
        if min(parts) < -1e-9:
            return None
        Hp = -sum(p * math.log(p) for p in parts if p > 0)
        S -= R * (H_sh(lam) + H_sh(mu) - Hp)
    return S


def usable(seq, u, v):
    """Skip corpora where the merge is ill-defined for this pair."""
    n = len(seq)
    if seq[n - 1] == u and seq[0] == v:      # match straddles the wrap
        return False
    if u == v:                                # overlapping occurrences (uuu)
        s = seq + [seq[0], seq[1]]
        return not any(s[i] == u == s[i + 1] == s[i + 2] for i in range(n))
    return True


def check_markov_corpora(w):
    """A perfectly first-order (bigram-Markov) corpus has `delta = 0` for every
    merge.  The periodic corpora below have all trigram factors `m = 1`."""
    bad = 0
    for base in ([0, 1, 2], [0, 1, 2, 3], [1, 2, 3, 1, 2, 3]):
        seq = base * 6
        B2 = ngram_counts(seq, 2)
        for u in set(seq):
            for v in set(seq):
                if B2.get((u, v), 0) and usable(seq, u, v):
                    d = score(merge(seq, u, v, w)) - score(seq)
                    if abs(d) > 1e-9:
                        bad += 1
                        print(f"MARKOV MISMATCH base={base} u={u} v={v} d={d!r}")
    return bad


def check_delta_sign_exhaustive(cap=20000):
    """Enumerate every cyclic corpus over <=4 symbols and check `delta <= 0`.

    Returns the number of positive deltas found, split by category:
      * distinct pairs `u != v`;
      * doubled words `u == v` with no run `uuu` (the standing assumption);
      * doubled words with a run (the only place a positive delta lives).
    """
    import itertools
    res = dict(distinct=0, doubled_ok=0, doubled_run=0)
    for k in range(2, 5):
        for n in range(2, 12):
            if k ** n > cap:
                break
            for seq in itertools.product(range(k), repeat=n):
                seq = list(seq)
                has_run = any(seq[i] == seq[(i + 1) % n] == seq[(i + 2) % n]
                              for i in range(n))
                for u in range(k):
                    for v in range(k):
                        if delta_formula(seq, u, v) <= 1e-9:
                            continue
                        if u != v:
                            res['distinct'] += 1
                        elif has_run:
                            res['doubled_run'] += 1
                        else:
                            res['doubled_ok'] += 1
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--exhaustive', action='store_true',
                    help='also enumerate every small cyclic corpus and check '
                         'the sign of delta (slow)')
    args = ap.parse_args()
    rng = random.Random(args.seed)
    w = -1                                   # a token outside the alphabet

    tested = bad = n_uvuv = n_eq = 0
    d1tested = d1bad = 0
    mexp = mexpbad = 0
    for _ in range(args.trials):
        n = rng.randint(6, 20)
        k = rng.randint(2, 5)
        seq = [rng.randrange(k) for _ in range(n)]
        F4 = ngram_counts(seq, 4)
        T3 = ngram_counts(seq, 3)
        B2 = ngram_counts(seq, 2)
        U = Counter(seq)
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

                # delta^(1): zero for distinct pairs, two-count form for u==v
                d1 = delta_first_order(seq, u, v)
                if u == v:
                    d1closed = delta_first_order_doubled_closed(U[u],
                                                                B2.get((u, u), 0))
                else:
                    d1closed = delta_first_order_closed(
                        U[u], U[v], B2.get((u, v), 0), B2.get((v, u), 0))
                d1tested += 1
                if abs(d1 - d1closed) > 1e-9 * max(1.0, abs(d1closed)):
                    d1bad += 1
                    if d1bad <= 5:
                        print(f"D1 MISMATCH seq={seq} u={u} v={v} "
                              f"substituted={d1!r} closed={d1closed!r}")
                if u != v and abs(d1) > 1e-9:
                    d1bad += 1
                    if d1bad <= 5:
                        print(f"D1 NONZERO seq={seq} u={u} v={v} d1={d1!r}")

                # exact entropy form, sum rule, and the (m-1)^2 expansion
                if u != v:
                    ent = delta_entropy(seq, u, v)
                    if ent is not None:
                        mexp += 1
                        if abs(ent - brute) > 1e-9 * max(1.0, abs(brute)):
                            mexpbad += 1
                            if mexpbad <= 5:
                                print(f"ENTROPY MISMATCH seq={seq} u={u} v={v} "
                                      f"brute={brute!r} entropy={ent!r}")
                    # exact sum rule: sum_x N(x,u)(m(x,u,v)-1) == 0
                    srule = sum(T3.get((x, u, v), 0) for x in U) * U[u] / B2[(u, v)] - U[u]
                    if abs(srule) > 1e-9:
                        mexpbad += 1
                        if mexpbad <= 5:
                            print(f"SUM RULE FAIL seq={seq} u={u} v={v} srule={srule!r}")
                    # (m-1)^2 expansion: linear term cancels, quadratic matches
                    if T3.get((v, u, v), 0) and T3.get((u, v, u), 0):
                        qd = delta_quadratic(seq, u, v)
                        s3 = delta_scaled(seq, u, v, 1e-4)
                        if qd is not None and s3 is not None:
                            num = s3 / 1e-8      # numeric quadratic coefficient
                            if abs(num - qd) > 1e-3 * max(1.0, abs(num)):
                                mexpbad += 1
                                if mexpbad <= 5:
                                    print(f"QUAD MISMATCH seq={seq} u={u} v={v} "
                                          f"numeric={num!r} formula={qd!r}")

    markov_bad = check_markov_corpora(w)

    ex_bad = 0
    if args.exhaustive:
        res = check_delta_sign_exhaustive()
        ex_bad = res['distinct'] + res['doubled_ok']
        print(f"exhaustive sign: distinct-pair positives {res['distinct']}, "
              f"doubled-word (no run) positives {res['doubled_ok']}, "
              f"doubled-word (with run) positives {res['doubled_run']}")

    print(f"tested {tested} (u==v: {n_eq}, Q>0: {n_uvuv}), mismatches {bad}")
    print(f"delta^1 checked {d1tested}, mismatches {d1bad} "
          f"(distinct-pair delta^1 is identically zero)")
    print(f"m-part checked {mexp}, mismatches {mexpbad} "
          f"(entropy form, sum rule, quadratic expansion)")
    print(f"bigram-Markov corpora: mismatches {markov_bad} (delta is zero)")
    raise SystemExit(1 if (bad or d1bad or mexpbad or markov_bad or ex_bad) else 0)


if __name__ == '__main__':
    main()
