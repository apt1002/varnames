#!/usr/bin/env python3
"""Dictionary-rule experiments for `docs/TREE_WORDS.md` (tasks A3, A4).

Builds a pair-merge dictionary three ways and compares the corpus size it
achieves at a fixed `NUM_PAIRS`:

  * `freq`  -- the plain rule: merge the most frequent pair (ordinary BPE);
  * `runs`  -- the *run-aware* rule of A2: when the most frequent pair is a
               doubled word `(u,u)`, collapse every maximal run `u^k` to a flat
               word `(u^k)` (one word per observed length) instead of merging
               two copies;
  * `delta` -- greedy by the exact drop in corpus size: among the most frequent
               candidate pairs, merge the one whose merge reduces `CS` the most.

`CS = S1 - S2` (base 2), computed on the cyclic tokenisation of the whole
corpus; smaller is better.  Sequences are *linear* while the dictionary is
built (as in the specification) and only bent into cycles for counting.

The two experiments:
  * A4 -- a synthetic corpus family with tunable run mass and boundary mass,
          to locate the `(u^k)` vs `(uv)` crossover;
  * A3 -- `freq` against `delta` on the same corpora.

Usage: dict_experiments.py [--quick]
"""
import argparse
import math
import random
from collections import Counter


def L(x):
    return 0.0 if x < 1e-12 else x * math.log2(x)


def cs(seqs):
    """Corpus size of a multiset of cyclic token sequences (base 2)."""
    U = Counter()
    B = Counter()
    for s in seqs:
        n = len(s)
        if n == 0:
            continue
        for i in range(n):
            U[s[i]] += 1
            B[(s[i], s[(i + 1) % n])] += 1
    return sum(L(v) for v in U.values()) - sum(L(v) for v in B.values())


def _replace_pairs(seqs, a, b, new):
    out = []
    for s in seqs:
        o = []
        i = 0
        n = len(s)
        while i < n:
            if i + 1 < n and s[i] == a and s[i + 1] == b:
                o.append(new)
                i += 2
            else:
                o.append(s[i])
                i += 1
        out.append(o)
    return out


def _collapse_runs(seqs, a, lengths):
    out = []
    for s in seqs:
        o = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == a:
                j = i
                while j < n and s[j] == a:
                    j += 1
                k = j - i
                if k >= 2 and k in lengths:
                    o.append(lengths[k])
                else:
                    o.extend([a] * k)
                i = j
            else:
                o.append(s[i])
                i += 1
        out.append(o)
    return out


def _pair_counts(seqs):
    c = Counter()
    for s in seqs:
        for i in range(len(s) - 1):
            c[(s[i], s[i + 1])] += 1
    return c


def build(corpus, num_pairs, rule='freq', cand=8):
    """Return (seqs, sym, rules).  `sym[id]` is the label; `rules` is the
    ordered list of (pattern_tuple, new_id)."""
    alpha = sorted(set().union(*[set(s) for s in corpus])) if corpus else []
    sym = {i: chr(ord('a') + i) for i in range(len(alpha))}
    idof = {t: i for i, t in enumerate(alpha)}
    seqs = [[idof[t] for t in s] for s in corpus]
    next_id = len(alpha)
    rules = []
    budget = num_pairs
    while budget > 0:
        pc = _pair_counts(seqs)
        pc = {p: c for p, c in pc.items() if c >= 2}
        if not pc:
            break
        ranked = sorted(pc.items(), key=lambda kv: (-kv[1], kv[0]))
        if rule == 'runs' and ranked[0][0][0] == ranked[0][0][1]:
            a = ranked[0][0][0]
            lc = Counter()
            for s in seqs:
                i = 0
                n = len(s)
                while i < n:
                    if s[i] == a:
                        j = i
                        while j < n and s[j] == a:
                            j += 1
                        if j - i >= 2:
                            lc[j - i] += 1
                        i = j
                    else:
                        i += 1
            if not lc:
                merged = ranked[0][0]
                new = next_id
                next_id += 1
                sym[new] = sym[merged[0]] + sym[merged[1]]
                rules.append((merged, new))
                seqs = _replace_pairs(seqs, merged[0], merged[1], new)
                budget -= 1
                continue
            order = sorted(lc, key=lambda k: (-lc[k], k))
            lengths = {}
            for k in order:
                if budget <= 0:
                    break
                new = next_id
                next_id += 1
                sym[new] = sym[a] * k
                rules.append(((a,) * k, new))
                lengths[k] = new
                budget -= 1
            seqs = _collapse_runs(seqs, a, lengths)
            continue
        if rule == 'delta':
            base = cs(seqs)
            best = None
            for p, _ in ranked[:cand]:
                new = next_id
                trial = _replace_pairs(seqs, p[0], p[1], new)
                d = cs(trial) - base
                if best is None or d < best[0]:
                    best = (d, p, trial)
            _, p, trial = best
            new = next_id
            next_id += 1
            sym[new] = sym[p[0]] + sym[p[1]]
            rules.append((p, new))
            seqs = trial
            budget -= 1
            continue
        p = ranked[0][0]
        new = next_id
        next_id += 1
        sym[new] = sym[p[0]] + sym[p[1]]
        rules.append((p, new))
        seqs = _replace_pairs(seqs, p[0], p[1], new)
        budget -= 1
    return seqs, sym, rules


