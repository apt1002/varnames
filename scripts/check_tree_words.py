#!/usr/bin/env python3
"""Regression test for the pair-merge dictionary in `scripts/tree_words.py`.

`tree_words.py` is fast because it keeps the dictionary build, the tokeniser and
the bigram count *incremental*: pair merges blank out one token of each merged
adjacent pair and patch only the neighbouring counts, and tokenising uses a
linked list plus a rank heap.  Every one of
those shortcuts has been a source of silent drift in the past (lost counts
across the `None` holes left by merges; a stale heap key after a decrement), so
this script re-derives the same answers the slow, obvious way and compares.

Three checks, all on random synthetic corpora plus the real `tw*` dictionaries:

  1. `builder`   the greedy build (rules and their order) against a
                 from-scratch recount-and-replace builder;
  2. `tokenize`  the fast plan replay against an independent, obviously-correct
                 replay of the same compiled plan;
  3. `adjacency` the incremental bigram matrix against a direct count over the
                 independently tokenised cycles.

Exit status is 0 when every check passes.  `--real` also checks the saved
`work/tw{512,2040,4414}ns` dictionaries against a fresh replay.

Usage:
    python3 scripts/check_tree_words.py            # synthetic fuzz only
    python3 scripts/check_tree_words.py --real     # + the work/tw* dictionaries
    python3 scripts/check_tree_words.py --trials 5000 --verbose
"""
import argparse
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw                                        # noqa: E402


# ---------------------------------------------------------------- reference ---

def reference_build(lines, num_pairs):
    """Slow builder: recount all bigrams from scratch at every step.

    Self-merges are forbidden, so no run step is ever taken."""
    chars = sorted(set(''.join(lines)))
    cid = {c: i for i, c in enumerate(chars)}
    seqs = [[cid[c] for c in s] for s in lines]
    rules = []
    next_id = len(chars) + 1
    budget = num_pairs
    while budget > 0:
        cnt = Counter()
        for seq in seqs:
            for j in range(len(seq) - 1):
                cnt[(seq[j], seq[j + 1])] += 1
        if not cnt:
            break
        cands = [(c, p) for p, c in cnt.items() if p[0] != p[1]]
        if not cands:                   # no eligible pair left
            break
        best = max(c for c, _ in cands)
        if best <= 1:                   # nothing left that occurs twice
            break
        cand = min(p for c, p in cands if c == best)
        a, b = cand                     # ordinary pair merge
        new = next_id
        next_id += 1
        budget -= 1
        rules.append(('pair', (a, b), new))
        merged = []
        for seq in seqs:
            out = []
            i, n = 0, len(seq)
            while i < n:
                if i < n - 1 and seq[i] == a and seq[i + 1] == b:
                    out.append(new)
                    i += 2
                else:
                    out.append(seq[i])
                    i += 1
            merged.append(out)
        seqs = merged
    return chars, rules


def _norm(rules):
    """Compare rule *sequences* (ids are assigned in order, so they match)."""
    return [r[1] for r in rules]


def replay_plan(tokens, plan):
    """Independent replay of a compiled plan; no heap, no linked list."""
    toks = list(tokens)
    for _, rank in plan:
        while True:
            best = None
            for i in range(len(toks) - 1):
                r = rank.get((toks[i], toks[i + 1]))
                if r is not None and (best is None or r[0] < best[0]):
                    best = (r[0], i, r[1])
            if best is None:
                break
            _, i, new = best
            toks[i:i + 2] = [new]
    return toks


# ------------------------------------------------------------------ checks ---

def check_builder(trials, verbose):
    rng = random.Random(1)
    bad = 0
    for t in range(trials):
        alpha = rng.choice(['aab', 'aabbcc', 'abcdef', 'aaaab', 'aaa'])
        lines = [''.join(rng.choice(alpha) for _ in range(rng.randint(2, 60)))
                 for _ in range(rng.randint(1, 7))]
        lines = [s for s in lines if s]
        if not lines:
            continue
        npairs = rng.randint(1, 25)
        _, r1, _ = tw.build_dictionary(lines, npairs)
        _, r2 = reference_build(lines, npairs)
        if _norm(r1) != _norm(r2):
            bad += 1
            if verbose and bad <= 3:
                print(f"  builder mismatch trial {t} npairs {npairs}")
                print(f"    fast {_norm(r1)}")
                print(f"    ref  {_norm(r2)}")
    return bad


