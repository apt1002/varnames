#!/usr/bin/env python3
"""Classify a corpus of identifiers into lower_case / UPPER_CASE / CamelCase.

An identifier is *CamelCase* when it contains at least one lower-case letter
AND at least one upper-case letter (digits and underscores are ignored).
Otherwise it is *UPPER_CASE* when it contains an upper-case letter, and
*lower_case* when it contains a lower-case letter (or no letters at all).

Input : a text file with one identifier per line.
Output: three text files, one identifier per line:
          <outdir>/lower_case.txt
          <outdir>/upper_case.txt
          <outdir>/camel_case.txt

Usage: classify_identifiers.py [CORPUS] [OUTDIR]
       (defaults: corpus/identifiers.multilang.txt  work/camel)
"""
import os
import sys


def classify(s):
    lower = upper = False
    for ch in s:
        if 'a' <= ch <= 'z':
            lower = True
        elif 'A' <= ch <= 'Z':
            upper = True
    if lower and upper:
        return 'camel'
    if upper:
        return 'upper'
    return 'lower'


def main():
    corpus = sys.argv[1] if len(sys.argv) > 1 else 'corpus/identifiers.multilang.txt'
    outdir = sys.argv[2] if len(sys.argv) > 2 else 'work/camel'
    os.makedirs(outdir, exist_ok=True)

    outs = {
        'lower': open(os.path.join(outdir, 'lower_case.txt'), 'w'),
        'upper': open(os.path.join(outdir, 'upper_case.txt'), 'w'),
        'camel': open(os.path.join(outdir, 'camel_case.txt'), 'w'),
    }
    counts = {'lower': 0, 'upper': 0, 'camel': 0}
    total = 0
    try:
        with open(corpus) as f:
            for line in f:
                s = line.rstrip('\n')
                if not s:
                    continue
                k = classify(s)
                outs[k].write(s + '\n')
                counts[k] += 1
                total += 1
    finally:
        for f in outs.values():
            f.close()

    print(f"input:   {corpus}")
    print(f"output:  {outdir}")
    print(f"  lower_case: {counts['lower']}")
    print(f"  UPPER_CASE: {counts['upper']}")
    print(f"  CamelCase:  {counts['camel']}")
    print(f"  total:      {total}")


if __name__ == '__main__':
    main()
