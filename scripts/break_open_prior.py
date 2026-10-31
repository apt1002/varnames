#!/usr/bin/env python3
"""C5: the break-open prior (`docs/BREAK_OPEN_PRIOR.md`).

Builds the word reference matrix `M` bottom-up in `NUM_PAIRS` order,

    M_ref(a,b) = N(a,b) + alpha * P(break(a,b)),        P = M / sum(M),

carrying the triple `(N_r, M_r, S_r)` level by level: at level `r` the new word
`w = (uv)` takes its row from `P(v,.)` and its column from `P(.,u)` read off the
*previous* level (before `w` is inserted); a *dead* cell `(u,v)` is zeroed
outright (count and prior); a run word `(u^k)` is `k`-ary with `lc = rc = u`.

The observed-count part `N_r` is replayed from a trace recorded by
`tree_words.build_dictionary` (the merge bookkeeping of TREE_WORDS.md §5), so a
single expensive pass yields the per-level counts and the prior is then rebuilt
cheaply for each `alpha`.

Held-out comparison: score held-out identifiers under the first-order word
Markov model `P_ref(b|a) = M(a,b) / sum_y M(a,y)` and compare the break-open
prior against the independence prior `P_mar` (the C6 baseline).

Usage:
    break_open_prior.py --dir work/tw2040 --kappas 3,10,30,100,300,1000,3000
    break_open_prior.py --selfcheck
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tww


# ---------------------------------------------------------------- trace replay

def trace_replay(trace, alpha, mode='break'):
    """Replay the level-by-level build from a `build_dictionary` trace.

    Returns `(M, Ncur, V, prior, info)`: the final joint reference matrix `M`,
    the observed counts `Ncur`, the vocabulary `V`, the prior block, and a
    diagnostic dict.  `mode` is `'break'` (break-open prior), `'mar'` (the
    independence prior `alpha*P_mar` read off the final marginals) or `'plain'`
    (no prior, `M = N`)."""
    nchars = trace['nchars']
    stop = nchars
    entries = trace['entries']
    nwords = sum(1 if e[0] == 'pair' else len(e[2]) for e in entries)
    Vcap = nchars + 1 + nwords
    Ncur = np.zeros((Vcap, Vcap), dtype=np.float64)
    prior = np.zeros((Vcap, Vcap), dtype=np.float64)
    rows, cols, vals = trace['level0']
    Ncur[rows, cols] = vals
    nsum = float(vals.sum())
    psum = 0.0
    next_id = nchars + 1
    nzeroed = 0
    fill = mode in ('break', 'breakz')

    if fill:
        V0 = next_id
        blk = Ncur[:V0, :V0]
        T0 = float(blk.sum())
        P0 = (np.outer(blk.sum(1), blk.sum(0)) / (T0 * T0)
              if T0 > 0 else np.zeros((V0, V0)))
        prior[:V0, :V0] = alpha * P0
        psum = float(prior[:V0, :V0].sum())

    def add_cell(w, child, axis):
        """Fill row (`axis=0`) or column (`axis=1`) `w` from joint row/col of
        `child`, and return the prior mass added."""
        invS = 1.0 / (nsum + psum)
        if axis == 0:
            v = (Ncur[child, :next_id] + prior[child, :next_id]) * alpha * invS
            prior[w, :next_id] = v
        else:
            v = (Ncur[:next_id, child] + prior[:next_id, child]) * alpha * invS
            prior[:next_id, w] = v
        return float(v.sum())

    for e in entries:
        if e[0] == 'pair':
            _, u, v, w, Ls, Rs = e      # w = (uv): lc = u, rc = v
            if fill:
                invS = 1.0 / (nsum + psum)
                m = add_cell(w, v, 0)                       # row w  from P(v,.)
                m += add_cell(w, u, 1)                      # col w  from P(.,u)
                diag = alpha * invS * (Ncur[v, u] + prior[v, u])
                prior[w, w] = diag                          # self-loop P(v,u)
                psum += m + diag
            np.add.at(Ncur, (Ls, u), -1.0)      # (L,u) lost
            np.add.at(Ncur, (u, v), -1.0)       # (u,v) lost, dead
            np.add.at(Ncur, (v, Rs), -1.0)      # (v,R) lost
            np.add.at(Ncur, (Ls, w), 1.0)       # (L,w) gained
            np.add.at(Ncur, (w, Rs), 1.0)       # (w,R) gained
            nsum -= len(Ls)
            nsum -= Ncur[u, v]                              # dead cell (u,v)
            Ncur[u, v] = 0.0
            if fill:
                psum -= prior[u, v]
                prior[u, v] = 0.0
                nzeroed += 1
            next_id += 1
        else:
            _, a, created, snap = e     # a run word (u^k): lc = rc = u = a
            for k, nid in created:
                if fill:
                    invS = 1.0 / (nsum + psum)
                    m = add_cell(nid, a, 0)
                    m += add_cell(nid, a, 1)
                    diag = alpha * invS * (Ncur[a, a] + prior[a, a])
                    prior[nid, nid] = diag
                    psum += m + diag
                next_id += 1
            Ncur[:] = 0.0
            Ncur[snap[0], snap[1]] = snap[2]
            nsum = float(snap[2].sum())
            if fill and 2 in dict(created):
                psum -= prior[a, a]
                prior[a, a] = 0.0
                nzeroed += 1

    V = next_id
    if mode == 'breakz':                     # same *shape*, mass matched to P_mar
        pm = float(prior[:V, :V].sum())
        if pm > 0:
            prior[:V, :V] *= alpha / pm
    if mode == 'mar':
        blk = Ncur[:V, :V]
        T = float(blk.sum())
        P = (np.outer(blk.sum(1), blk.sum(0)) / (T * T)
             if T > 0 else np.zeros((V, V)))
        prior[:V, :V] = alpha * P
    M = Ncur[:V, :V] + prior[:V, :V]
    deadset = set()
    for e in entries:
        if e[0] == 'pair':
            deadset.add((e[1], e[2]))
        elif 2 in dict(e[2]):
            deadset.add((e[1], e[1]))
    zc = np.argwhere(M == 0.0)
    live_zero = sum(1 for a, b in zc if (int(a), int(b)) not in deadset)
    info = dict(nsum=nsum, V=V, nzeroed=nzeroed,
                prior_mass=float(prior[:V, :V].sum()),
                cells_zero=int(len(zc)), cells_zero_live=int(live_zero))
    return M, Ncur[:V, :V], V, prior[:V, :V], info


# ------------------------------------------------------------------- scoring

def score_bits(lines, char_id, plan, nchars, M, Ncur=None, eps=1e-12):
    """Bits of each identifier under `P_ref(b|a) = M(a,b) / M(a,.)`.

    A held-out bigram whose reference mass is exactly zero is floored at `eps`
    and counted in `nzero` (the model has no shape for it).  If `Ncur` is given,
    also return the mean bits and the token count restricted to bigrams whose
    *training* count is zero (the cells the prior exists to fill)."""
    stop = nchars
    rowsum = M.sum(1)
    log2 = 1.0 / np.log(2.0)
    out = np.empty(len(lines), dtype=np.float64)
    nzero = 0
    ntok = 0
    un_sum = 0.0
    un_n = 0
    for idx, s in enumerate(lines):
        seq = tww.tokenize(s, char_id, plan, nchars) + [stop]
        n = len(seq)
        bits = 0.0
        for i in range(n):
            a = seq[i]
            b = seq[i + 1] if i + 1 < n else stop
            ntok += 1
            p = M[a, b] / rowsum[a] if rowsum[a] > 0 else 0.0
            if p <= 0.0:
                nzero += 1
                p = eps
            cb = -np.log(p) * log2
            bits += cb
            if Ncur is not None and Ncur[a, b] == 0:
                un_sum += cb
                un_n += 1
        ntok += 1
        p = M[stop, seq[0]] / rowsum[stop] if rowsum[stop] > 0 else 0.0
        if p <= 0.0:
            nzero += 1
            p = eps
        cb = -np.log(p) * log2
        bits += cb
        if Ncur is not None and Ncur[stop, seq[0]] == 0:
            un_sum += cb
            un_n += 1
        out[idx] = bits
    un = (un_sum / un_n, un_n, 100.0 * un_n / ntok) if un_n else (0.0, 0, 0.0)
    return out, ntok, nzero, un


# --------------------------------------------------------------------- driver

def load_setup(outdir):
    chars, rules, sym = tww.load_dictionary(outdir)
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tww.make_plan(rules, nchars)
    return chars, rules, sym, nchars, char_id, plan


def word_budget(rules):
    return sum(1 if r[0] == 'pair' else len(r[2]) for r in rules)


def build_trace(outdir, rules_saved, corpus, stride, verbose=True):
    """Rebuild the dictionary on `corpus` with a trace **and its own rules**.

    The rebuilt dictionary is the one the trace describes — for the `tw*`
    stride-20 sample it reproduces the saved dictionary exactly (checked)."""
    lines = tww.read_lines(corpus, stride=stride)
    trace = {}
    chars, rules, sym = tww.build_dictionary(lines, word_budget(rules_saved),
                                             trace=trace)
    trace['chars'] = chars
    trace['rules'] = rules
    trace['sym'] = sym
    if rules != rules_saved:
        print("note: rebuilt dictionary differs from the saved one "
              f"({len(rules)} vs {len(rules_saved)} rules)", flush=True)
    return trace, len(lines)


def load_or_build_trace(args, rules_saved):
    if args.load_trace:
        return np.load(args.load_trace, allow_pickle=True).item(), -1
    meta = {}
    mp = os.path.join(args.dir, 'meta.json')
    if os.path.exists(mp):
        with open(mp) as f:
            meta = json.load(f)
    stride = args.train_stride if args.train_stride else meta.get('sample', 0)
    trace, ntrain = build_trace(args.dir, rules_saved, args.corpus, stride)
    if args.save_trace:
        np.save(args.save_trace, trace, allow_pickle=True)
    return trace, ntrain


def js_bits(p, q):
    """Jensen-Shannon divergence in bits between two non-negative vectors."""
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    if p.sum() <= 0 or q.sum() <= 0:
        return float('nan')
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(x, y):
        nz = x > 0
        return float((x[nz] * np.log2(x[nz] / np.maximum(y[nz], 1e-300))).sum())

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def cmd_feasibility(args):
    """Reproduce docs/BREAK_OPEN_PRIOR.md §6: is the boundary child a good proxy
    for a word's row, against the independence prior and the other child?"""
    chars, rules, sym, nchars, char_id, plan = load_setup(args.dir)
    trace, _ = load_or_build_trace(args, rules)
    if trace.get('rules') is not None:
        chars, rules, sym = trace['chars'], trace['rules'], trace['sym']
        nchars = len(chars)
    V = nchars + 1 + word_budget(rules)
    _, Ncur, Vv, _, _ = trace_replay(trace, 1.0, 'plain')
    Mm, _, _, _, _ = trace_replay(trace, args.fkappa * V, 'mar')
    col = Ncur.sum(0)
    rng = np.random.default_rng(1)
    child = {}
    for r in rules:
        if r[0] == 'pair':
            child[r[2]] = r[1]
        else:
            for k, nid in r[2]:
                child[nid] = (r[1], r[1])
    for src, name in ((Ncur, 'raw count rows'), (Mm, 'smoothed M rows')):
        Nw = Ncur.sum(1)
        acc = {'right child': [], 'left child': [], 'independence': [],
               'random word': []}
        for a, (u, v) in child.items():
            if v < nchars + 1 or Nw[v] < 10:
                continue
            row_a = src[a, :Vv]
            acc['right child'].append(js_bits(row_a, src[v, :Vv]))
            acc['left child'].append(js_bits(row_a, src[u, :Vv]))
            acc['independence'].append(js_bits(row_a, col))
            rw = int(rng.integers(nchars + 1, Vv))
            acc['random word'].append(js_bits(row_a, src[rw, :Vv]))
        n = len(acc['right child'])
        print(f"\nfeasibility ({name}); {n} words a with rc(a) a word, "
              f"N(rc(a)) >= 10:")
        for k, val in sorted(acc.items(), key=lambda kv: np.mean(kv[1])):
            wins = 100.0 * np.mean([x < y for x, y in
                                    zip(val, acc['independence'])])
            print(f"  {k:<14} mean JS {np.nanmean(val):.3f} bits  "
                  f"(beats independence {wins:.0f}% of the time)")


