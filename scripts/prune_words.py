#!/usr/bin/env python3
"""Overshoot the word list, then prune it by removal cost (the ``Delta_CS`` of
un-merging a word).

Idea.  The greedy most-frequent-pair build commits to its
first ``NUM_PAIRS`` words.  Build ``overshoot * NUM_PAIRS`` instead, then
repeatedly delete the *removable* word (one that is not a child of any kept
word) whose removal costs the least, until the list is back to ``NUM_PAIRS``.
If the overshoot explored words the greedy prefix missed, this keeps the better
``NUM_PAIRS`` and approaches the compression of the larger list at the smaller
model size.

Removal cost.  Deleting a pair word ``w = (a, b)`` is the exact inverse of the
merge that created it: every token ``w`` is split back into ``a, b``.  From the
*current* bigram counts alone (no trigram scan) the new counts are

    U'[a] += N(w), U'[b] += N(w), U'[w] = 0,
    (x, w) -> (x, a) and (w, y) -> (b, y) for each occurrence,
    (w, w) removed once,  (a, b) created N(w) times,
    and each ``w w`` adjacency contributes a single ``(b, a)``,

so the change in ``CS = S1 - S2`` (``L(z) = z log z``) is exact.  ``split_cost``
implements it; ``selfcheck`` verifies it (and ``apply_split``) against a
brute-force recount.

Only pair words are pruned; run words (few, valuable) are always kept.

Usage:
    prune_words.py run --target 512 --overshoot 1.5 --sample 20 \\
        --build-corpus work/camel/merged_training.txt \\
        --validation work/camel/merged_validation.txt --val-stride 20
"""
import argparse
import heapq
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw


def L(x):
    return 0.0 if x < 1e-12 else x * np.log(x)


def cs(U, B):
    return sum(L(v) for v in U.values()) - sum(L(v) for v in B.values())


def split_delta_counts(U, B, w, a, b):
    """Net change to each bigram cell when the word ``w = (a, b)`` is split."""
    d = Counter()
    Nw = U[w]
    Nww = B.get((w, w), 0.0)
    for (x, y), c in B.items():
        if y == w and x != w:
            d[(x, w)] -= c
            d[(x, a)] += c
        elif x == w and y != w:
            d[(w, y)] -= c
            d[(b, y)] += c
    d[(w, w)] -= Nww
    d[(a, b)] += Nw
    d[(b, a)] += Nww
    return d


def split_cost(U, B, w, a, b):
    """Exact ``CS(after splitting w) - CS(before)`` (>= 0)."""
    Nw = U[w]
    if Nw <= 0:
        return 0.0
    dS1 = L(U[a] + Nw) - L(U[a]) + L(U[b] + Nw) - L(U[b]) - L(Nw)
    dS2 = 0.0
    for cell, dc in split_delta_counts(U, B, w, a, b).items():
        old = B.get(cell, 0.0)
        dS2 += L(old + dc) - L(old)
    return dS1 - dS2


def apply_split(U, B, w, a, b):
    """Mutate ``U`` and ``B`` as if the word ``w = (a, b)`` were split."""
    Nw = U[w]
    for cell, dc in split_delta_counts(U, B, w, a, b).items():
        new = B.get(cell, 0.0) + dc
        if new <= 0:
            B.pop(cell, None)
        else:
            B[cell] = new
    U[a] += Nw
    U[b] += Nw
    U.pop(w, None)


