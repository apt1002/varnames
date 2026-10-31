#!/usr/bin/env python3
"""Run-length statistics of the identifier corpus.

A *run* is a maximal block of one repeated character -- the `oo` in `book`, the
`---` in `a---b`.  A length-1 block is a character with no equal neighbour and
is not a run.  This reports the distribution of **maximal run lengths** `k >= 2`
over a corpus, the **run mass** (each run of length `k` contributes `k - 1`
adjacent `uu` bigrams), and how the mass splits across characters -- the
quantities behind the run-aware dictionary rule (`docs/DICTIONARY_RULES.md`,
`docs/TREE_WORDS.md` §9.1).

Counts are over *distinct* identifiers (the corpus has no occurrence weights),
so they are unweighted by how often an identifier occurs in real source.

Usage:
    run_lengths.py [corpus.txt]        # default corpus/identifiers.multilang.txt
    run_lengths.py --top 15 [corpus.txt]
"""

import argparse
from collections import Counter
from itertools import groupby


def runs_of(ident):
    """Yield (char, length) for every maximal run of length >= 2 in `ident`."""
    for ch, grp in groupby(ident):
        n = sum(1 for _ in grp)
        if n >= 2:
            yield ch, n


def analyse(path, top):
    n_id = 0
    n_chars = 0
    runs_by_len = Counter()          # k -> #runs of length k
    mass_by_char = Counter()         # char -> sum (k-1) over its runs
    runs_by_char = Counter()         # char -> #runs
    len_by_char = {}                 # char -> Counter of run lengths
    runs_per_id = Counter()          # #runs in an identifier -> #identifiers
    ids_with_run = 0
    pairs = set()                    # distinct (char, length) run words
    chars_with_runs = set()
    longest = []                     # (length, ident) for the few longest runs

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            ident = line.rstrip("\n")
            if not ident:
                continue
            n_id += 1
            n_chars += len(ident)
            n_runs = 0
            for ch, k in runs_of(ident):
                n_runs += 1
                runs_by_len[k] += 1
                runs_by_char[ch] += 1
                mass_by_char[ch] += k - 1
                len_by_char.setdefault(ch, Counter())[k] += 1
                pairs.add((ch, k))
                chars_with_runs.add(ch)
                if len(longest) < 12 or k > longest[0][0]:
                    longest.append((k, ident))
                    longest.sort(reverse=True)
                    del longest[12:]
            runs_per_id[n_runs] += 1
            if n_runs:
                ids_with_run += 1

    return dict(
        n_id=n_id, n_chars=n_chars, runs_by_len=runs_by_len,
        mass_by_char=mass_by_char, runs_by_char=runs_by_char,
        len_by_char=len_by_char, runs_per_id=runs_per_id,
        ids_with_run=ids_with_run, longest=longest,
        pairs=pairs, chars_with_runs=chars_with_runs,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", nargs="?", default="corpus/identifiers.multilang.txt")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    a = analyse(args.corpus, args.top)
    total_runs = sum(a["runs_by_len"].values())
    total_mass = sum((k - 1) * c for k, c in a["runs_by_len"].items())

    print(f"corpus: {args.corpus}")
    print(f"distinct identifiers: {a['n_id']:,}")
    print(f"characters: {a['n_chars']:,}")
    print(f"identifiers with >=1 run: {a['ids_with_run']:,} "
          f"({100 * a['ids_with_run'] / a['n_id']:.1f}%)")
    print(f"maximal runs (k>=2): {total_runs:,} "
          f"({total_runs / a['n_id']:.3f} per identifier)")
    print(f"run mass (sum k-1): {total_mass:,} "
          f"({total_mass / a['n_chars']:.4f} per character)")
    print(f"distinct run words (char, k): {len(a['pairs']):,} "
          f"over {len(a['chars_with_runs'])} characters")
    print(f"mean run length: {sum(k * c for k, c in a['runs_by_len'].items()) / total_runs:.3f}")
    print()

    print("| run length k | #runs | % of runs | mass (k-1)*#runs | % of mass |")
    print("|---:|---:|---:|---:|---:|")
    for k in sorted(a["runs_by_len"]):
        c = a["runs_by_len"][k]
        print(f"| {k} | {c:,} | {100 * c / total_runs:.1f}% | "
              f"{(k - 1) * c:,} | {100 * (k - 1) * c / total_mass:.1f}% |")
    print()

    print("| #runs in identifier | #identifiers |")
    print("|---:|---:|")
    for r in sorted(a["runs_per_id"])[:12]:
        print(f"| {r} | {a['runs_per_id'][r]:,} |")
    print()

    print(f"| char | #runs | mass (k-1) | k=2 | k=3 | k=4 | k=5 | k>=6 | max k |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for ch, mass in a["mass_by_char"].most_common(args.top):
        lc = a["len_by_char"][ch]
        ge6 = sum(c for k, c in lc.items() if k >= 6)
        disp = repr(ch)[1:-1] if ch == " " else ch
        print(f"| `{disp}` | {a['runs_by_char'][ch]:,} | {mass:,} | "
              f"{lc.get(2, 0):,} | {lc.get(3, 0):,} | {lc.get(4, 0):,} | "
              f"{lc.get(5, 0):,} | {ge6:,} | {max(lc)} |")
    print()

    print("longest runs (length, example identifier):")
    for k, ident in a["longest"][:8]:
        print(f"  {k:>3}  {ident}")


if __name__ == "__main__":
    main()