def cmd_compare(args):
    chars0, rules0, sym0, nchars0, char_id0, plan0 = load_setup(args.dir)
    meta = {}
    mp = os.path.join(args.dir, 'meta.json')
    if os.path.exists(mp):
        with open(mp) as f:
            meta = json.load(f)
    stride = args.train_stride if args.train_stride else meta.get('sample', 0)
    t0 = time.time()
    trace, ntrain = load_or_build_trace(args, rules0)
    print(f"trace pass: {ntrain} train identifiers (stride {stride}), "
          f"{len(trace['entries'])} levels in {time.time()-t0:.0f}s", flush=True)

    if trace.get('rules') is not None:
        chars, rules, sym = trace['chars'], trace['rules'], trace['sym']
    else:
        chars, rules, sym = chars0, rules0, sym0
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tww.make_plan(rules, nchars)
    V = nchars + 1 + word_budget(rules)
    print(f"dictionary: {len(rules)} rules, vocab {V}, "
          f"{'same as' if rules == rules0 else 'differs from'} the saved one",
          flush=True)
    score_lines = tww.read_lines(args.score_corpus, stride=args.score_stride)
    print(f"vocab {V}, {len(rules)} rules; scoring {len(score_lines)} held-out "
          f"identifiers (stride {args.score_stride})", flush=True)
    budgets = [int(x) for x in args.budgets.split(',')]
    kappas = [float(x) for x in args.kappas.split(',')]

    for mode in args.modes.split(','):
        print(f"\n=== prior: {mode}   (alpha = kappa * V = kappa * {V}) ===")
        hdr = f"{'kappa':>7} {'alpha':>11} {'mean bits':>10}"
        for b in budgets:
            hdr += f" {'<=' + str(b):>8}"
        hdr += f" {'priormass/a':>12} {'unobs bits':>11} {'unobs%':>7} {'zero tok':>9} {'sec':>5}"
        print(hdr)
        for kappa in kappas:
            alpha = kappa * V
            t1 = time.time()
            M, Ncur, Vv, prior, info = trace_replay(trace, alpha, mode)
            bits, ntok, nzero, un = score_bits(score_lines, char_id, plan,
                                               nchars, M, Ncur)
            row = f"{kappa:>7g} {alpha:>11.4g} {bits.mean():>10.3f}"
            for b in budgets:
                row += f" {100.0*(bits <= b).mean():>7.1f}%"
            row += (f" {info['prior_mass']/alpha:>12.3f} {un[0]:>11.3f}"
                    f" {un[2]:>6.1f}% {nzero:>9d} {time.time()-t1:>5.0f}")
            print(row, flush=True)
    print()


