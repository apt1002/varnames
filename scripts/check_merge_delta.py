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
  * a *genuinely* first-order Markov corpus has `delta = 0` for every merge.
    (Trigram consistency `m = 1` alone is not enough — see
    `check_trigram_markov_counterexample`.)
  * the checkable sufficient condition (trigram identity `m = 1` **and** the
    `(a,b,a,b)` 4-gram identity) also makes `delta = 0` for every merge
    (`check_sufficient_condition`).
  * the *run-aware* rule (collapse a run of a doubled word to a flat `(u^k)`
    instead of merging two copies) restores `delta <= 0` on every step,
    including the run `uuu` corpora that break the plain rule
    (`check_run_aware`).
  * the exact `delta <= 0` proof for a distinct-pair merge is checked through
    its Jensen bound `delta <= R[H(p) - H(alpha) - H(beta)] <= 0`
    (`delta_jensen_bound`, `check_delta_bound`); see `docs/TREE_WORDS.md` §9.0.
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


def delta_jensen_bound(seq, u, v):
    """The Jensen/subadditivity upper bound on `delta` (docs `TREE_WORDS.md` §9).

    With `R = N(v,u)`, `alpha = N(v,u,v)/R`, `beta = N(u,v,u)/R`, and `p` the
    four-way distribution over (predecessor of the `v` is `u`) x (successor of
    the `u` is `v`) across the `R` occurrences of the bigram `(v,u)`,

        delta <= R * [ H(p) - H(alpha) - H(beta) ] <= 0 .

    The bound is proved from the exact entropy form by Jensen on the `u`- and
    `v`-context sums (both have mean `lambda`, resp. `mu`, matching the entropy
    term that is subtracted) and subadditivity `H(p) <= H(alpha) + H(beta)`.
    Returns `None` when the bound is not defined (`u == v`) or `0.0` when the
    two words are not mutually adjacent (`R = 0`, where the bound is the trivial
    zero from Jensen alone)."""
    if u == v:
        return None
    B2 = ngram_counts(seq, 2)
    M = B2.get((u, v), 0)
    R = B2.get((v, u), 0)
    if M == 0:
        return None
    if R == 0:
        return 0.0
    T3 = ngram_counts(seq, 3); F4 = ngram_counts(seq, 4)
    a = T3.get((v, u, v), 0); b = T3.get((u, v, u), 0)
    q4 = F4.get((u, v, u, v), 0)
    parts = [(R - a - b + q4) / R, (a - q4) / R, (b - q4) / R, q4 / R]
    if min(parts) < -1e-9:
        return None
    Hp = -sum(p * math.log(p) for p in parts if p > 0)
    return R * (Hp - H_sh(a / R) - H_sh(b / R))


def run_collapse_delta(seq, u):
    """Collapse each maximal run `u^k` (k >= 2) to one flat token and return
    `(delta, free_bound)`.

    `delta` is the exact `CS` change; `free_bound = m[H(k) - lambda H_b(1/lambda)]`
    is the §9.1 upper bound (m = number of runs of `u`, `lambda = N(u)/m` the
    mean run length, `H(k)` the entropy of the run-length distribution over
    runs).  The bound is `>= delta` and `<= 0` by construction."""
    n = len(seq)
    if u not in seq:
        return 0.0, 0.0
    if all(x == u for x in seq):
        return 0.0, 0.0                      # one run round the cycle: CS = 0
    j0 = next(i for i in range(n) if seq[i] != u)
    order = [seq[(j0 + 1 + k) % n] for k in range(n)]
    segs = []
    runs = []                                # (length, left neighbour, right)
    k = 0
    while k < n:
        if order[k] == u:
            st = k
            while k < n and order[k] == u:
                k += 1
            segs.append(('run', k - st))
            runs.append((k - st, order[(st - 1) % n], order[k % n]))
        else:
            segs.append(('tok', order[k]))
            k += 1
    if not any(kl >= 2 for kl, _, _ in runs):
        return 0.0, 0.0
    base = max(seq) + 1
    ids = {kl: base + i for i, kl in enumerate(sorted({r[0] for r in runs
                                                       if r[0] >= 2}))}
    new = [ids[t[1]] if (t[0] == 'run' and t[1] >= 2) else
           (u if t[0] == 'run' else t[1]) for t in segs]
    delta = score(new) - score(seq)
    m = len(runs)
    nu = sum(r[0] for r in runs)
    lam = nu / m
    c = Counter(r[0] for r in runs)
    Hk = -sum((v / m) * math.log(v / m) for v in c.values())
    return delta, m * (Hk - lam * H_sh(1.0 / lam))


