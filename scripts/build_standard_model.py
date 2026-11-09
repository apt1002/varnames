#!/usr/bin/env python3
"""Build the standard model file that the two implementations ship.

The standard is the one model of `MODEL_FORMAT.md` §7: a pair-merge
dictionary of `V = 8,191` symbols, `k = 32` clusters, `q = 1`, built from the
corpus in `work/tw8192ns` at `kappa = 300`, seed 1.  This script writes it, the
YAML beside it for human reading, and a checksum, so that the shipped bytes can
be audited and rebuilt.

    build_standard_model.py --dir work/tw8192ns --k 32 --out standard

Exit status is non-zero if the file does not round-trip through the reader.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_size as msz


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dir', default='work/tw8192ns')
    ap.add_argument('--k', type=int, default=32)
    ap.add_argument('--q', type=int, default=1)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default='standard')
    args = ap.parse_args()

    m = msz.build_model(args.dir, args.k, args.q, kappa=args.kappa,
                        seed=args.seed)
    buf, sections = msz.pack(m)

    back = msz.unpack(buf)
    for key in ('alphabet', 'memberships', 'bottom', 'top', 'rules'):
        a, b = m[key], back[key]
        if key == 'alphabet':
            assert a == b, 'alphabet differs after the round trip'
        elif key in ('memberships', 'bottom', 'top'):
            import numpy as np
            assert np.array_equal(np.asarray(a), np.asarray(b)), key
        else:
            assert [tuple(x) for x in a] == [tuple(x) for x in b], key

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, 'model.nvm1')
    with open(path, 'wb') as f:
        f.write(buf)
    digest = hashlib.sha256(buf).hexdigest()

    yaml_path = os.path.join(args.out, 'model.yaml')
    with open(yaml_path, 'w', encoding='ascii') as f:
        f.write(msz.model_yaml(m))

    print(f'wrote {path}: {len(buf)} bytes')
    print(f'  sha256 {digest}')
    print(f'  V={m["V"]} k={m["k"]} q={m["q"]} alphabet={len(m["alphabet"])} '
          f'rules={len(m["rules"])}')
    for name, size in sections.items():
        if not name.endswith('_bits'):
            print(f'    {name:<16} {size:>7}')
    print(f'  wrote {yaml_path}: {os.path.getsize(yaml_path)} bytes')


if __name__ == '__main__':
    main()