def _rand_split_check(trials=600, seed=1):
    rng = np.random.default_rng(seed)
    bad = 0
    for _ in range(trials):
        n = int(rng.integers(6, 20))
        k = int(rng.integers(2, 4))
        seq = [int(x) for x in rng.integers(0, k, n)]
        a, b, w = 0, 1, k
        merged, i = [], 0
        while i < len(seq):
            if seq[i] == a and i + 1 < len(seq) and seq[i + 1] == b:
                merged.append(w)
                i += 2
            else:
                merged.append(seq[i])
                i += 1
        if w not in merged:
            continue
        U, B = Counter(merged), Counter()
        for i in range(len(merged)):
            B[(merged[i], merged[(i + 1) % len(merged)])] += 1
        cost = split_cost(U, B, w, a, b)
        split = []
        for t in merged:
            split.extend([a, b] if t == w else [t])
        U2, B2 = Counter(split), Counter()
        for i in range(len(split)):
            B2[(split[i], split[(i + 1) % len(split)])] += 1
        brute = cs(U2, B2) - cs(U, B)
        Ua, Ba = Counter(U), Counter(B)
        apply_split(Ua, Ba, w, a, b)
        eq = (dict(Ua) == dict(U2)
              and {k: v for k, v in Ba.items() if v}
              == {k: v for k, v in B2.items() if v})
        if abs(cost - brute) > 1e-9 * max(1.0, abs(brute)) or not eq:
            bad += 1
            if bad <= 5:
                print(f"MISMATCH merged={merged} cost={cost} brute={brute} "
                      f"counts_equal={eq}")
    return bad


# --------------------------------------------------------------- id bookkeeping

def word_ids(rules, nchars):
    """For each rule, the list of word ids it creates."""
    out = []
    nxt = nchars + 1
    for item in rules:
        if item[0] == 'pair':
            out.append([nxt])
            nxt += 1
        else:
            m = len(item[2])
            out.append(list(range(nxt, nxt + m)))
            nxt += m
    return out


# --------------------------------------------------------------- pruning

def build_plan_corpus(lines, rules, nchars):
    char_id = {c: i for i, c in enumerate(sorted(set(''.join(lines))))}
    plan = tw.make_plan(rules, nchars)
    seqs = [tw.tokenize(s, char_id, plan, nchars) for s in lines]
    return seqs, char_id


def counts(seqs):
    U, B = Counter(), Counter()
    for s in seqs:
        for t in s:
            U[t] += 1
        for i in range(len(s)):
            B[(s[i], s[(i + 1) % len(s)])] += 1
    return U, B


def prune(rules, nchars, seqs, target, verbose=True):
    """Return ``(alive_word_ids, removed)``.

    ``removed`` is a list of ``(cost, word_id, (a, b))`` in deletion order.
    """
    ids = word_ids(rules, nchars)
    pair_rule = {}                        # word id -> rule index
    for r, item in enumerate(rules):
        if item[0] == 'pair':
            pair_rule[ids[r][0]] = r
    run_words = set()
    for r, item in enumerate(rules):
        if item[0] == 'run':
            run_words.update(ids[r])
    alive = set(pair_rule) | run_words

    refcount = Counter()
    for r, item in enumerate(rules):
        if item[0] == 'pair':
            _, (a, b), _ = item
            for c in (a, b):
                if c in pair_rule:
                    refcount[c] += 1

    U, B = counts(seqs)
    heap = []
    for wid in pair_rule:
        if refcount[wid] == 0:
            _, (a, b), _ = rules[pair_rule[wid]]
            heapq.heappush(heap, (split_cost(U, B, wid, a, b), wid))

    nwords = len(alive)
    removed = []
    while nwords > target and heap:
        cost, wid = heapq.heappop(heap)
        if wid not in alive:
            continue
        _, (a, b), _ = rules[pair_rule[wid]]
        c = split_cost(U, B, wid, a, b)
        if abs(c - cost) > 1e-9:         # stale; re-queue with the fresh cost
            heapq.heappush(heap, (c, wid))
            continue
        apply_split(U, B, wid, a, b)
        alive.discard(wid)
        removed.append((c, wid, (a, b)))
        nwords -= 1
        for ch in (a, b):
            if ch in pair_rule:
                refcount[ch] -= 1
                if refcount[ch] == 0 and ch in alive:
                    _, (ca, cb), _ = rules[pair_rule[ch]]
                    heapq.heappush(heap, (split_cost(U, B, ch, ca, cb), ch))
        if verbose and len(removed) % 200 == 0:
            print(f"  removed {len(removed)}  words left {nwords}", flush=True)
    return alive, removed