def check_run_collapse_bound(trials=20000, seed=3):
    """`delta <= free_bound <= 0` on random corpora for the run collapse.

    Returns `(failures, n_positive_bounds, n_checked)`; both counts must be
    zero (`docs/TREE_WORDS.md` §9.1)."""
    rng = random.Random(seed)
    nchecked = fails = npos = 0
    for _ in range(trials):
        n = rng.randint(4, 40)
        k = rng.randint(2, 4)
        seq = [rng.randrange(k) for _ in range(n)]
        for u in set(seq):
            d, bnd = run_collapse_delta(seq, u)
            nchecked += 1
            npos += bnd > 1e-9
            if d > bnd + 1e-9 * max(1.0, abs(bnd)):
                fails += 1
                if fails <= 5:
                    print(f"RUN BOUND MISMATCH seq={seq} u={u} "
                          f"delta={d!r} bound={bnd!r}")
    return fails, npos, nchecked


def check_delta_bound(trials=20000, seed=2):
    """`delta <= R[H(p) - H(alpha) - H(beta)] <= 0` on random corpora.
    Returns `(failures, n_positive_bounds, n_checked)`; both counts should be
    zero: the bound is never positive and never below the exact `delta`."""
    rng = random.Random(seed)
    nchecked = fails = npos = 0
    for _ in range(trials):
        n = rng.randint(6, 40)
        k = rng.randint(2, 5)
        seq = [rng.randrange(k) for _ in range(n)]
        B2 = ngram_counts(seq, 2)
        for u in range(k):
            for v in range(k):
                if u == v or not usable(seq, u, v) or B2.get((u, v), 0) == 0:
                    continue
                bnd = delta_jensen_bound(seq, u, v)
                if bnd is None:
                    continue
                d = delta_formula(seq, u, v)
                nchecked += 1
                npos += bnd > 1e-9
                if d > bnd + 1e-9 * max(1.0, abs(bnd)):
                    fails += 1
                    if fails <= 5:
                        print(f"BOUND MISMATCH seq={seq} u={u} v={v} "
                              f"delta={d!r} bound={bnd!r}")
    return fails, npos, nchecked


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
    """A genuinely first-order Markov corpus has `delta = 0` for every merge.
    The periodic corpora below are first-order Markov at every order (trigram
    factors `m = 1` *and* 4-gram factors `m4 = 1`)."""
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


def _multi_counts(cycles, k):
    from collections import Counter
    C = Counter()
    for c in cycles:
        n = len(c)
        for i in range(n):
            C[tuple(c[(i + j) % n] for j in range(k))] += 1
    return C


def check_trigram_markov_counterexample():
    """`m = 1` everywhere is *not* enough for `delta = 0`.

    The three-string corpus "01", "01", "00111010100011" (each bent into a
    cycle) has every trigram factor exactly 1, yet merging (0,1) reduces CS.
    The whole delta is the four-way (4-gram) term.  Returns the number of
    failures (0 = the document's claim is as stated)."""
    cycles = [list(s) + ['\n'] for s in ('01', '01', '00111010100011')]
    U = _multi_counts(cycles, 1)
    B = _multi_counts(cycles, 2)
    T = _multi_counts(cycles, 3)
    F = _multi_counts(cycles, 4)
    fails = 0

    # (i) every trigram factor m = N(a,b,c) N(b) / (N(a,b) N(b,c)) equals 1
    for (a, b, c), nabc in T.items():
        m = nabc * U[(b,)] / (B[(a, b)] * B[(b, c)])
        if abs(m - 1) > 1e-12:
            fails += 1

    # (ii) the merge (0,1) nevertheless reduces CS (brute force on the cycles)
    def score(cyc):
        u, b = _multi_counts(cyc, 1), _multi_counts(cyc, 2)
        return sum(L(v) for v in u.values()) - sum(L(v) for v in b.values())

    def merge_cycle(c, u, v, w):
        n = len(c); out = []; i = 0
        while i < n:
            if i + 1 < n and c[i] == u and c[i + 1] == v:
                out.append(w); i += 2
            else:
                out.append(c[i]); i += 1
        return out

    merged = [merge_cycle(c, '0', '1', 'w') for c in cycles]
    d = score(merged) - score(cycles)
    if not d < -1e-9:
        fails += 1

    # (iii) the whole delta is the four-way term -N(v,u)[H(lam)+H(mu)-H(p)]
    def h(x):
        return 0.0 if x <= 0 or x >= 1 else -x * math.log(x) - (1 - x) * math.log(1 - x)
    M = B[('0', '1')]; R = B[('1', '0')]
    lam = M / U[('0',)]; mu = M / U[('1',)]
    a = T[('1', '0', '1')]; b = T[('0', '1', '0')]; q = F[('0', '1', '0', '1')]
    parts = [(R - a - b + q) / R, (a - q) / R, (b - q) / R, q / R]
    Hp = -sum(p * math.log(p) for p in parts if p > 0)
    four = -R * (h(lam) + h(mu) - Hp)
    if abs(four - d) > 1e-9 * max(1.0, abs(d)):
        fails += 1
    return fails


