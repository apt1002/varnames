#!/usr/bin/env python3
"""Compute statistics for an identifier corpus and emit Markdown.

Usage:
    python3 stats.py CORPUS_FILE [--title TITLE]

Writes a Markdown report to stdout.
"""
import sys
import argparse
import collections
import statistics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    n = 0
    total_chars = 0
    max_len = 0
    max_token = ""
    lengths = []
    first = collections.Counter()
    chars = collections.Counter()
    starts_underscore = 0
    ends_digit = 0
    contains_underscore = 0
    all_caps = 0
    camel = 0
    has_digit = 0

    with open(args.corpus, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            t = line.rstrip("\n")
            if not t:
                continue
            n += 1
            L = len(t)
            total_chars += L
            lengths.append(L)
            first[t[0]] += 1
            chars.update(t)
            if L > max_len:
                max_len, max_token = L, t
            if t[0] == "_":
                starts_underscore += 1
            if t[-1].isdigit():
                ends_digit += 1
            if "_" in t:
                contains_underscore += 1
            if t.isupper():
                all_caps += 1
            if any(c.isdigit() for c in t):
                has_digit += 1
            # crude camelCase/PascalCase detector
            if any(c.isupper() for c in t[1:]):
                camel += 1

    lengths.sort()

    def pct(p):
        idx = min(int(len(lengths) * p / 100), len(lengths) - 1)
        return lengths[idx]

    title = args.title or args.corpus
    print(f"# Corpus statistics — `{title}`\n")
    print(f"| Metric | Value |")
    print(f"|---|---|")
    print(f"| Distinct identifiers | {n:,} |")
    print(f"| Total characters | {total_chars:,} |")
    print(f"| Mean length | {statistics.mean(lengths):.2f} |")
    print(f"| Median length | {statistics.median(lengths):.0f} |")
    print(f"| Min length | {min(lengths)} |")
    print(f"| Max length | {max_len:,} |")
    print(f"| Distinct characters | {len(chars)} |")
    print(f"| Starts with `_` | {starts_underscore:,} ({starts_underscore/n*100:.2f}%) |")
    print(f"| Contains `_` | {contains_underscore:,} ({contains_underscore/n*100:.2f}%) |")
    print(f"| Ends with a digit | {ends_digit:,} ({ends_digit/n*100:.2f}%) |")
    print(f"| Contains a digit | {has_digit:,} ({has_digit/n*100:.2f}%) |")
    print(f"| ALL_CAPS style | {all_caps:,} ({all_caps/n*100:.2f}%) |")
    print(f"| Contains inner capitals (camel/Pascal) | {camel:,} ({camel/n*100:.2f}%) |")
    print()
    print("## Length distribution\n")
    print("| Percentile | Length (chars) |")
    print("|---|---|")
    for p in (10, 25, 50, 75, 90, 95, 99, 99.9, 99.99):
        print(f"| p{p} | {pct(p)} |")
    print(f"| max | {max_len:,} |")
    print()
    print("## Length histogram\n")
    buckets = collections.Counter()
    for L in lengths:
        if L <= 8:
            buckets[L] += 1
        elif L <= 16:
            buckets["9-16"] += 1
        elif L <= 24:
            buckets["17-24"] += 1
        elif L <= 32:
            buckets["25-32"] += 1
        elif L <= 48:
            buckets["33-48"] += 1
        elif L <= 64:
            buckets["49-64"] += 1
        elif L <= 96:
            buckets["65-96"] += 1
        elif L <= 128:
            buckets["97-128"] += 1
        elif L <= 256:
            buckets["129-256"] += 1
        else:
            buckets[">256"] += 1
    order = [str(i) for i in range(1, 9)] + [
        "9-16", "17-24", "25-32", "33-48", "49-64", "65-96", "97-128", "129-256", ">256"
    ]
    print("| Length | Count | % of corpus |")
    print("|---|---|---|")
    for k in order:
        if buckets.get(k):
            print(f"| {k} | {buckets[k]:,} | {buckets[k]/n*100:.2f}% |")
    print()
    print("## Character frequency (top 20)\n")
    print("| Char | Occurrences | % of all chars |")
    print("|---|---|---|")
    for c, cnt in chars.most_common(20):
        print(f"| `{c}` | {cnt:,} | {cnt/total_chars*100:.2f}% |")
    print()
    print("## Leading character (top 15)\n")
    print("| Char | Identifiers | % of corpus |")
    print("|---|---|---|")
    for c, cnt in first.most_common(15):
        print(f"| `{c}` | {cnt:,} | {cnt/n*100:.2f}% |")
    print()
    if max_len > 128:
        long_count = sum(1 for L in lengths if L > 128)
        print(f"## Notes\n")
        print(f"- {long_count:,} identifiers exceed 128 characters; the longest is "
              f"{max_len:,} chars and is almost certainly an embedded blob "
              f"(base64 font/source-map data) rather than a real identifier.")
        print(f"- Longest token begins: `{max_token[:80]}...`")


if __name__ == "__main__":
    main()
