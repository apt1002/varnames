#!/usr/bin/env python3
"""Is the word list in unigram order?  (It is not.)

The pair-merge dictionary is stored in *creation* order: rule `r` was the
most frequent adjacent pair at step `r`, so the **selection counts** are
monotone non-increasing.  But the unigram the decoder stores is the word's
count in the **final** segmentation, and an early word keeps being absorbed
into longer words later.  This measures the gap on a built dictionary.

Reported per build:

* `rises` -- adjacent creation-order pairs whose final unigram count *increases*
  from `i` to `i+1` (0 if the creation order were unigram order);
* `displacement` -- mean `|rank_creation - rank_unigram|`, as a fraction of `V`;
* the first few created words with their final counts, so the counterexample is
  visible.

The build's own selection counts are not stored in `dict.txt`, so only the
final-segmentation side is measured here; the monotonicity of the selection
counts is a property of the greedy rule, not a measurement.

Usage:
    wordlist_order.py --dirs work/tw4096ns,work/tw6144ns,work/tw8192ns
"""
import argparse
import sys

import numpy as np

sys.path.insert(0, 'scripts')
import tree_words as tw
import model_fit_rates as mfr


def measure(d, corpus, stride):
    chars, rules, sym = tw.load_dictionary(d)
    V = len(sym)
    plan = tw.make_plan(rules, len(chars))
    char_id = {c: i for i, c in enumerate(chars)}
    cnt = np.zeros(V, dtype=np.int64)
    with open(corpus, 'r', encoding='ascii') as f:
        for i, line in enumerate(f):
            if stride and i % stride:
                continue
            s = line.rstrip('\n')
            if not s:
                continue
            for t in tw.tokenize(s, char_id, plan, len(chars)):
                cnt[t] += 1
    nrules = len(rules)
    # id -> creation position; characters are implicit and cost nothing
    created = cnt[len(chars) + 1:]
    rises = int(np.sum(created[1:] > created[:-1]))
    rank_u = np.empty(nrules, dtype=np.int64)
    rank_u[np.argsort(-created, kind='stable')] = np.arange(nrules)
    disp = np.abs(np.arange(nrules) - rank_u).mean() / nrules
    return dict(V=V, rules=nrules, rises=rises, disp=disp,
                first=[(sym[len(chars) + 1 + r], created[r])
                       for r in range(6)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', required=True)
    ap.add_argument('--corpus', default='work/camel/merged_training.txt')
    ap.add_argument('--stride', type=int, default=0)
    a = ap.parse_args()
    for d in a.dirs.split(','):
        m = measure(d, a.corpus, a.stride)
        print(f"{d}: V={m['V']}, rules={m['rules']}, "
              f"rises {m['rises']}/{m['rules'] - 1} "
              f"({100.0 * m['rises'] / (m['rules'] - 1):.1f}%), "
              f"mean |rank displacement| {100 * m['disp']:.1f}% of V (float32)")
        print("  first created: " +
              ', '.join(f"`{w}` {c:,}" for w, c in m['first']))


if __name__ == '__main__':
    main()