def tokenize(tokens, rules):
    ids = list(tokens)
    for pat, new in rules:
        Lp = len(pat)
        out = []
        i = 0
        n = len(ids)
        while i < n:
            if i + Lp <= n and tuple(ids[i:i + Lp]) == pat:
                out.append(new)
                i += Lp
            else:
                out.append(ids[i])
                i += 1
        ids = out
    return ids


def score(corpus, sym, rules):
    alpha = sorted(set().union(*[set(s) for s in corpus])) if corpus else []
    idof = {t: i for i, t in enumerate(alpha)}
    seqs = [tokenize([idof[c] for c in s], rules) for s in corpus]
    return cs(seqs), seqs

def gen_spread(rng, nlines, lens, runmean, pbound):
    """Run lengths ~ Exponential(runmean); each run of the run-symbol (0) is
    followed by the boundary symbol (1) w.p. `pbound`, else a filler (2/3)."""
    out = []
    for _ in range(nlines):
        s = []
        while len(s) < lens:
            if rng.random() < 0.5:
                r = min(lens, 1 + rng.expovariate(1.0 / runmean))
                s.extend([0] * int(r))
                s.append(1 if rng.random() < pbound else rng.choice([2, 3]))
            else:
                s.append(rng.choice([1, 2, 3]))
        out.append(s[:lens])
    return out


def gen_fixed(rng, nlines, lens, R, pbound):
    """Every run of the run-symbol (0) has the *fixed* length `R`."""
    out = []
    for _ in range(nlines):
        s = []
        while len(s) < lens:
            if rng.random() < 0.6:
                s.extend([0] * R)
                s.append(1 if rng.random() < pbound else 2)
            else:
                s.append(rng.choice([1, 2]))
        out.append(s[:lens])
    return out


def _counts(tr):
    """(N(0,1), {run length: count}, #runs)."""
    n01 = sum(1 for s in tr for i in range(len(s) - 1)
              if s[i] == 0 and s[i + 1] == 1)
    rl = Counter()
    nruns = 0
    for s in tr:
        i = 0
        while i < len(s):
            if s[i] == 0:
                j = i
                while j < len(s) and s[j] == 0:
                    j += 1
                if j - i >= 2:
                    rl[j - i] += 1
                nruns += 1
                i = j
            else:
                i += 1
    return n01, rl, nruns


def _build_single_uv(tr):
    """Dictionary = the single boundary word (0,1)."""
    alpha = sorted(set().union(*[set(s) for s in tr]))
    idof = {t: i for i, t in enumerate(alpha)}
    sym = {i: chr(97 + i) for i in range(len(alpha))}
    new = len(alpha)
    sym[new] = 'xy'
    return sym, [((idof[0], idof[1]), new)]


def _build_single_run(tr):
    """Dictionary = the single (most common-length) flat run word (0^k)."""
    _, sym, rules = build(tr, 1, rule='runs')
    return sym, rules


def held_out_cs(train, test, rule, npairs, cand=8):
    """Build on `train`, tokenise `test`, return CS of the test tokenisation."""
    _, sym, rules = build(train, npairs, rule=rule, cand=cand)
    return score(test, sym, rules)[0]


def a4_spread(quick):
    print("A4(a): full run-aware rule vs plain BPE, held-out CS (bits)")
    print("       run lengths spread out (exponential); run mass N(u,u) = "
          "sum (k-1)*#runs(k)")
    print(f"{'runmean':>8}{'pbound':>7}{'N(u,u)':>8}{'N(u,v)':>8}"
          f"{'freq':>9}{'runs':>9}  winner")
    rng = random.Random(11)
    npairs = 12 if quick else 16
    for runmean in (1.5, 3.0):
        for pbound in (0.2, 0.6, 0.9):
            tr = gen_spread(rng, 600, 20, runmean, pbound)
            te = tr
            n01, rl, _ = _counts(tr)
            nuu = sum((k - 1) * c for k, c in rl.items())
            f = held_out_cs(tr, te, 'freq', npairs)
            r = held_out_cs(tr, te, 'runs', npairs)
            win = 'freq' if f < r else 'runs'
            print(f"{runmean:>8}{pbound:>7}{nuu:>8}{n01:>8}"
                  f"{f:>9.0f}{r:>9.0f}  {win}")