def check_tokenize_and_adjacency(trials, verbose):
    rng = random.Random(2)
    bad_tok = bad_adj = 0
    for t in range(trials):
        alpha = rng.choice(['aab', 'aabbcc', 'abcdef', 'aaaab', 'aaa'])
        lines = [''.join(rng.choice(alpha) for _ in range(rng.randint(2, 60)))
                 for _ in range(rng.randint(1, 7))]
        lines = [s for s in lines if s]
        if not lines:
            continue
        npairs = rng.randint(1, 25)
        chars, rules, _ = tw.build_dictionary(lines, npairs)
        cid = {c: i for i, c in enumerate(chars)}
        nchars = len(chars)
        plan = tw.make_plan(rules, nchars)

        toks = []
        for s in lines:
            fast = tw.tokenize(s, cid, plan, nchars)
            ref = replay_plan([cid[c] for c in s], plan)
            toks.append(ref)
            if fast != ref:
                bad_tok += 1
                if verbose and bad_tok <= 3:
                    print(f"  tokenize mismatch trial {t}: {s!r}")
                    print(f"    fast {fast}")
                    print(f"    ref  {ref}")

        big, _ = tw.count_adjacency(lines, cid, plan, nchars)
        direct = Counter()
        for seq in toks:
            cyc = seq + [nchars]
            for i in range(len(cyc)):
                direct[(cyc[i], cyc[(i + 1) % len(cyc)])] += 1
        if big != direct:
            bad_adj += 1
            if verbose and bad_adj <= 3:
                diff = {k: (big.get(k, 0), direct.get(k, 0))
                        for k in set(big) | set(direct)
                        if big.get(k, 0) != direct.get(k, 0)}
                print(f"  adjacency mismatch trial {t}: {list(diff.items())[:5]}")
    return bad_tok, bad_adj


def check_real(verbose):
    """Check saved dictionaries against a fresh replay of their own rules."""
    import numpy as np
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    bad = 0
    corpus = os.path.join(root, 'work/camel/merged_training.txt')
    for name in ('tw512ns', 'tw2040ns', 'tw4414ns'):
        d = os.path.join(root, 'work', name)
        if not os.path.isdir(d):
            continue
        chars, rules, sym = tw.load_dictionary(d)
        cid = {c: i for i, c in enumerate(chars)}
        nchars = len(chars)
        plan = tw.make_plan(rules, nchars)
        nwords = len(rules)
        assert len(sym) == nchars + 1 + nwords, f"{name}: vocab size"
        assert max(max(r[1]) for r in rules) < len(sym)

        # replay a sample of the *training* corpus through both tokenisers
        lines = tw.read_lines(corpus, stride=997, limit=2000)
        bad_tok = 0
        seqs = []
        for s in lines:
            fast = tw.tokenize(s, cid, plan, nchars)
            ref = replay_plan([cid[c] for c in s], plan)
            seqs.append(ref)
            if fast != ref:
                bad_tok += 1
        big, _ = tw.count_adjacency(lines, cid, plan, nchars)
        direct = Counter()
        for seq in seqs:
            cyc = seq + [nchars]
            for i in range(len(cyc)):
                direct[(cyc[i], cyc[(i + 1) % len(cyc)])] += 1
        ok = big == direct
        print(f"  {name}: vocab {len(sym)} ({nwords} words), "
              f"tokenize {'OK' if bad_tok == 0 else f'{bad_tok} BAD'}, "
              f"bigrams {'OK' if ok else 'MISMATCH'} ({len(big)} distinct)")
        if bad_tok or not ok:
            bad += 1
            if verbose:
                print(f"    first fast/ref pair: {tw.tokenize(lines[0], cid, plan, nchars)}"
                      f" vs {replay_plan([cid[c] for c in lines[0]], plan)}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--trials', type=int, default=600)
    ap.add_argument('--real', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    bad_build = check_builder(args.trials, args.verbose)
    bad_tok, bad_adj = check_tokenize_and_adjacency(args.trials, args.verbose)
    print(f"synthetic: {args.trials} trials — builder mismatches {bad_build}, "
          f"tokenize {bad_tok}, adjacency {bad_adj}")
    bad_real = check_real(args.verbose) if args.real else 0
    total = bad_build + bad_tok + bad_adj + bad_real
    print("PASS" if total == 0 else f"FAIL ({total})")
    return 0 if total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
