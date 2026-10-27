#!/usr/bin/env python3
"""Estimate the successor distribution of every common substring.

For each common substring (see common_substrings.py) we count how often each
character immediately follows it in the wrapped corpus (^identifier$), giving an
empirical distribution over successors.

Substrings that end with '$' have no successor (the identifier is over) and are
omitted, as is the empty substring.  The successor alphabet is
[a-z A-Z 0-9 _ $] ('^' can never follow anything).

Output is a dense count table (tab separated):

    #substring	sample_size	a	b	...	Z	0	...	9	_	$
    #global	<total>	<counts of the corpus-wide successor distribution q>
    Attribute	10956	...

The '#global' row is the global successor distribution, provided so that the
clustering step can smooth sparse counts with a shared Dirichlet prior.

Input : corpus (one identifier per line) and common-substring list.
Output: <outdir>/successor_distributions.tsv

Usage: successor_distributions.py CORPUS SUBSTRINGS [--outdir work/camel]
"""
import argparse
import os
import sys

import numpy as np

B = 0x9E3779B97F4A7C15            # same multiplier as common_substrings.py
NUL = 0
CHUNK = 1 << 22
# characters that can follow a substring ('^' only ever starts an identifier)
SYMS = (b"abcdefghijklmnopqrstuvwxyz"
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        b"0123456789_$")
NSYM = len(SYMS)


def build_text(path):
    buf = bytearray()
    buf.append(NUL)
    n = 0
    with open(path, 'rb') as f:
        for line in f:
            ident = line.rstrip(b'\n')
            if not ident:
                continue
            buf += b'^' + ident + b'$'
            buf.append(NUL)
            n += 1
    return bytes(buf), n


def hash_bytes(s):
    h = 0
    for b in s:
        h = (h * B + b) & 0xFFFFFFFFFFFFFFFF
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/camel')
    args = ap.parse_args()

    pats = []
    with open(args.substrings, 'rb') as f:
        for line in f:
            s = line.rstrip(b'\n')
            if s == b'' or s.endswith(b'$'):
                continue                    # no successor
            pats.append(s)
    print(f"analysable common substrings: {len(pats)}")

    text, nlines = build_text(args.corpus)
    T = np.frombuffer(text, dtype=np.uint8)
    N = T.shape[0]
    print(f"identifiers: {nlines}  text bytes: {N}")

    sym_col = np.full(256, -1, dtype=np.int64)
    syms_arr = np.frombuffer(SYMS, dtype=np.uint8)
    for i, c in enumerate(SYMS):
        sym_col[c] = i
    glob = np.bincount(T[1:], minlength=256)[syms_arr].astype(np.int64)

    by_len = {}
    for s in pats:
        by_len.setdefault(len(s), []).append(s)
    max_len = max(by_len)

    counts = {}
    h = T.astype(np.uint64)                 # window hashes for length 1
    with np.errstate(over='ignore'):
        for L in range(1, max_len + 1):
            m = N - L + 1
            if L > 1:
                win = h[:m]
                np.multiply(win, np.uint64(B), out=win)
                for s in range(0, m, CHUNK):
                    e = min(s + CHUNK, m)
                    add = np.frombuffer(text, np.uint8, count=e - s,
                                        offset=(L - 1) + s).astype(np.uint64)
                    win[s:e] += add
            lpats = by_len.get(L)
            if not lpats:
                continue
            npats = len(lpats)
            ph = np.array([hash_bytes(s) for s in lpats], dtype=np.uint64)
            order = np.argsort(ph)
            phs = ph[order]
            lc = np.zeros((npats, NSYM), dtype=np.int64)
            view = h[:m]
            for s in range(0, m, CHUNK):
                e = min(s + CHUNK, m)
                chunk = view[s:e]
                idx = np.searchsorted(phs, chunk)
                np.minimum(idx, npats - 1, out=idx)
                hitf = phs[idx] == chunk
                if not hitf.any():
                    continue
                pos = np.nonzero(hitf)[0]           # positions within chunk
                patidx = order[idx[pos]]
                succ = T[s + pos + L]               # char after the match
                col = sym_col[succ]
                good = col >= 0                     # NUL etc. cannot happen
                if not good.any():
                    continue
                comb = patidx[good] * NSYM + col[good]
                lc += np.bincount(comb, minlength=npats * NSYM).reshape(npats, NSYM)
            for i, s in enumerate(lpats):
                counts[s] = lc[i]
            print(f"level {L}: {npats} substrings, "
                  f"{int(lc.sum())} successor samples")

    # ---- write ----
    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, 'successor_distributions.tsv')
    sym_hdr = '\t'.join(chr(c) for c in SYMS)
    with open(path, 'w') as f:
        f.write('#substring\tsample_size\t' + sym_hdr + '\n')
        f.write('#global\t%d\t' % int(glob.sum()) +
                '\t'.join(str(int(x)) for x in glob) + '\n')
        for s in pats:
            c = counts[s]
            f.write(s.decode('latin1') + '\t' + str(int(c.sum())) + '\t' +
                    '\t'.join(str(int(x)) for x in c) + '\n')
    print(f"wrote {path}")


if __name__ == '__main__':
    main()
