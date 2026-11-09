#!/usr/bin/env python3
"""Classify a corpus of identifiers into lower_case / UPPER_CASE / CamelCase.

An identifier is *CamelCase* when it contains at least one lower-case cased
character AND at least one upper-case one (digits, underscores and inert
characters are ignored).  Otherwise it is *UPPER_CASE* when it contains an
upper-case one, and *lower_case* when it contains a lower-case one (or no cased
character at all).  The cased set is the one `STANDARD.md` §11 defines; the
implementation is `python/varnames/case.py`, shared with the library.

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'python'))
from varnames.case import classify    # noqa: E402  (the package is the source)


def main():
    corpus = sys.argv[1] if len(sys.argv) > 1 else 'corpus/identifiers.multilang.txt'
    outdir = sys.argv[2] if len(sys.argv) > 2 else 'work/camel'
    os.makedirs(outdir, exist_ok=True)

    outs = {
        'lower': open(os.path.join(outdir, 'lower_case.txt'), 'w', encoding='utf-8'),
        'upper': open(os.path.join(outdir, 'upper_case.txt'), 'w', encoding='utf-8'),
        'camel': open(os.path.join(outdir, 'camel_case.txt'), 'w', encoding='utf-8'),
    }
    counts = {'lower': 0, 'upper': 0, 'camel': 0}
    total = 0
    try:
        with open(corpus, encoding='utf-8') as f:
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
