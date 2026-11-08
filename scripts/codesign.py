#!/usr/bin/env python3
"""Walk the first step of the codesign question (``docs/CODESIGN.md``).

The design sketch asks one diagnostic before anything clever: at a matched
number of cells, can an assignment chosen **only by the code term** beat the
one the build ships, which is chosen only by the model term?  With the
Hellinger term switched off the compound merge key *is* Huffman, so the
code-only endpoint is the two-smallest-mass merge down to `k` cells.

This script compares three assignments at `k = 32`, `q = 1`, everything else
identical (same dictionary, same `kappa`, same packing, same held-out sample):

  * the shipped assignment, read out of ``standard/model.nvm1``;
  * a fresh Hellinger assignment (the build's own `shared_labels`);
  * the mass-merge assignment — the code term with the fit term switched off.

For each it builds the real model, packs it, and encodes the held-out
identifiers through the packed file, so the numbers are file bytes and code
bits, not proxies.

    python3 scripts/codesign.py --dir work/tw8192ns
"""

import argparse
import heapq
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import model_fit_rates as mfr  # noqa: E402
import model_size as msz  # noqa: E402
import tree_words as tw  # noqa: E402


def mass_merge(masses, k):
    """Merge the two lightest cells until `k` remain — Huffman, top down.

    The code term of the compound key, with the fit term switched off.  Returns
    a label per word, numbered by the order the cells were created.
    """
    heap = [(float(m), i, [i]) for i, m in enumerate(masses)]
    heapq.heapify(heap)
    labels = np.zeros(len(masses), dtype=np.int64)
    serial = len(heap)
    while len(heap) > k:
        a = heapq.heappop(heap)
        b = heapq.heappop(heap)
        merged = a[2] + b[2]
        heapq.heappush(heap, (a[0] + b[0], serial, merged))
        serial += 1
    # number the surviving cells by creation order, so the labels are stable
    for label, (_mass, _serial, members) in enumerate(sorted(heap,
                                                            key=lambda t: t[1])):
        labels[members] = label
    return labels


def read_shipped(path, V):
    """The assignment the standard model ships, as a label per file id."""
    m = msz.unpack(open(path, 'rb').read())
    labels = np.asarray(m['memberships'], dtype=np.int64)
    assert labels.shape == (V,)
    return labels


def evaluate(name, model, seqs, k, q):
    buf, sections = msz.pack(model)
    back = msz.unpack(buf)                      # the decoder's view is the file
    lcl = np.asarray(back['memberships'], dtype=np.int64) // q
    bottom, top = msz.codes_from(back, lcl)
    bits = np.array([len(msz.encode(seq, back, lcl, bottom, top))
                     for seq in seqs], dtype=np.float64)
    print(f'  {name:<22} {len(buf):>7,} B  {bits.mean():8.3f} bits  '
          f'fit<=64 {100 * (bits <= 64).mean():5.1f}%  '
          f'fit<=128 {100 * (bits <= 128).mean():5.1f}%')
    return dict(name=name, bytes=len(buf), bits=float(bits.mean()),
                fit64=float((bits <= 64).mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw8192ns')
    ap.add_argument('--k', type=int, default=32)
    ap.add_argument('--q', type=int, default=1)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--model', default='standard/model.nvm1')
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=10)
    args = ap.parse_args()

    prepared = msz.prepared_matrix(args.dir, args.kappa)
    V, nchars = prepared['V'], prepared['nchars']
    c = prepared['Mw'].sum(0)
    print(f"{args.dir}: V={V}, k={args.k}, q={args.q}, kappa={args.kappa}")

    lines = tw.read_lines(args.validation, stride=args.stride)
    chars, rules, _ = tw.load_dictionary(args.dir)
    seqs = [[msz.to_file_id(s, nchars) for s in seq[:-1]]
            for seq in mfr.tokenise(lines, chars, rules, nchars)]
    del lines
    print(f'held-out n={len(seqs)}')

    shipped = read_shipped(args.model, V)
    hella = msz.shared_labels(prepared['Mw'], args.k,
                              np.random.default_rng(args.seed), 1.0)
    mass = mass_merge(c, args.k)

    print('assignment sizes:', {name: int(len(set(lab)))
                                for name, lab in (('shipped', shipped),
                                                  ('hellinger', hella),
                                                  ('mass', mass))})
    rows = []
    for name, labels in (('shipped', shipped), ('hellinger', hella),
                         ('mass-merge', mass)):
        model = msz.build_model(args.dir, args.k, args.q, kappa=args.kappa,
                                seed=args.seed, labels=labels,
                                prepared=prepared)
        rows.append(evaluate(name, model, seqs, args.k, args.q))

    base = rows[0]
    print('\nthe code term alone, against the shipped assignment:')
    for row in rows[1:]:
        print(f"  {row['name']:<22} {row['bits'] - base['bits']:+.3f} bits, "
              f"{100 * (row['fit64'] - base['fit64']):+.1f} points, "
              f"{row['bytes'] - base['bytes']:+d} B")


if __name__ == '__main__':
    main()
