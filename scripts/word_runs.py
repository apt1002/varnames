#!/usr/bin/env python3
"""Word-level runs: repeated *words*, not repeated characters.

A character run (`run_lengths.py`) is a maximal block of one repeated
character.  Once the corpus is tokenised into dictionary words, a **word-level
run** is a maximal block of one repeated *word* -- e.g. `Dot Dot Dot` inside
`BadDotDotDotSyntax`, or `Bucket Bucket` inside a generated SDK name.  This
reports how often they occur and what the repeated word is: a single character
or a multi-character pair word.

Usage:
    word_runs.py work/tw2040ns work/camel/merged_validation.txt
"""

import argparse
import sys
from collections import Counter
from itertools import groupby
from os.path import dirname, abspath

sys.path.insert(0, dirname(abspath(__file__)))
import tree_words as tw                                   # noqa: E402


def kinds(rules, nchars):
    """word id -> 'char' | 'pair'."""
    kind = {i: "char" for i in range(nchars)}
    for nid in range(nchars + 1, nchars + 1 + len(rules)):
        kind[nid] = "pair"
    return kind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dictionary")
    ap.add_argument("corpus")
    ap.add_argument("--stride", type=int, default=0)
    ap.add_argument("--examples", type=int, default=10)
    args = ap.parse_args()

    chars, rules, sym = tw.load_dictionary(args.dictionary)
    plan = tw.make_plan(rules, len(chars))
    char_id = {c: i for i, c in enumerate(chars)}
    nchars = len(chars)
    kind = kinds(rules, nchars)

    lines = tw.read_lines(args.corpus, stride=args.stride)

    char_runs = 0                       # raw character runs in the same corpus
    by_kind = Counter()                 # kind -> number of word-level runs
    mass_kind = Counter()               # kind -> sum (k-1)
    by_kind_len = {k: Counter() for k in ("pair",)}
    examples = {k: [] for k in ("pair",)}
    n_word_runs = 0

    for s in lines:
        for _ch, grp in groupby(s):
            if sum(1 for _ in grp) >= 2:
                char_runs += 1
        toks = tw.tokenize(s, char_id, plan, nchars)
        i, n = 0, len(toks)
        while i < n:
            j = i
            while j + 1 < n and toks[j + 1] == toks[i]:
                j += 1
            run = j - i + 1
            if run >= 2 and len(sym[toks[i]]) > 1:
                n_word_runs += 1
                k = kind[toks[i]]
                by_kind[k] += 1
                mass_kind[k] += run - 1
                by_kind_len[k][run] += 1
                if len(examples[k]) < args.examples:
                    examples[k].append((sym[toks[i]], run, s))
            i = j + 1

    print(f"dictionary: {args.dictionary}")
    print(f"corpus: {args.corpus}  ({len(lines):,} identifiers)")
    print()
    print(f"raw character runs (k>=2): {char_runs:,}")
    print(f"word-level runs (repeated multi-character word): {n_word_runs:,} "
          f"({100.0 * n_word_runs / max(char_runs, 1):.2f}% of character runs)")
    print()
    print("| repeated word kind | #runs | mass (k-1) | run-length histogram |")
    print("|---|---:|---:|---|")
    for k in ("pair",):
        hist = ", ".join(f"{kk}:{c}" for kk, c in sorted(by_kind_len[k].items()))
        print(f"| {k} word | {by_kind[k]:,} | {mass_kind[k]:,} | {hist or '-'} |")
    print()
    for k in ("pair",):
        if not examples[k]:
            continue
        print(f"examples ({k} word):")
        for w, run, s in examples[k]:
            print(f"   {w!r} x{run}   in  {s}")


if __name__ == "__main__":
    main()
