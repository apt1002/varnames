#!/usr/bin/env python3
"""Enumerate the "common substrings" of an identifier corpus.

Every identifier is wrapped as  ^identifier$  and the wrapped identifiers are
concatenated (separated by NUL bytes) so that every substring of every wrapped
identifier can be examined.  A substring is *common* when it occurs at least
THRESHOLD times across the whole corpus; the empty substring is common by
definition.

The search is an Apriori / BFS over substring length.  A substring of length L
can only be common if its length-(L-1) prefix is common, so common substrings
are grown one character at a time, starting from the common single characters.
Each level counts the occurrences of the candidate extensions with a 64-bit
polynomial hash of every window of the concatenated text (h_L = h_{L-1}*B + c,
mod 2^64).  Occurrence counts are exact up to 64-bit hash collisions, which are
negligible for a corpus of this size.

Input : text file with one identifier per line.
Output: <outdir>/common_substrings.txt  - one common substring per line
                                         (empty line = empty substring),
                                         sorted in byte order.
        <outdir>/common_substrings.tsv  - length<TAB>count<TAB>substring
and a verification report on stdout.

Usage: common_substrings.py INPUT [--threshold 10000] [--outdir work/common10000]
"""
import argparse
import os

import numpy as np

# every character that can occur in a wrapped identifier
ALPHABET = (b"abcdefghijklmnopqrstuvwxyz"
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            b"0123456789_^$")
# odd 64-bit multiplier (Knuth's golden-ratio constant)
B = 0x9E3779B97F4A7C15
NUL = 0
CHUNK = 1 << 22


def build_text(path):
    """Return (concatenated NUL-separated ^id$ text, number of identifiers)."""
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


def count_matches(win, csorted):
    """For each value in the sorted array `csorted`, count how many windows
    in `win` equal it.  Returns counts in the order of `csorted`."""
    m = csorted.shape[0]
    counts = np.zeros(m, dtype=np.int64)
    for s in range(0, win.shape[0], CHUNK):
        chunk = win[s:s + CHUNK]
        idx = np.searchsorted(csorted, chunk)
        np.minimum(idx, m - 1, out=idx)
        hit = csorted[idx] == chunk
        if hit.any():
            counts += np.bincount(idx[hit], minlength=m)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('infile')
    ap.add_argument('--threshold', type=int, default=10000)
    ap.add_argument('--outdir', default='work/common10000')
    args = ap.parse_args()
    K = args.threshold

    text, nlines = build_text(args.infile)
    T = np.frombuffer(text, dtype=np.uint8)
    N = T.shape[0]
    print(f"identifiers: {nlines}  text bytes: {N}  threshold: {K}")

    # ---- level 1: single characters ----
    byte_count = np.bincount(T, minlength=256)
    common = {b'': nlines}
    parents = []                       # (substring bytes, 64-bit hash)
    for b in ALPHABET:
        c = int(byte_count[b])
        if c >= K:
            common[bytes([b])] = c
            parents.append((bytes([b]), b))
    print(f"level 1: {len(parents)} common single characters")

    chars = np.frombuffer(ALPHABET, dtype=np.uint8).astype(np.uint64)
    A = chars.shape[0]
    Bc = np.uint64(B)

    h = T.astype(np.uint64)            # window hashes for length 1
    level = 1
    with np.errstate(over='ignore'):
        while parents:
            level += 1
            m = N - (level - 1)        # number of windows of this length
            if m <= 0:
                break
            win = h[:m]                # h[i] currently holds h_{level-1}
            np.multiply(win, Bc, out=win)
            for s in range(0, m, CHUNK):
                e = min(s + CHUNK, m)
                add = np.frombuffer(text, np.uint8, count=e - s,
                                    offset=(level - 1) + s).astype(np.uint64)
                win[s:e] += add

            parents_h = np.array([p[1] for p in parents], dtype=np.uint64)
            cand = np.repeat(parents_h, A) * Bc + np.tile(chars, len(parents))

            order = np.argsort(cand, kind='stable')
            counts_sorted = count_matches(win, cand[order])
            counts = np.empty_like(counts_sorted)
            counts[order] = counts_sorted

            keep = np.nonzero(counts >= K)[0]
            print(f"level {level}: {keep.size} common substrings "
                  f"(of {cand.shape[0]} candidates)")
            if keep.size == 0:
                break

            new_parents = []
            for i in keep:
                parent_str = parents[i // A][0]
                s = parent_str + bytes([int(chars[i % A])])
                common[s] = int(counts[i])
                new_parents.append((s, int(cand[i])))
            parents = new_parents

    # ---- write results ----
    os.makedirs(args.outdir, exist_ok=True)
    items = sorted(common.items())
    list_path = os.path.join(args.outdir, 'common_substrings.txt')
    tsv_path = os.path.join(args.outdir, 'common_substrings.tsv')
    with open(list_path, 'wb') as f:
        for s, _ in items:
            f.write(s + b'\n')
    with open(tsv_path, 'w') as f:
        f.write('length\tcount\tsubstring\n')
        for s, c in items:
            f.write(f"{len(s)}\t{c}\t{s.decode('latin1')}\n")

    # ---- verification ----
    print(f"\ncommon substrings: {len(common)}  "
          f"max length: {max(len(s) for s in common)}")
    missing = []
    if b'' not in common:
        missing.append('(empty)')
    for required in (b'^', b'$'):
        if required not in common:
            missing.append(required.decode())
    for b in range(256):
        if b == NUL:
            continue                    # NUL is only the internal separator
        if byte_count[b] > 0 and bytes([b]) not in common:
            missing.append(repr(chr(b)))
    if missing:
        print("MISSING basic common substrings:", ', '.join(missing))
    else:
        print("OK: the empty string, '^', '$' and every occurring single "
              "character are common substrings.")
    print(f"wrote {list_path}")
    print(f"wrote {tsv_path}")


if __name__ == '__main__':
    main()
