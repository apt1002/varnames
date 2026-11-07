#!/usr/bin/env python3
"""The rule-pair encoding grid: three pairings crossed with eight number codes.

Each rule is a pair `(u, v)` of child ids, both below `N = nchars + i` for rule
`i`, and the file stores `V - nchars` of them (`MODEL_FORMAT.md` §3).  This
script prices the design's grid on the 8192-word rule list.

The first axis, the pairing:

    pair       store `u` and `v` separately
    triangle   store `(u + v)(u + v - 1) / 2 + u`
    square     store `(v - 1)^2 + u` if `u < v`, else `u (u - 1) + v`

The second axis, coding a number `x` known to lie in `[0, N)`:

    fixed      `ceil(log2 N)` bits
    variable   `L = floor(log2 N)`, `s = N - 2^L`: `L` bits for `x` if
               `x < 2^L`, else for `x - s`; one more bit when that field is
               ambiguous, which is exactly when `x >= 2^L - s`
    zipf       `b` bits of interval index, then the residual coded `variable`
               inside the interval; `base = 2^(-1/s_design)`, and the interval
               edges are `N (base^i - 1)/(base^B - 1)` for `i = 0 .. B`

The index is `floor(log_base(1 + (base^B - 1) x / N))`.  The design writes `B =
b`, which yields only `b` intervals and so wastes most of the `b`-bit field;
the script prices that reading (`narrow`) and the one that uses the field,
`B = 2^b` (`wide`), so the two can be compared.  Edges are rounded down to
integers once, and the decoder derives the same edges from `N`, `b` and `base`,
so the code is well defined; the residual is `variable` over the interval's
width.  At `base = 2` the edge is `N (2^i - 1) // (2^B - 1)` exactly, so a
decoder needs no floating point.

The design names three exponents; the bases it lists are 2, `exp(1)` and
`exp(0.5)`.  Under `base = 2^(-1/s)` the third corresponds to `s = -ln 4`, not
`-ln(sqrt 2)` (which would give `exp(2)`); the base is the meaningful parameter,
so the grid runs the stated bases and the footnote prices `exp(2)` for `pair`.

Usage:
    rule_encoding.py --dir work/tw8192ns
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw

BASES = (('base=2', 2.0), ('base=e', math.e), ('base=sqrt(e)', math.sqrt(math.e)))


def fixed_bits(x, N):
    return 0 if N <= 1 else max(1, int(N - 1).bit_length())


def variable_bits(x, N):
    """The variable-width code of `x` in `[0, N)`: `L` bits, plus one if needed."""
    if N <= 1:
        return 0
    L = int(math.floor(math.log2(N)))
    s = N - (1 << L)
    if s <= 0:
        return L
    if x < (1 << L):
        return L + (1 if x >= (1 << L) - s else 0)
    return L + 1                     # `x - s` is always in the ambiguous half


def zipf_edges(N, b, base, wide):
    """Integer interval edges `[e_0=0, ..., e_B=N]` of the Zipf code."""
    B = (1 << b) if wide else b
    top = base ** B
    if base == 2.0:                      # exact: no floating point in a decoder
        return [(N * ((1 << i) - 1)) // ((1 << B) - 1) for i in range(B + 1)]
    return [int(math.floor(N * (base ** i - 1.0) / (top - 1.0)))
            for i in range(B + 1)]


def zipf_bits(x, N, b, base, wide):
    """`b` bits for the interval, then `variable` bits inside it."""
    if N <= 1:
        return b
    edges = zipf_edges(N, b, base, wide)
    i = 0
    for i in range(len(edges) - 2, -1, -1):      # the interval that holds `x`
        if x >= edges[i]:
            break
    lo, hi = edges[i], edges[i + 1]
    w = max(1, hi - lo)
    r = min(max(x - lo, 0), w - 1)
    return b + variable_bits(r, w)


def triangle(u, v):
    return (u + v) * (u + v - 1) // 2 + u


def triangle_max(N):
    m = 2 * (N - 1)
    return m * (m - 1) // 2 + (N - 1)


def square(u, v):
    return (v - 1) ** 2 + u if u < v else u * (u - 1) + v


def square_max(N):
    vals = [(N - 1) ** 2 + u for u in range(min(N - 1, 4))]
    vals += [(N - 1) * (N - 2) + v for v in range(min(N - 1, 4))]
    return max(vals) if vals else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw8192ns')
    ap.add_argument('--all', action='store_true',
                    help='also print the exp(2) footnote rows')
    args = ap.parse_args()
    chars, rules, _sym = tw.load_dictionary(args.dir)
    nchars = len(chars)
    V = nchars + len(rules)
    m = len(rules)
    print(f'{args.dir}: {nchars} characters, {m} rules, V={V}')
    print(f'dictionary size is 2 x {m} = {2 * m} child indices')

    # the dictionary numbers characters 0..nchars-1, the stop nchars, the words
    # above it; the file drops the stop, so a word id and a bound both lose one
    def fid(i):
        return i if i < nchars else i - 1

    u = np.array([fid(a) for _kind, (a, b), _nid in rules], dtype=np.int64)
    v = np.array([fid(b) for _kind, (a, b), _nid in rules], dtype=np.int64)
    Ns = np.arange(nchars, nchars + m, dtype=np.int64)
    assert (u < Ns).all() and (v < Ns).all()
    tri = [(a + b) * (a + b - 1) // 2 + a for a, b in zip(u, v)]
    sq = [square(a, b) for a, b in zip(u, v)]
    triN = [triangle_max(n) for n in Ns]
    sqN = [square_max(n) + 1 for n in Ns]
    assert max(tri) < triangle_max(nchars + m - 1) + 1
    assert max(sq) < sqN[-1]

    rows = []

    def add(name, bits):
        total = float(np.sum(bits))
        rows.append((name, total / 8.0, total / (2 * m)))

    add('pair / fixed', [fixed_bits(a, n) + fixed_bits(b, n)
                         for a, b, n in zip(u, v, Ns)])
    add('pair / variable', [variable_bits(a, n) + variable_bits(b, n)
                            for a, b, n in zip(u, v, Ns)])
    tri = np.array(tri)
    sq = np.array(sq)
    add('triangle / fixed', [fixed_bits(t, n) for t, n in zip(tri, triN)])
    add('triangle / variable', [variable_bits(t, n)
                                for t, n in zip(tri, triN)])
    add('square / fixed', [fixed_bits(t, n) for t, n in zip(sq, sqN)])
    add('square / variable', [variable_bits(t, n) for t, n in zip(sq, sqN)])

    def zipf_row(pairing, b, base, wide):
        if pairing == 'pair':
            return [zipf_bits(a, n, b, base, wide) + zipf_bits(c, n, b, base, wide)
                    for a, c, n in zip(u, v, Ns)]
        if pairing == 'triangle':
            return [zipf_bits(t, n, b, base, wide) for t, n in zip(tri, triN)]
        return [zipf_bits(t, n, b, base, wide) for t, n in zip(sq, sqN)]

    for b in (2, 3):
        for label, base in BASES:
            for wide in (False, True):
                for pairing in ('pair', 'triangle', 'square'):
                    tag = (f'zipf b={b} {label}' + (' wide' if wide else ' ')
                           + f' / {pairing}')
                    add(tag, zipf_row(pairing, b, base, wide))
    if args.all:
        for b in (2, 3):
            for wide in (False, True):
                add(f'zipf b={b} base=e^2' + (' wide' if wide else ' ')
                    + ' / pair', zipf_row('pair', b, math.e ** 2, wide))

    best = min(r[1] for r in rows)
    print(f'\n{"encoding":<38} {"bytes":>8} {"bits/child":>11} {"vs best":>9}')
    for name, nbytes, bits_per in sorted(rows, key=lambda r: r[1]):
        print(f'{name:<38} {nbytes:>8,.0f} {bits_per:>11.3f} '
              f'{nbytes / best:>8.3f}x')

    N = nchars + m
    print(f'\nthe pairings at the last rule (N={N}):')
    print(f'  pair      {N * N:,} ordered pairs occupy {N * N:,} values')
    print(f'  triangle  {N * N:,} pairs occupy up to {triangle_max(N) + 1:,} '
          f'values ({(triangle_max(N) + 1) / (N * N):.2f} x the count)')
    print(f'  square    {N * (N - 1):,} distinct pairs occupy up to '
          f'{square_max(N) + 1:,} values ({(square_max(N) + 1) / (N * N):.2f} x'
          f' the count)')
    dup = len(set(sq.tolist())) != m
    print(f'  square is injective on this list: {not dup}')


if __name__ == '__main__':
    main()