def _trigram_markov(seq):
    """N(a,b,c) N(b) = N(a,b) N(b,c) for every trigram (m = 1)."""
    U = Counter(seq); B = ngram_counts(seq, 2); T = ngram_counts(seq, 3)
    return all(v * U[b] == B[(a, b)] * B[(b, c)] for (a, b, c), v in T.items())


def _fourgram_abab(seq):
    """N(a,b,a,b) N(b,a) = N(a,b,a) N(b,a,b) for every a, b."""
    B = ngram_counts(seq, 2); T = ngram_counts(seq, 3); F = ngram_counts(seq, 4)
    syms = set(seq)
    return all(F.get((a, b, a, b), 0) * B.get((b, a), 0)
               == T.get((a, b, a), 0) * T.get((b, a, b), 0)
               for a in syms for b in syms)


def check_sufficient_condition(cap=20000, w='W'):
    """Corpora satisfying both identities of `docs/TREE_WORDS.md` §7.1
    ("A checkable sufficient condition for `delta = 0`") must have `delta = 0`
    for every merge.

    Enumerates all small cyclic corpora, keeps those with the trigram identity
    (m = 1) *and* the `(a,b,a,b)` 4-gram identity, and checks `delta`.  Returns
    `(failures, n_corpora)`."""
    import itertools
    syms = [0, 1, 2]
    fails = 0
    n_ok = 0
    for n in range(3, 12):
        if len(syms) ** n > cap:
            break
        for tup in itertools.product(syms, repeat=n):
            seq = list(tup)
            if not (_trigram_markov(seq) and _fourgram_abab(seq)):
                continue
            n_ok += 1
            B2 = ngram_counts(seq, 2)
            for u in syms:
                for v in syms:
                    if B2.get((u, v), 0) == 0 or not usable(seq, u, v):
                        continue
                    d = score(merge(seq, u, v, w)) - score(seq)
                    if abs(d) > 1e-9:
                        fails += 1
    return fails, n_ok


def most_common_pair(seq):
    """The most frequent length-2 substring `uv` (count >= 2), ties broken by
    smallest `(u, v)`.  `None` if no pair occurs twice."""
    B = ngram_counts(seq, 2)
    best = None
    for (u, v), c in B.items():
        if c < 2:
            continue
        key = (-c, u, v)
        if best is None or key < best[0]:
            best = (key, (u, v))
    return best[1] if best else None


def cyclic_merge_distinct(seq, u, v, w):
    """Replace every non-overlapping occurrence of the pair `(u, v)` by `w`,
    with `u != v` (so occurrences never overlap).

    Done cyclically and correctly: a matching pair at position `i` uses tokens
    `i` and `(i+1) % n`.  The linear `merge()` above double-uses the token at
    position 0 when a match straddles the wrap (which is why `usable()` skips
    those); starting the scan at a match start avoids that."""
    n = len(seq)
    match = [i for i in range(n) if seq[i] == u and seq[(i + 1) % n] == v]
    if not match:
        return list(seq)
    s = min(match)
    order = [seq[(s + k) % n] for k in range(n)]
    out = []
    k = 0
    while k < n:
        if k + 1 < n and order[k] == u and order[k + 1] == v:
            out.append(w)
            k += 2
        else:
            out.append(order[k])
            k += 1
    return out