def cmd_mix(args):
    """Interpolate the reference prior between the mass-matched break shape
    (lambda=0) and the independence `P_mar` (lambda=1): is the break shape worth
    any weight at all?"""
    chars, rules, sym, nchars, char_id, plan = load_setup(args.dir)
    trace, _ = load_or_build_trace(args, rules)
    if trace.get('rules') is not None:
        chars, rules, sym = trace['chars'], trace['rules'], trace['sym']
        nchars = len(chars)
        char_id = {c: i for i, c in enumerate(chars)}
        plan = tww.make_plan(rules, nchars)
    V = nchars + 1 + word_budget(rules)
    score_lines = tww.read_lines(args.score_corpus, stride=args.score_stride)
    lams = [float(x) for x in args.mix_lambdas.split(',')]
    kappas = [float(x) for x in args.kappas.split(',')]
    print(f"vocab {V}, {len(score_lines)} held-out identifiers; "
          f"mean bits for prior = (1-lam)*break_shape + lam*P_mar")
    print(f"{'kappa':>7}" + "".join(f" {'lam=' + format(l, 'g'):>10}"
                                    for l in lams))
    for kappa in kappas:
        alpha = kappa * V
        _, pN, _, pbr, _ = trace_replay(trace, alpha, 'break')
        pmar = trace_replay(trace, alpha, 'mar')[3]
        pm = float(pbr.sum())
        row = f"{kappa:>7g}"
        for lam in lams:
            prior = (1.0 - lam) * (pbr * (alpha / pm)) + lam * pmar
            bits, _, _, _ = score_bits(score_lines, char_id, plan, nchars,
                                       pN + prior)
            row += f" {bits.mean():>10.3f}"
        print(row, flush=True)


