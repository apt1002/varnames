#!/usr/bin/env python3
"""Why the weight bias is not a closed form: three small trees.

`MODEL_FORMAT.md` §3 stores every depth in four bits, so every tree's depths must
span at most 15 levels, and the build must get there by biasing the leaf weights
before the Huffman merge.  The bias is not a formula one can solve in one line,
and this script shows the three cases that say why:

1. the design's example, `[1, 2, 4, 8, 16]`, with a *one-bit* field — it does
   not tickle the bug, because the formulas are written for a 15-level span and
   this tree is nowhere near it;
2. the Fibonacci weights, which do: `q_min` is small enough that both stated
   formulas ask for no bias at all, and yet Huffman needs 19 levels;
3. the closed form that does work, `q_min >= phi^-15`, and why it costs too
   much — the build searches for the least bias instead.

Usage:
    depth_bias.py
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_size as msz

PHI = msz.PHI


def span(lens):
    return int(lens.max() - lens.min())


def stated_bias(w):
    """The two formulas of `MODEL_FORMAT.md` §3, on positive weights only."""
    live = w[w > 0]
    pmax, pmin = float(live.max()), float(live.min())
    ratio = max(0.0, (pmax - 32768.0 * pmin) / 32767.0)
    floor = float(live.sum()) / 32768.0 - pmin
    return max(0.0, ratio, floor)


def minimal_bias(w, target, hi=1e9):
    """The smallest bias that brings the span to `target` or less."""
    lo, best = 0.0, None
    if span(msz.huffman(w, stop_at=1)[0]) <= target:
        return 0.0
    while hi - lo > 1e-9:
        mid = (lo + hi) / 2
        if span(msz.huffman(w + mid, stop_at=1)[0]) <= target:
            best, hi = mid, mid
        else:
            lo = mid
    return best


def report(name, w, target):
    lens, _, _ = msz.huffman(w, stop_at=1)
    live = w[w > 0]
    qmin = float(live.min()) / float(live.sum())
    print(f'{name}: weights {[int(x) for x in w]}')
    print(f'  q_min {qmin:.3e} = 2^-{-math.log2(qmin):.2f}, '
          f'log_phi(1/q_min) {math.log(1 / qmin) / math.log(PHI):.2f}')
    print(f'  unbias  span {span(lens):2d}  depths {[int(x) for x in lens]}')
    b = stated_bias(w)
    lb, _, _ = msz.huffman(w + b, stop_at=1)
    print(f'  stated  bias {b:.3f}  span {span(lb):2d}  '
          f'{"FITS" if span(lb) <= target else "does not fit"} {target} bit'
          f'{"s" if target > 1 else ""}')
    bf = float(live.sum()) / PHI ** 15 - float(live.min())
    lf, _, _ = msz.huffman(np.where(w > 0, w + max(0.0, bf), w), stop_at=1)
    print(f'  phi^15  bias {max(0.0, bf):.3f}  span {span(lf):2d}  '
          f'{"FITS" if span(lf) <= target else "does not fit"} {target} bit'
          f'{"s" if target > 1 else ""}  (sufficient, over-flat)')
    need = minimal_bias(w, target)
    ln, _, _ = msz.huffman(w + need, stop_at=1)
    base = float((lens * w).sum() / w.sum())
    new = float((ln * (w + need)).sum() / (w + need).sum())
    print(f'  needed  bias {need:.3f}  span {span(ln):2d}  '
          f'cost {new - base:+.2f} bits/leaf\n')


def main():
    print('FIELD 4 BITS (span <= 15), the shipped rule\n')
    report('the design example', np.array([1.0, 2, 4, 8, 16]), 15)
    fib = [1, 1]
    while len(fib) < 20:
        fib.append(fib[-1] + fib[-2])
    report('20 Fibonacci weights', np.array(fib, dtype=float), 15)
    report('a long-tailed tail', np.array([1000.0] + [1] * 40), 15)

    print('FIELD 1 BIT (span <= 1), the question as asked\n')
    report('the design example', np.array([1.0, 2, 4, 8, 16]), 1)
    report('20 Fibonacci weights', np.array(fib, dtype=float), 1)

    print('random trees: is the phi^15 closed form ever not enough?')
    rng = np.random.default_rng(1)
    bad = 0
    for _ in range(2000):
        n = int(rng.integers(2, 60))
        w = np.exp(rng.normal(0, 2.0, n))
        w[rng.random(n) < 0.2] = 0.0
        if w.sum() == 0:
            continue
        b = stated_bias(w)
        b = max(b, float(w[w > 0].sum()) / PHI ** 15 - float(w[w > 0].min()))
        if span(msz.huffman(np.where(w > 0, w + b, w), stop_at=1)[0]) > 15:
            bad += 1
    print(f'  {bad} of 2000 trees needed more than the closed form')


if __name__ == '__main__':
    main()