def remap_rules(rules, nchars, alive):
    """Drop pruned pair rules and renumber the survivors."""
    ids = word_ids(rules, nchars)
    newid = {}
    nxt = nchars + 1
    out = []
    for r, item in enumerate(rules):
        if item[0] == 'pair':
            if ids[r][0] not in alive:
                continue
            _, (a, b), _ = item
            out.append(('pair', (newid.get(a, a), newid.get(b, b)), nxt))
            newid[ids[r][0]] = nxt
            nxt += 1
        else:
            _, a, created = item
            newc = []
            for k, _nid in created:
                newc.append((k, nxt))
                nxt += 1
            out.append(('run', newid.get(a, a), newc))
    return out


def score_model(lines_build, lines_val, rules, nchars, val_stride, kappa):
    seqs, char_id = build_plan_corpus(lines_build, rules, nchars)
    U, B = counts(seqs)
    V = max(U) + 1 if U else nchars + 1
    Ua = np.zeros(V, dtype=np.float64)
    for k, v in U.items():
        Ua[k] = v
    T = float(Ua.sum())
    alpha = kappa * V
    den = Ua * (1.0 + alpha / T)
    plan = tw.make_plan(rules, nchars)
    stop = nchars
    log2 = 1.0 / np.log(2.0)
    val = lines_val[::val_stride] if val_stride else lines_val
    bits = np.empty(len(val))
    for j, s in enumerate(val):
        seq = tw.tokenize(s, char_id, plan, nchars) + [stop]
        n = len(seq)
        b = 0.0
        for i in range(n):
            aa = seq[i]
            bb = seq[(i + 1) % n]
            den_a = den[aa]
            num = B.get((aa, bb), 0.0) + alpha * (Ua[aa] / T) * (Ua[bb] / T)
            if den_a <= 0 or num <= 0:       # unseen context / bigram
                p = 1.0 / V
            else:
                p = num / den_a
            b -= np.log(p) * log2
        bits[j] = b
    return float(bits.mean()), V