def a4_single(quick):
    print("\nA4(b): a *single* word -- flat run word (0^k) vs boundary (0,1)")
    print("       predictor: run word wins iff (k-1)*#runs(k) > N(u,v)")
    for name, gen, params in (
            ("fixed run length R", gen_fixed, [(3, .1), (3, .5), (3, .9),
                                               (5, .1), (5, .5), (5, .9)]),
            ("spread run lengths (runmean, pbound)",
             gen_spread, [(1.5, .3), (1.5, .7), (3.0, .3), (3.0, .7)])):
        print(f"  -- {name}")
        print(f"    {'R/m':>5}{'pbound':>7}{'save(k*)':>9}{'N(u,v)':>7}"
              f"{'run_CS':>9}{'uv_CS':>9}  win  pred")
        ok = tot = 0
        rng = random.Random(4)
        for p in params:
            pbound = p[1]
            tr = gen(rng, 600, 20, *p)
            n01, rl, nruns = _counts(tr)
            kstar = max(rl, key=lambda k: (rl[k], -k)) if rl else None
            save = (kstar - 1) * rl[kstar] if kstar else 0
            sym_r, rules_r = _build_single_run(tr)
            csr = score(tr, sym_r, rules_r)[0]
            sym_u, rules_u = _build_single_uv(tr)
            csu = score(tr, sym_u, rules_u)[0]
            win = 'run' if csr < csu else 'uv'
            pred = 'run' if save > n01 else 'uv'
            ok += win == pred
            tot += 1
            tag = p[0]
            print(f"    {str(tag):>5}{pbound:>7}{save:>9}{n01:>7}"
                  f"{csr:>9.0f}{csu:>9.0f}  {win:>3}  {pred:>3}"
                  f"{'' if win == pred else '  X'}")
        print(f"    predictor correct {ok}/{tot}")


def a3(quick):
    print("\nA3: greedy-by-frequency vs greedy-by-delta, held-out CS (bits)")
    print(f"{'runmean':>8}{'pbound':>7}{'freq':>9}{'delta':>9}  better")
    rng = random.Random(5)
    npairs = 10 if quick else 14
    for runmean, pbound in ((1.5, 0.25), (3.0, 0.6), (3.0, 0.9)):
        corpus = gen_spread(rng, 1200, 20, runmean, pbound)
        cut = len(corpus) // 2
        tr, te = corpus[:cut], corpus[cut:]
        f = held_out_cs(tr, te, 'freq', npairs)
        d = held_out_cs(tr, te, 'delta', npairs)
        better = 'delta' if d < f else 'freq'
        print(f"{runmean:>8}{pbound:>7}{f:>9.0f}{d:>9.0f}  {better} "
              f"({100.0 * (f - d) / f:+.1f}%)")


def a3_real(path, quick):
    """freq vs delta on a stride sample of a real corpus (identifiers)."""
    n = 4000 if quick else 8000
    lines = []
    with open(path) as f:
        for i, l in enumerate(f):
            if i % 500 == 0:
                s = l.rstrip('\n')
                if s:
                    lines.append(s)
            if len(lines) >= n:
                break
    random.Random(0).shuffle(lines)
    cut = len(lines) // 2
    tr, te = lines[:cut], lines[cut:]
    print(f"\nA3 (real: {path}, train {len(tr)} test {len(te)}, "
          f"{len(set(''.join(tr)))} symbols)")
    print(f"{'npairs':>7}{'freq':>10}{'delta':>10}  better")
    for npairs in (8, 16, 24):
        f = held_out_cs(tr, te, 'freq', npairs)
        d = held_out_cs(tr, te, 'delta', npairs, cand=8)
        better = 'delta' if d < f else 'freq'
        print(f"{npairs:>7}{f:>10.0f}{d:>10.0f}  {better} "
              f"({100.0 * (f - d) / f:+.2f}%)")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--real', default=None,
                    help='corpus file for the A3 real-data comparison')
    args = ap.parse_args()
    a4_spread(args.quick)
    a4_single(args.quick)
    a3(args.quick)
    if args.real:
        a3_real(args.real, args.quick)
