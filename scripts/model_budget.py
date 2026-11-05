#!/usr/bin/env python3
"""Byte budget for the word-level model.

Estimates the *stored* size of the word model in bytes, so the `store = k^2+2V`
"numbers" convention of the clustering notes can be replaced by an end-to-end
byte count that includes the word list.

Objects stored by the decoder:

* **word list** -- the merge rules that build the vocabulary.  A pair rule
  `(uv)` stores its two children; a run rule stores the base symbol and the run
  lengths `k` for which a word `(u^k)` exists.  Rules are in creation order, so
  every child index is `< s`, the number of symbols defined when the rule is
  created; a child therefore costs `ceil(log2 s)` bits.  The 63 single
  characters are implicit in the identifier syntax and cost nothing.
* **unigram** -- the `V` word probabilities, one byte each (aggressively
  quantised; see `--bits`).
* **membership** -- the two maps word -> left cluster and word -> right
  cluster, `2V` labels of `ceil(log2 k)` bits each.
* **block** -- the `k x k` cluster-pair table, one byte per cell.

The program code itself is not included; add `--code` bytes to see the effect.

Usage:
    model_budget.py --dirs work/tw2040,work/tw4414,work/tw11694 \
                    --ks 52,105,210,420,840 --results work/c23_budget.csv
"""
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw


def _bits(n):
    return max(1, (int(n) - 1).bit_length()) if n > 1 else 0


def _zipf_bits(V, exponent):
    w = (np.arange(V) + 1.0) ** (-exponent)
    return w / w.sum()


def dictionary_bits(chars, rules, code='var'):
    """Cost of the merge rules under an index code.

    ``fixed``  every child index costs ``ceil(log2 V)`` bits;
    ``var``    every child index costs ``ceil(log2 s)`` bits, ``s`` = the
               number of symbols defined when the rule was created (children
               always precede their parent, so ``s <= V``);
    ``zipf``   a static arithmetic code whose prior is ``p(j) ~ (j+1)^-a``,
               truncated to ``[0, s)`` -- two parameters for the whole list.
    """
    V = len(chars) + 1 + len(rules)
    zipf = _zipf_bits(V, 0.7)
    s = len(chars) + 1                       # the stop symbol is id len(chars)
    bits = 0
    for item in rules:
        if item[0] == 'pair':
            _, (a, b), _nid = item
            if code == 'fixed':
                bits += 2 * _bits(V)
            elif code == 'zipf':
                bits += sum(-np.log2(zipf[j] / zipf[:s].sum())
                            for j in (a, b))
            else:
                bits += 2 * _bits(s)
            s += 1
    return bits, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', required=True,
                    help='comma list of dictionary directories')
    ap.add_argument('--ks', required=True, help='comma list of cluster counts')
    ap.add_argument('--bits', type=int, default=8,
                    help='bits per stored probability (default 8 = one byte)')
    ap.add_argument('--code', type=int, default=0,
                    help='bytes charged for the program code (default 0)')
    ap.add_argument('--index-code', default='var',
                    choices=('fixed', 'var', 'zipf'),
                    help='how the word-list child indices are coded')
    ap.add_argument('--results', default='',
                    help='optional CSV with columns V,k,store,assoc_bits '
                         '(e.g. work/c23_budget.csv) to print a byte frontier')
    args = ap.parse_args()

    nbytes = args.bits / 8.0
    info = {}
    for d in args.dirs.split(','):
        chars, rules, sym = tw.load_dictionary(d)
        V = len(sym)
        dbits, s = dictionary_bits(chars, rules, args.index_code)
        assert s == V, (s, V)
        info[V] = dict(dir=d, dict_b=dbits / 8.0, dict_bits=dbits,
                       nrule=len(rules), V=V)

    def total_b(V, k, code=0):
        m = info[V]
        dict_b = m['dict_b']
        uni_b = V * nbytes
        lab = _bits(k) / 8.0
        mem_b = 2 * V * lab
        blk_b = k * k * nbytes
        return dict(dict_b=dict_b, uni_b=uni_b, mem_b=mem_b, blk_b=blk_b,
                    code=code,
                    tot=dict_b + uni_b + mem_b + blk_b + code)

    for V, m in sorted(info.items()):
        print(f"\n{m['dir']}: V={V}, rules={m['nrule']}, "
              f"word list {m['dict_bits']} bits = {m['dict_b']:.1f} B "
              f"({m['dict_bits'] / max(1, m['nrule']):.1f} bits/rule)")
        print(f"  {'k':>5} {'wordlist':>9} {'unigram':>8} {'members':>8} "
              f"{'block':>9} {'TOTAL B':>9} {'KB':>8}")
        for k in [int(x) for x in args.ks.split(',')]:
            t = total_b(V, k, args.code)
            print(f"  {k:>5} {t['dict_b']:>9.1f} {t['uni_b']:>8.1f} "
                  f"{t['mem_b']:>8.1f} {t['blk_b']:>9.1f} "
                  f"{t['tot']:>9.1f} {t['tot'] / 1024:>8.2f}")

    if args.results:
        rows = []
        with open(args.results) as f:
            for r in csv.DictReader(f):
                V, k = int(r['V']), int(r['k'])
                if V not in info:
                    continue
                t = total_b(V, k, args.code)
                rows.append((t['tot'], V, k, float(r['assoc_bits']),
                             float(r.get('full_bits') or 'nan')))
        rows.sort()
        print(f"\nbyte frontier ({args.results}, kappa=300): rows sorted by "
              f"size; '*' = not beaten by any smaller row")
        print(f"  {'KB':>8} {'V':>6} {'k':>5} {'bits':>8} {'full':>8}")
        best = float('inf')
        for tot, V, k, bits, full in rows:
            star = ''
            if bits < best:
                best = bits
                star = ' *'
            print(f"  {tot / 1024:>8.2f} {V:>6} {k:>5} {bits:>8.3f} {full:>8.3f}{star}")
        for budget in (20, 50):
            adm = [r for r in rows if r[0] / 1024 <= budget]
            if adm:
                tot, V, k, bits, full = min(adm, key=lambda r: r[3])
                print(f"  best under {budget} kB: V={V}, k={k} -> "
                      f"{bits:.3f} bits ({tot / 1024:.2f} kB)")
            else:
                print(f"  best under {budget} kB: none")


if __name__ == '__main__':
    main()
