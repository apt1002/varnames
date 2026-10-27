#!/usr/bin/env python3
"""Merge the three identifier lists and remove duplicates.

Concatenates (in this order)
    <indir>/camel_case.txt
    <indir>/camel_from_lower.txt
    <indir>/camel_from_upper.txt
then sorts and de-duplicates them in byte order (LC_ALL=C) and writes the
result, one identifier per line.

Usage: merge_identifiers.py [INDIR] [OUTFILE]
       (defaults: work/camel  work/camel/merged.txt)
"""
import os
import subprocess
import sys


def main():
    indir = sys.argv[1] if len(sys.argv) > 1 else 'work/camel'
    outfile = sys.argv[2] if len(sys.argv) > 2 else os.path.join(indir, 'merged.txt')
    inputs = [os.path.join(indir, n)
              for n in ('camel_case.txt', 'camel_from_lower.txt',
                        'camel_from_upper.txt')]

    tmp = outfile + '.unsorted'
    with open(tmp, 'wb') as out:
        for p in inputs:
            with open(p, 'rb') as f:
                while True:
                    block = f.read(1 << 20)
                    if not block:
                        break
                    out.write(block)

    env = dict(os.environ)
    env['LC_ALL'] = 'C'
    subprocess.run(['sort', '-u', '-o', outfile, tmp], check=True, env=env)
    os.remove(tmp)

    with open(outfile, 'rb') as f:
        n = sum(1 for _ in f)
    print(f"merged {n} distinct identifiers -> {outfile}")


if __name__ == '__main__':
    main()