def cmd_selfcheck(args):
    import random
    random.seed(7)
    alpha_blocks = list('abcd')
    lines = []
    for _ in range(300):
        n = random.randint(1, 12)
        lines.append(''.join(random.choice(alpha_blocks) for _ in range(n)))
    lines += ['aaaa', 'bbbbbb', 'abcabc', 'aaabbbaaa', 'ababab'] * 20
    trace = {}
    chars, rules, sym = tww.build_dictionary(lines, 40, trace=trace)
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = tww.make_plan(rules, nchars)
    big, uni = tww.count_adjacency(lines, char_id, plan, nchars)
    V = nchars + 1 + word_budget(rules)

    for mode in ('plain', 'mar', 'break'):
        M, Ncur, Vv, prior, info = trace_replay(trace, 10.0 * V, mode)
        bad = 0
        for a in range(Vv):
            for b in range(Vv):
                if Ncur[a, b] != big.get((a, b), 0):
                    bad += 1
        assert bad == 0, f"count mismatch ({mode}): {bad} cells"
        assert np.isfinite(M).all(), f"non-finite M ({mode})"
        assert (M.sum(1) > 0).all(), f"zero row sum ({mode})"
        for r in rules:
            if r[0] == 'pair':
                u, v = r[1]
                assert Ncur[u, v] == 0.0, f"dead cell count ({mode})"
                if mode == 'break':
                    assert M[u, v] == 0.0, f"dead cell M ({mode})"
    print(f"selfcheck OK: {len(lines)} lines, {len(rules)} rules, vocab {V}; "
          f"replayed counts match the direct cyclic count in all modes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw2040')
    ap.add_argument('--corpus', default='work/camel/merged_training.txt')
    ap.add_argument('--train-stride', type=int, default=0)
    ap.add_argument('--score-corpus',
                    default='work/camel/merged_validation.txt')
    ap.add_argument('--score-stride', type=int, default=20)
    ap.add_argument('--kappas', default='3,10,30,100,300,1000,3000')
    ap.add_argument('--fkappa', type=float, default=300.0)
    ap.add_argument('--budgets', default='64,128')
    ap.add_argument('--modes', default='mar,break')
    ap.add_argument('--save-trace', default=None)
    ap.add_argument('--load-trace', default=None)
    ap.add_argument('--selfcheck', action='store_true')
    ap.add_argument('--feasibility', action='store_true')
    ap.add_argument('--mix', action='store_true')
    ap.add_argument('--mix-lambdas', default='0,0.25,0.5,0.75,0.9,0.99,1')
    args = ap.parse_args()
    if args.selfcheck:
        cmd_selfcheck(args)
    elif args.feasibility:
        cmd_feasibility(args)
    elif args.mix:
        cmd_mix(args)
    else:
        cmd_compare(args)


if __name__ == '__main__':
    main()
