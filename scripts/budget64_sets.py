#!/usr/bin/env python3
"""Measure the 64- and 128-bit identifier sets through the shipped codec.

The older study priced the sets with the `assoc` transition; this one encodes
every held-out identifier with the packed standard model, so the numbers are
the ones the standard actually delivers: 30,745 bytes, 45.218 bits per
identifier, 85.0 % within 64 bits.

    python3 scripts/budget64_sets.py
"""

import argparse
import collections
import random
import re
import sys

sys.path.insert(0, 'python')

import varnames  # noqa: E402

SYNTAX = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
FLAT = (123_401, 43.333, 86.9)      # (8,192, 16) flat yardstick, MODEL_BUDGET §7


def read_lines(path, stride):
    with open(path, 'r', encoding='ascii') as f:
        return [s for i, line in enumerate(f)
                if i % stride == 0 and (s := line.rstrip('\n'))]


def picture(name):
    """The markers of §3, as booleans."""
    return dict(
        underscore_cap=bool(re.search(r'_[A-Z]', name)),
        run_caps=bool(re.search(r'[A-Z]{2}', name)),
        underscore='_' in name,
        digit=any(c.isdigit() for c in name),
        no_vowel=not any(c in 'aeiouAEIOU' for c in name),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validation',
                    default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=10)
    ap.add_argument('--sample', type=int, default=50_000)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    codec = varnames.standard()
    names = read_lines(args.validation, args.stride)
    bits = []
    for name in names:
        value, length = codec.encode(name)
        assert codec.decode(value) == name
        bits.append(length)
    n = len(names)
    chars = [len(s) for s in names]
    print(f'n = {n}, mean chars {sum(chars) / n:.2f}, '
          f'mean bits {sum(bits) / n:.3f}')
    fit64 = sum(b <= 64 for b in bits)
    fit128 = sum(b <= 128 for b in bits)
    print(f'fit <=64 {100 * fit64 / n:.1f} %   fit <=128 {100 * fit128 / n:.1f} %')
    print(f'flat yardstick comparison: {FLAT[0]} B, {FLAT[1]} bits, '
          f'{FLAT[2]} % <=64')

    # ----------------------------------------------------------- the boundary
    fitters = [c for c, b in zip(chars, bits) if b <= 64]
    failers = [c for c, b in zip(chars, bits) if b > 64]
    print(f'\nlongest fitting {max(fitters)} chars, '
          f'shortest failing {min(failers)} chars')
    lo, hi = min(failers), max(fitters)
    inside = [c for c in failers if c <= hi]
    total_inside = sum(1 for c in chars if lo <= c <= hi)
    print(f'failures inside {lo}..{hi}: {len(inside)} of {total_inside} '
          f'({100 * len(inside) / total_inside:.1f} %)')

    buckets = collections.defaultdict(lambda: [0, 0])
    for c, b in zip(chars, bits):
        key = '1-8' if c <= 8 else '44+' if c >= 44 else str(c)
        buckets[key][0] += 1
        buckets[key][1] += b <= 64
    order = ['1-8'] + [str(i) for i in range(9, 44) if str(i) in buckets] + ['44+']
    print('\n| len | n | fit <=64 |')
    print('|---:|---:|---:|')
    for key in order:
        if key not in buckets:
            continue
        count, fit = buckets[key]
        print(f'| {key} | {count:,} | {100 * fit / count:.1f} % |')

    # the two ends of the overlap, in full
    fits = [(b, c, s) for s, b, c in zip(names, bits, chars) if b <= 64]
    fails = [(b, c, s) for s, b, c in zip(names, bits, chars) if b > 64]
    print('\nlongest fitting:')
    for b, c, s in sorted(fits, key=lambda t: (-t[1], -t[0]))[:4]:
        print(f'  {s}  {c} ch, {b} b')
    print('shortest failing:')
    for b, c, s in sorted(fails, key=lambda t: (t[1], -t[0]))[:4]:
        print(f'  {s}  {c} ch, {b} b')

    # ------------------------------------------------------------- what fails
    feats = {k: [0, 0] for k in
             ['underscore_cap', 'run_caps', 'underscore', 'digit', 'no_vowel']}
    for name, b in zip(names, bits):
        for key, present in picture(name).items():
            if present:
                feats[key][1 if b <= 64 else 0] += 1
    none = [0, 0]
    for name, b in zip(names, bits):
        if not any(picture(name).values()):
            none[1 if b <= 64 else 0] += 1
    print('\n| feature | fitters | failers | over-represented by |')
    print('|---|---:|---:|---:|')
    for key, (fail, fit) in list(feats.items()) + [('none', tuple(none))]:
        share_fit = fit / fit64
        share_fail = fail / (n - fit64)
        ratio = share_fail / share_fit if share_fit else float('inf')
        label = key if key == 'none' else f'`{key}`'
        print(f'| {label} | {100 * share_fit:.1f} % | {100 * share_fail:.1f} % | '
              f'{ratio:.1f}x |')

    # ------------------------------------------- a uniform draw from the set
    rng = random.Random(args.seed)
    reference = set(names)
    sizes, valid, real, lengths = 0, 0, 0, []
    examples = []
    for _ in range(args.sample):
        value = rng.getrandbits(64)
        name = codec.decode(value)
        lengths.append(len(name))
        valid += bool(SYNTAX.match(name))
        real += name in reference
        sizes += len(name)
        if len(examples) < 8 and SYNTAX.match(name):
            examples.append(name)
    k = args.sample
    if not k:
        return
    print(f'\nuniform 64-bit draw: mean len {sizes / k:.2f}, '
          f'syntax {100 * valid / k:.1f} %, real {100 * real / k:.2f} %')
    print('examples:', ', '.join(f'`{e}`' for e in examples))


if __name__ == '__main__':
    main()
