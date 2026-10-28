#!/usr/bin/env python3
"""Count identifier *occurrences* in a sample of source files.

The varnames corpus stores each distinct identifier once, so it cannot tell us
how often an identifier occurs in real code -- needed for the "dynamic" 64-bit
success rate.  This script samples source files from the same trees the corpus
was built from, scrubs each one with the corpus tokeniser (extract.scrub) and
counts every identifier occurrence with the corpus regex.

Output per ecosystem: <outdir>/<eco>.counts  (identifier <TAB> count, sorted)
Output combined    : <outdir>/all.counts

Usage: sample_occurrences.py [--outdir work/occ] [--per-eco 1500] [--seed 1]
                             [--max-bytes 2000000] [--eco NAME ...]
"""
import argparse
import collections
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract                                                   # noqa: E402

ECOSYSTEMS = {
    'ruby':       (['work/gems_src'], {'.rb', '.rake', '.gemspec', '.erb'}),
    'rust':       (['work/rust_src'], {'.rs'}),
    'go':         (['/usr/share/go-1.24/src'], {'.go'}),
    'python':     (['/usr/lib/python3.13', '/usr/lib/python3/dist-packages'],
                   {'.py', '.pyi', '.pyx'}),
    'javascript': (['/usr/share/javascript'], {'.js', '.mjs', '.jsx'}),
    'perl':       (['/usr/share/perl5', '/usr/lib/aarch64-linux-gnu/perl5'],
                   {'.pl', '.pm'}),
}


def gather(roots, exts):
    files = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if os.path.splitext(fn)[1] in exts:
                    files.append(os.path.join(dp, fn))
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default='work/occ')
    ap.add_argument('--per-eco', type=int, default=1500)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--max-bytes', type=int, default=2_000_000)
    ap.add_argument('--eco', action='append', default=[])
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    rng = random.Random(args.seed)
    names = args.eco or list(ECOSYSTEMS)
    combined = collections.Counter()
    for name in names:
        roots, exts = ECOSYSTEMS[name]
        files = gather(roots, exts)
        if not files:
            print(f"{name}: no files found, skipping", file=sys.stderr)
            continue
        sample = rng.sample(files, min(args.per_eco, len(files)))
        counts = collections.Counter()
        for path in sample:
            try:
                if os.path.getsize(path) > args.max_bytes:
                    continue
                data = open(path, 'rb').read()
            except OSError:
                continue
            ext = os.path.splitext(path)[1]
            try:
                data = extract.scrub(data, ext, True, True)
            except Exception:
                pass
            for m in extract.IDENT_RX.findall(data):
                counts[m] += 1
        combined.update(counts)
        with open(os.path.join(args.outdir, name + '.counts'), 'w') as f:
            for ident, c in sorted(counts.items()):
                f.write(ident.decode('latin1') + '\t' + str(c) + '\n')
        print(f"{name}: {len(sample)} files, {sum(counts.values())} occurrences, "
              f"{len(counts)} distinct", flush=True)

    with open(os.path.join(args.outdir, 'all.counts'), 'w') as f:
        for ident, c in sorted(combined.items()):
            f.write(ident.decode('latin1') + '\t' + str(c) + '\n')
    print(f"all: {sum(combined.values())} occurrences, {len(combined)} distinct")


if __name__ == '__main__':
    main()
