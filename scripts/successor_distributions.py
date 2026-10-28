#!/usr/bin/env python3
"""Estimate the successor distribution of every common substring.

Longest-suffix (variable-order) model
-------------------------------------
For each split of a wrapped identifier (^identifier$) we take the prefix up to
the split and find the *longest common substring* (see common_substrings.py)
that is a suffix of that prefix; the successor is the character at the split.
That (context, successor) pair is counted.  For example, at the split after
"^Ac" the successor is credited to "^Ac" (if that is common), not to "Ac" or
"c".

This differs from a plain "character after substring" count: each split
contributes to exactly one context, the longest one, so a short suffix such as
"c" only receives the positions where no longer common suffix applies.  The
splits run from just after the leading '^' (predicting the first character) to
just after the identifier (predicting the trailing '$').

The empty string is a common substring, but as every occurring single character
is common, it can never be the longest suffix; any such positions are counted
separately and reported as `unassigned` (expected to be zero).

Rows: every common substring except the empty string and those ending in '$'
(a '$' cannot appear inside a prefix).  The successor alphabet is
[a-z A-Z 0-9 _ $] ('^' can never follow anything).

Output is a dense count table (tab separated):

    #substring	sample_size	a	b	...	Z	0	...	9	_	$
    #global	<total>	<counts of the corpus-wide successor distribution q>
    Attribute	10956	...

The '#global' row is the global successor distribution over all split
positions, provided so that the clustering step can smooth sparse counts with a
shared Dirichlet prior.

Input : corpus (one identifier per line) and common-substring list.
Output: <outdir>/successor_distributions.tsv

Usage: successor_distributions.py CORPUS SUBSTRINGS [--outdir work/common10000]
"""
import argparse
import os
import sys

import numpy as np

import winhash

B = 0x9E3779B97F4A7C15            # same multiplier as common_substrings.py
NUL = 0
CHUNK = 1 << 21
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
    ap.add_argument('--outdir', default='work/common10000')
    args = ap.parse_args()

    # ---- vocabulary: every non-empty common substring --------------------
    vocab = []
    with open(args.substrings, 'rb') as f:
        for line in f:
            s = line.rstrip(b'\n')
            if s == b'':
                continue
            vocab.append(s)
    rows = [s for s in vocab if not s.endswith(b'$')]   # contexts that can occur
    vidx = {s: i for i, s in enumerate(vocab)}
    print(f"vocabulary: {len(vocab)}  output rows: {len(rows)}")

    text, nlines = build_text(args.corpus)
    T = np.frombuffer(text, dtype=np.uint8)
    N = T.shape[0]
    max_len = max(len(s) for s in vocab)
    print(f"identifiers: {nlines}  text bytes: {N}  max context length: {max_len}")

    sym_col = np.full(256, -1, dtype=np.int64)
    for i, c in enumerate(SYMS):
        sym_col[c] = i

    Bpow = winhash.bpow_table(max_len)

    # hashes of the common substrings, grouped by length
    by_len = {}
    for vi, s in enumerate(vocab):
        by_len.setdefault(len(s), []).append((winhash.hash_bytes(s), vi))
    Hs, Imap = {}, {}
    for l, lst in by_len.items():
        a = np.array([h for h, _ in lst], dtype=np.uint64)
        idx = np.array([vi for _, vi in lst], dtype=np.int32)
        order = np.argsort(a, kind='stable')
        a, idx = a[order], idx[order]
        if a.size > 1 and np.any(a[1:] == a[:-1]):
            print(f"warning: hash collision among length-{l} substrings", file=sys.stderr)
        Hs[l], Imap[l] = a, idx
    lengths = sorted(by_len, reverse=True)

    NCTX = len(vocab)
    counts = np.zeros((NCTX, NSYM), dtype=np.int64)
    glob = np.zeros(NSYM, dtype=np.int64)
    unassigned = 0

    # pad on both sides so left/right windows never run off T
    P = np.zeros(N + 2 * max_len, dtype=np.uint8)
    P[max_len:max_len + N] = T

    for p0 in range(0, N, CHUNK):
        p1 = min(p0 + CHUNK, N)
        nchunk = p1 - p0
        seg = P[p0:p1 + 2 * max_len]             # local s <-> T index p0+s-max_len
        Q = winhash.prefix_q(seg)
        ctxidx = np.full(nchunk, -1, dtype=np.int32)
        with np.errstate(over='ignore'):
            for l in lengths:                    # longest first
                hw = (Q[max_len:max_len + nchunk]
                      - Q[max_len - l:max_len - l + nchunk] * Bpow[l])
                Hs_l = Hs[l]
                pos = np.searchsorted(Hs_l, hw)
                np.minimum(pos, Hs_l.shape[0] - 1, out=pos)
                match = (Hs_l[pos] == hw) & (ctxidx < 0)
                if match.any():
                    ctxidx[match] = Imap[l][pos[match]]
        with np.errstate(over='ignore'):
            # succ + counts
            hit = ctxidx >= 0
            succ = T[p0:p1]
            col = sym_col[succ]
            valid = col >= 0
            unassigned += int((valid & ~hit).sum())
            if valid.any():
                glob += np.bincount(col[valid], minlength=NSYM)
                g = valid & hit
                if g.any():
                    flat = ctxidx[g].astype(np.int64) * NSYM + col[g]
                    counts += np.bincount(flat, minlength=NCTX * NSYM).reshape(NCTX, NSYM)

    total = int(counts.sum())
    print(f"split positions (valid): {int(glob.sum())}")
    print(f"assigned to a context:   {total}")
    print(f"unassigned (empty ctx):  {unassigned}")

    # ---- write ----
    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, 'successor_distributions.tsv')
    sym_hdr = '\t'.join(chr(c) for c in SYMS)
    with open(path, 'w') as f:
        f.write('#substring\tsample_size\t' + sym_hdr + '\n')
        f.write('#global\t%d\t' % int(glob.sum()) +
                '\t'.join(str(int(x)) for x in glob) + '\n')
        for s in rows:
            c = counts[vidx[s]]
            f.write(s.decode('latin1') + '\t' + str(int(c.sum())) + '\t' +
                    '\t'.join(str(int(x)) for x in c) + '\n')
    print(f"wrote {path}")


if __name__ == '__main__':
    main()
