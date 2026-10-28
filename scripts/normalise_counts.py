#!/usr/bin/env python3
"""Case-normalise an occurrence-count file so it can be joined with the
case-normalised corpus (work/camel/merged.txt).

Reads a file of `identifier<TAB>count` lines (e.g. work/occ/all.counts) and
applies the same CamelCase normalisation used to build the corpus
(camelize_identifiers.to_camel), summing the counts of identifiers that
normalise to the same string.

Usage: normalise_counts.py INFILE OUTFILE
       (e.g. work/occ/all.counts work/occ/all.camel.counts)
"""
import sys

from camelize_identifiers import to_camel


def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else 'work/occ/all.counts'
    outfile = sys.argv[2] if len(sys.argv) > 2 else infile + '.camel'
    agg = {}
    n = 0
    with open(infile) as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            ident, _, cnt = line.rpartition('\t')
            if not ident:
                continue
            try:
                c = int(cnt)
            except ValueError:
                continue
            k = to_camel(ident)
            agg[k] = agg.get(k, 0) + c
            n += 1
    with open(outfile, 'w') as g:
        for k, c in agg.items():
            g.write(f"{k}\t{c}\n")
    print(f"read {n} distinct identifiers, {len(agg)} after normalisation")
    print(f"wrote {outfile}")


if __name__ == '__main__':
    main()