def cmd_run(args):
    lines_build = tw.read_lines(args.build_corpus, stride=args.sample)
    lines_val = tw.read_lines(args.validation, stride=args.val_stride)
    n_over = int(round(args.overshoot * args.target))
    print(f"building oversize dictionary: {n_over} words "
          f"({args.overshoot}x {args.target}) on {len(lines_build)} lines",
          flush=True)
    chars, rules_over, sym_over = tw.build_dictionary(
        lines_build, n_over, verbose=True)
    nchars = len(chars)
    if args.tokcache:
        import token_cache as tc
        cid = {c: i for i, c in enumerate(sorted(set(''.join(lines_build))))}
        plan_over = tw.make_plan(rules_over, nchars)
        path = tc.build_with(
            f"over{n_over}", args.build_corpus, args.sample,
            lambda s: tw.tokenize(s, cid, plan_over, nchars),
            nchars, len(sym_over), args.cachedir)
        ids, offs = tc.load(path)
        seqs = [ids[offs[j]:offs[j + 1]].tolist() for j in range(len(offs) - 1)]
    else:
        seqs, _ = build_plan_corpus(lines_build, rules_over, nchars)
    print(f"tokenised oversize corpus: {sum(len(s) for s in seqs)} tokens, "
          f"vocab {len(sym_over)}", flush=True)
    alive, removed = prune(rules_over, nchars, seqs, args.target)

    print(f"\nremoved {len(removed)} pair words. first 20 / last 20 "
          f"(deletion order):")
    def show(rows):
        for cost, wid, (a, b) in rows:
            print(f"  {sym_over[wid]!r:22s} <- {sym_over[a]!r}+{sym_over[b]!r}"
                  f"   cost {cost:.2f} nats")
    show(removed[:20])
    print("  ...")
    show(removed[-20:])

    kept = remap_rules(rules_over, nchars, alive)
    if args.outdir:                       # save the surviving word list
        sym_kept = list(chars) + [tw.STOP]
        for item in rules_over:
            if item[0] == 'pair':
                if item[2] in alive:
                    sym_kept.append(sym_over[item[2]])
            else:
                for _k, nid in item[2]:
                    sym_kept.append(sym_over[nid])
        os.makedirs(args.outdir, exist_ok=True)
        tw.save_dictionary(args.outdir, chars, kept, sym_kept)
        print(f"wrote dictionary {args.outdir} "
              f"({len(sym_kept) - nchars - 1} words)", flush=True)
    greedy = tw.build_dictionary(lines_build, args.target)[1]
    # overlap diagnostics: which kept/removed words the greedy build would keep.
    # NB use the *original* oversize ids for names (sym_over is indexed by those);
    # `kept` has been renumbered, so read names off `rules_over`/`alive` instead.
    g_chars, g_rules, g_sym = tw.build_dictionary(lines_build, args.target)
    greedy_words = set()
    for item in g_rules:
        if item[0] == 'pair':
            greedy_words.add(g_sym[item[2]])
    kept_words = set()
    for r, item in enumerate(rules_over):
        if item[0] == 'pair' and item[2] in alive:
            kept_words.add(sym_over[item[2]])
    removed_names = [sym_over[wid] for _, wid, _ in removed]
    n_rm_greedy = sum(1 for nm in removed_names if nm in greedy_words)
    n_new = sum(1 for nm in kept_words if nm not in greedy_words)
    print(f"\npruned {len(removed)} words; {n_rm_greedy} of them are greedy-"
          f"{args.target} words; {n_new} kept words are new (not in greedy-"
          f"{args.target})")
    out = os.path.join('work', f'prune_{args.target}_removed.txt')
    with open(out, 'w') as f:
        for cost, wid, (a, b) in removed:
            f.write(f"{sym_over[wid]}\t{sym_over[a]}\t{sym_over[b]}\t{cost:.3f}"
                    f"\t{'greedy' if sym_over[wid] in greedy_words else 'overshoot'}\n")
    print(f"wrote {out}")
    print(f"\nmodel comparison (held-out mean bits, kappa={args.kappa}):",
          flush=True)
    b_over, V_over = score_model(lines_build, lines_val, rules_over, nchars,
                                 args.val_stride, args.kappa)
    b_prune, V_prune = score_model(lines_build, lines_val, kept, nchars,
                                   args.val_stride, args.kappa)
    b_greedy, V_greedy = score_model(lines_build, lines_val, greedy, nchars,
                                     args.val_stride, args.kappa)
    print(f"  oversize (V={V_over}, {V_over-1-nchars} words): {b_over:.3f} bits")
    print(f"  pruned   (V={V_prune}, {args.target} words): {b_prune:.3f} bits")
    print(f"  greedy   (V={V_greedy}, {args.target} words): {b_greedy:.3f} bits")
    print(f"  pruned vs greedy: {b_greedy - b_prune:+.3f} bits")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    rn = sub.add_parser('run')
    rn.add_argument('--target', type=int, default=512)
    rn.add_argument('--overshoot', type=float, default=1.5)
    rn.add_argument('--build-corpus', default='work/camel/merged_training.txt')
    rn.add_argument('--sample', type=int, default=20)
    rn.add_argument('--validation', default='work/camel/merged_validation.txt')
    rn.add_argument('--val-stride', type=int, default=20)
    rn.add_argument('--kappa', type=float, default=300.0)
    rn.add_argument('--outdir', default='',
                    help='save the surviving word list as a dictionary dir')
    rn.add_argument('--tokcache', action='store_true',
                    help='cache the oversize tokenisation (scripts/token_cache.py)')
    rn.add_argument('--cachedir', default='work/tokcache')
    rn.set_defaults(func=cmd_run)
    ck = sub.add_parser('selfcheck')
    ck.set_defaults(func=lambda a: print(
        f"split_cost/apply_split mismatches: {_rand_split_check()}"))
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
