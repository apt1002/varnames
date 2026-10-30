#!/usr/bin/env python3
"""Split a one-identifier-per-line corpus into training and validation files.

Deterministic: line i (0-based) of the input goes to validation iff
``i % every == 0``, otherwise to training.  The default 10:1 split therefore
puts 10% of the lines in validation.  Used to build
``work/camel/merged_training.txt`` and ``work/camel/merged_validation.txt``
without shuffling (the input is already sorted, and the modulo rule is a cheap
way to interleave without materialising the file in memory).

Usage: split_corpus.py [IN] [TRAIN] [VALID] [--every N]
       (defaults: work/camel/merged.txt  work/camel/merged_training.txt
                  work/camel/merged_validation.txt  --every 10)
"""
import argparse
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('infile', nargs='?', default='work/camel/merged.txt')
    ap.add_argument('train', nargs='?', default='work/camel/merged_training.txt')
    ap.add_argument('valid', nargs='?', default='work/camel/merged_validation.txt')
    ap.add_argument('--every', type=int, default=10,
                    help='1 line in N goes to validation')
    args = ap.parse_args()

    n_tr = n_va = 0
    with open(args.infile, 'rb') as fin, \
         open(args.train, 'wb') as ftr, open(args.valid, 'wb') as fva:
        for i, line in enumerate(fin):
            if i % args.every == 0:
                fva.write(line if line.endswith(b'\n') else line + b'\n')
                n_va += 1
            else:
                ftr.write(line if line.endswith(b'\n') else line + b'\n')
                n_tr += 1
    print(f"train {n_tr} lines -> {args.train}")
    print(f"valid {n_va} lines -> {args.valid}")


if __name__ == '__main__':
    main()
