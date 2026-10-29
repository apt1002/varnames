#!/usr/bin/env python3
"""Per-identifier code length under the longest-suffix successor model.

For each identifier in IDLIST, wrap it as ^identifier$ and code its characters
(and the terminating '$') with the variable-order model defined by the common
substrings and their successor distributions:

    L(id) = sum_j  -log2 P(c_j | longest common substring that is a suffix of
                                   ^ c_1 ... c_{j-1})

where P(.|ctx) is the alpha-smoothed successor distribution of ctx and the
'#global' row supplies the distribution q used for the empty / backoff context.
L(id) is the ideal arithmetic-code length of id under the model, i.e. the number
of bits a model-based coder would spend; it is the natural estimate of whether
an identifier can be packed into a fixed budget such as 64 bits.

Inputs : IDLIST (one identifier per line), SUBS (common_substrings.txt),
         <outdir>/successor_distributions.tsv
Output : --lengths FILE (identifier <TAB> bits, default <outdir>/code_lengths.tsv)
         plus a summary on stdout.

Usage: code_lengths.py IDLIST SUBS [--outdir DIR] [--alpha 1.0] [--lengths FILE]
"""
import argparse
import os
import sys

import numpy as np

import winhash

B = 0x9E3779B97F4A7C15
CHUNK = 1 << 21
SYMS = (b"abcdefghijklmnopqrstuvwxyz"
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        b"0123456789_$")
NSYM = len(SYMS)


def hash_bytes(s):
    h = 0
    for b in s:
        h = (h * B + b) & 0xFFFFFFFFFFFFFFFF
    return h


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('idlist')
    ap.add_argument('substrings')
    ap.add_argument('--outdir', default='work/common10000')
    ap.add_argument('--alpha', type=float, default=1.0)
    ap.add_argument('--lengths', default='')
    args = ap.parse_args()

    # ---- vocabulary and per-context probabilities ------------------------
    vocab = []
    with open(args.substrings, 'rb') as f:
        for line in f:
            s = line.rstrip(b'\n')
            if s:
                vocab.append(s)
    vidx = {s: i for i, s in enumerate(vocab)}
    N = len(vocab)
    max_len = max(len(s) for s in vocab)

    q = None
    counts = {}
    with open(os.path.join(args.outdir, 'successor_distributions.tsv')) as f:
        header = f.readline().rstrip('\n').split('\t')
        assert header[2:] == [chr(c) for c in SYMS], "unexpected successor alphabet"
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if parts[0] == '#global':
                q = np.array([float(x) for x in parts[2:]], dtype=np.float64)
            else:
                key = parts[0].encode('latin1')
                if key in vidx:
                    counts[vidx[key]] = np.array([float(x) for x in parts[2:]],
                                                 dtype=np.float64)
    q = q / q.sum()
    D = np.tile(q, (N, 1))                       # default (unseen contexts) = q
    for vi, c in counts.items():
        n = c.sum()
        D[vi] = (c + args.alpha * q) / (n + args.alpha)
    logD = np.log2(np.maximum(D, 1e-300))
    logq = np.log2(np.maximum(q, 1e-300))
    print(f"contexts: {N}  loaded: {len(counts)}  max length: {max_len}  "
          f"H(q) = {entropy_bits(q):.4f} bits")
    if len(counts) < N:
        print(f"  note: {N - len(counts)} contexts have no successor row (use q)")

    # ---- longest-suffix lookup tables ------------------------------------
    by_len = {}
    for vi, s in enumerate(vocab):
        by_len.setdefault(len(s), []).append((winhash.hash_bytes(s), vi))
    Hs, Imap = {}, {}
    for l, lst in by_len.items():
        a = np.array([h for h, _ in lst], dtype=np.uint64)
        ix = np.array([vi for _, vi in lst], dtype=np.int32)
        o = np.argsort(a, kind='stable')
        Hs[l], Imap[l] = a[o], ix[o]
    lengths = sorted(by_len, reverse=True)

    sym_col = np.full(256, -1, dtype=np.int64)
    for i, c in enumerate(SYMS):
        sym_col[c] = i
    Bpow = winhash.bpow_table(max_len)

    # ---- stream the identifiers in blocks --------------------------------
    bits = []
    buf = bytearray()
    starts = []                                  # wrapped-start + 1 per identifier

    def flush():
        if not starts:
            return
        T = np.frombuffer(bytes(buf), dtype=np.uint8)
        n = T.shape[0]
        P = np.zeros(n + 2 * max_len, dtype=np.uint8)
        P[max_len:max_len + n] = T
        Q = winhash.prefix_q(P)
        ctxidx = np.full(n, -1, dtype=np.int32)
        with np.errstate(over='ignore'):
            for l in lengths:
                hw = (Q[max_len:max_len + n]
                      - Q[max_len - l:max_len - l + n] * Bpow[l])
                Hl = Hs[l]
                pos = np.searchsorted(Hl, hw)
                np.minimum(pos, Hl.shape[0] - 1, out=pos)
                hit = (Hl[pos] == hw) & (ctxidx < 0)
                if hit.any():
                    ctxidx[hit] = Imap[l][pos[hit]]
        col = sym_col[T]
        valid = col >= 0
        cost = np.zeros(n, dtype=np.float64)
        if valid.any():
            vi = np.nonzero(valid)[0]
            ci = ctxidx[vi]
            cc = col[vi]
            lg = np.where(ci >= 0, logD[ci, cc], logq[cc])
            cost[vi] = -lg
        idx = np.array(starts + [n], dtype=np.int64)
        bits.extend(np.add.reduceat(cost, idx[:-1]).tolist())
        buf.clear()
        starts.clear()

    with open(args.idlist, 'rb') as f:
        for line in f:
            ident = line.rstrip(b'\n')
            if not ident:
                continue
            starts.append(len(buf) + 1)
            buf += b'^' + ident + b'$\x00'
            if len(buf) >= CHUNK:
                flush()
    flush()

    bits = np.array(bits)
    out = args.lengths or os.path.join(args.outdir, 'code_lengths.tsv')
    with open(args.idlist, 'rb') as fi, open(out, 'w') as fo:
        fo.write('identifier\tbits\n')
        i = 0
        for line in fi:
            ident = line.rstrip(b'\n')
            if not ident:
                continue
            fo.write(ident.decode('latin1') + '\t' + '%.4f' % bits[i] + '\n')
            i += 1
    print(f"identifiers: {len(bits)}")
    print(f"bits: mean {bits.mean():.2f}  median {np.median(bits):.2f}  "
          f"p90 {np.percentile(bits, 90):.2f}  max {bits.max():.2f}")
    for budget in (64, 128):
        frac = float((bits <= budget).mean())
        print(f"  fit in {budget} bits: {100 * frac:.2f}%  "
              f"({int((bits <= budget).sum())} identifiers)")
    print(f"wrote {out}")


if __name__ == '__main__':
    main()