def collapse_runs(seq, a, base):
    """Collapse each maximal run of the word `a` of length `k >= 2` to a single
    word `(a^k)`, one word per observed length.  Runs of length 1 stay `a`.
    Returns `(new_seq, {length: new_id})`."""
    n = len(seq)
    if all(x == a for x in seq):
        return [base + 2], {n: base + 2}
    j0 = next(i for i in range(n) if seq[i] != a)
    order = [seq[(j0 + 1 + k) % n] for k in range(n)]
    segs = []
    lens = []
    k = 0
    while k < n:
        if order[k] == a:
            Lr = 0
            while k < n and order[k] == a:
                Lr += 1
                k += 1
            segs.append(('run', Lr))
            lens.append(Lr)
        else:
            segs.append(('tok', order[k]))
            k += 1
    uniq = {Lr: base + 2 + j for j, Lr in enumerate(sorted(set(lens)))}
    new = [uniq[t[1]] if t[0] == 'run' else t[1] for t in segs]
    return new, uniq


def run_aware_step(seq):
    """One run-aware dictionary step.

    The most common pair `uv`: if `u != v`, merge it (as usual).  If `u == v`
    (a doubled word) then instead of merging two copies -- the step that breaks
    `delta <= 0` on a run `uuu` -- collapse every maximal run of `u` to one flat
    word `(u^k)` per length.  Returns `(new_seq, kind, info)` with `kind` in
    `{pair, run, none}`."""
    p = most_common_pair(seq)
    if p is None:
        return seq, 'none', None
    u, v = p
    w = max(seq) + 1
    if u != v:
        return cyclic_merge_distinct(seq, u, v, w), 'pair', (u, v)
    new, uniq = collapse_runs(seq, u, max(seq) + 1)
    return new, 'run', (u, uniq)


def check_run_aware(cap=20000, steps=4):
    """The run-aware rule of `docs/TREE_WORDS.md` §9.1
    ("Relaxing `no uuu`") keeps `delta <= 0`.

    Enumerates small cyclic corpora, applies up to `steps` run-aware steps to
    each, and checks every step's `delta`.  Returns `(positives, n_steps,
    n_run, n_pair, worst)`."""
    import itertools
    syms = [0, 1, 2]
    pos = steps_done = n_run = n_pair = 0
    worst = 0.0
    for n in range(2, 13):
        if len(syms) ** n > cap:
            break
        for tup in itertools.product(syms, repeat=n):
            seq = list(tup)
            for _ in range(steps):
                d0 = score(seq)
                new, kind, info = run_aware_step(seq)
                if kind == 'none':
                    break
                steps_done += 1
                n_run += kind == 'run'
                n_pair += kind == 'pair'
                d = score(new) - d0
                if d > 1e-9:
                    pos += 1
                    worst = max(worst, d)
                seq = new
    return pos, steps_done, n_run, n_pair, worst


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
    trig_bad = check_trigram_markov_counterexample()
    cond_bad, cond_n = check_sufficient_condition(w=w)
    run_pos, run_steps, run_run, run_pair, run_worst = check_run_aware()
    bound_bad, bound_pos, bound_n = check_delta_bound()
    runb_bad, runb_pos, runb_n = check_run_collapse_bound()
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
    print(f"trigram-Markov counterexample: failures {trig_bad} "
          f"(all m=1 yet delta<0, from the 4-gram term)")
    print(f"sufficient condition (m=1 and (a,b,a,b)): failures {cond_bad} "
          f"over {cond_n} corpora (every merge has delta=0)")
    print(f"run-aware step: positives {run_pos} over {run_steps} steps "
          f"(run {run_run}, pair {run_pair}, worst {run_worst:.1e})")
    print(f"Jensen bound (delta <= R[H(p)-H(alpha)-H(beta)] <= 0): failures "
          f"{bound_bad}, positive bounds {bound_pos}, checked {bound_n}")
    print(f"run-collapse bound (delta <= m[H(k)-lambda H_b(1/lambda)] <= 0): "
          f"failures {runb_bad}, positive bounds {runb_pos}, checked {runb_n}")
    raise SystemExit(1 if (bad or d1bad or mexpbad or markov_bad or ex_bad
                           or trig_bad or cond_bad or run_pos
                           or bound_bad or bound_pos
                           or runb_bad or runb_pos) else 0)


if __name__ == '__main__':
    main()
