#!/usr/bin/env python3
"""Audit `scripts/extract.py` scrubbing against real source trees.

The corpus is meant to contain identifiers only: string literals, heredocs,
comments, POD and numeric literals are blanked before tokenising.  This script
scans a source tree with exactly the production scrubber and reports files whose
*output* still contains tokens that look like leaked literal data (hex blobs,
UUID/hash fragments, digit-heavy blobs), quoting the surrounding source so the
missed construct can be identified.

Usage:
    python3 scripts/audit_extract.py work/gems_src --exts .rb,.erb --show 20
    python3 scripts/audit_extract.py work/rust_src --exts .rs --limit 2000

`--limit N` stops after N files.  Exit status is 0 when nothing is flagged (so
it can be used as a regression check on a small tree).
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as ex                                            # noqa: E402

HEX_BLOB = re.compile(r'^(?:[0-9a-f]{8,}|[0-9A-F]{8,})$')
UUIDISH = re.compile(r'^[0-9a-f]{6,}$')
DIGITS = re.compile(r'^[a-zA-Z_][0-9]{6,}$')


def suspicious(tok):
    """Return a reason string if `tok` looks like leaked literal data."""
    if HEX_BLOB.match(tok):
        return 'hex-blob'
    if tok.isdigit() and len(tok) >= 6:
        return 'digits'
    if DIGITS.match(tok):
        return 'digits'
    return None


def context(data, tok, width=70):
    """A printable snippet of `data` around the first occurrence of `tok`."""
    hit = data.find(tok.encode('ascii'))
    if hit < 0:
        return ''
    a = max(0, hit - width)
    b = min(len(data), hit + len(tok) + width)
    snip = data[a:b].decode('utf-8', 'replace')
    return snip.replace('\r', '').replace('\n', '\u00b6').replace('\t', ' ')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('roots', nargs='+')
    ap.add_argument('--exts', required=True, help='comma list, e.g. .rb,.erb')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--show', type=int, default=10,
                    help='quote this many examples (0 = counts only)')
    args = ap.parse_args()

    exts = {e if e.startswith('.') else '.' + e for e in args.exts.split(',')}
    files = flagged = 0
    toks = {}
    examples = []
    for path in ex.walk_files(args.roots, exts):
        if args.limit and files >= args.limit:
            break
        try:
            with open(path, 'rb') as fh:
                head = fh.read(65536)
                if b'\x00' in head:
                    continue
                data = head + fh.read()
        except OSError:
            continue
        files += 1
        clean = ex.scrub(data, os.path.splitext(path)[1].lower(), True, True)
        hits = []
        for tok in set(ex.IDENT_RX.findall(clean)):
            t = tok.decode('ascii')
            why = suspicious(t)
            if why:
                toks[why] = toks.get(why, 0) + 1
                hits.append(t)
        if hits:
            flagged += 1
            if len(examples) < args.show:
                t = sorted(hits)[0]
                examples.append((path, t, context(data, t)))
        if files % 20000 == 0:
            print(f'  {files} files, {flagged} flagged', file=sys.stderr)

    print(f'scanned {files} files, {flagged} flagged '
          f'({100.0 * flagged / max(files, 1):.2f}%)')
    for why, n in sorted(toks.items()):
        print(f'  {why}: {n} distinct tokens')
    for path, tok, snip in examples:
        print(f'\n{path}\n  token {tok!r}\n  ...{snip}...')
    return 0 if flagged == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
