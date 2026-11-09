#!/usr/bin/env python3
"""The size oracle: build a model, write its YAML, pack the binary, decode.

Every byte the budget quotes should come from this script rather than from a
formula (`docs/MODEL_BUDGET.md` §7).  One run builds the model that the shipped
format can express, writes it as the YAML of `standard/MODEL_FORMAT.md`, packs that
YAML into the binary form of `MODEL_FORMAT.md` §3, reports the actual bytes per
section, and then rounds held-out identifiers through the codes derived from the
*packed* file alone.

The build
---------
    dictionary (chars, merge rules)  ->  symbol ids in the file's numbering
    adjacency M                      ->  M_ref = M + kappa prior
    one label per word               ->  k clusters (the shared assignment)
    truncated Huffman per cluster    ->  q right clusters, depths inside them
    Huffman per left cluster         ->  k top trees of k*q leaves

Symbol numbering is the file's (`MODEL_FORMAT.md` §2): the characters are ids
`0 .. len(alphabet)-1` and the words follow.  There is no stop symbol in the
file, so `to_file_id` only has to drop the tokeniser's trailing stop.

The terminator
--------------
The stop is never written; the padding zeros are its codeword.  The padding meets
the *top* stage first, so each top tree carries one extra leaf: a zero-weight
**STOP** leaf 0, which is therefore the deepest leaf of that tree.  The bottoms
need no stop leaf — the identifier simply does not continue.  Both stages use
one convention, the mirror of DEFLATE's: the all-zeros codeword belongs to the
*first* leaf at the **maximum** depth, and the remaining codes are handed out in
ascending depth order from the far end of the space.  So the top STOP leaf takes
code 0, and the file needs no orientation table.  The orientation is derivable
from the depths and the labels alone, so nothing is stored for it;
`check_terminator` asserts it on the built model.

The start state
---------------
The corpus tokeniser emits a stop token, so its adjacency matrix is `V0 x V0`
with `V0 = V + 1` counting the stop.  The stop's *row* is the distribution of
the first token, so it survives as the start state and is folded into one top
tree; its *column* does not, because nothing is coded after the end of an
identifier.  The matrix is therefore `V0 x (V0-1)` = `(V+1) x V` — the
`V x (V+1)` of `MODEL_FORMAT.md` up to transposition — and the file has `V`
symbols.  The start state belongs to
left cluster 0 by convention; the build picks the cluster that codes the
first-token distribution cheapest and renumbers the labels so that one is 0.

`--flat` measures the flat yardstick instead: one Huffman tree per left cluster
over all `V` words, which is the upper bound `docs/MODEL_BUDGET.md` §5.3 prices
the factored code against.  Its `k·V` depths are not shippable.

Usage:
    model_size.py --dir work/tw512ns --k 16 --q 2
    model_size.py --dir work/tw8192ns --k 16 --q 2 --yaml work/model.yaml
"""
import argparse
import codecs
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import cluster_substrings_lib as csl
import model_fit_rates as mfr
from quarter_accounting import huffman

MAGIC = b'NVM1'
ZIPF_EXPONENT = 0.7


# ------------------------------------------------------------------ atomics

def ceil_log2(n):
    """Bits needed to hold the values 0..n-1."""
    return max(1, int(n - 1).bit_length()) if n > 1 else 0


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_varint(buf, pos):
    n = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return n, pos


class BitWriter:
    """LSB-first: bit *i* of the output is the *i*-th bit written."""

    def __init__(self):
        self.acc = 0
        self.n = 0
        self.total = 0
        self.out = bytearray()

    def put(self, value, width):
        self.total += width
        if width:
            self.acc |= (int(value) & ((1 << width) - 1)) << self.n
            self.n += width
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def finish(self):
        if self.n:
            self.out.append(self.acc & 0xFF)
        return bytes(self.out)


class BitReader:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0
        self.acc = 0
        self.n = 0
        self.total = 0          # bits handed out, for the length checks

    def get(self, width):
        while self.n < width:
            byte = self.buf[self.pos] if self.pos < len(self.buf) else 0
            self.pos += 1
            self.acc |= byte << self.n
            self.n += 8
        v = self.acc & ((1 << width) - 1)
        self.acc >>= width
        self.n -= width
        self.total += width
        return v


# ------------------------------------------------------- arithmetic coder

class ArithEncoder:
    """Witten-Neal-Cleary 32-bit arithmetic coder over cumulative counts."""

    MASK = 0xFFFFFFFF
    HALF = 0x80000000
    QUARTER = 0x40000000
    THREE = 0xC0000000

    def __init__(self):
        self.low = 0
        self.high = self.MASK
        self.pending = 0
        self.bits = 0
        self.out = bytearray()
        self._acc = 0
        self._n = 0

    def _emit(self, bit):
        self._acc = (self._acc << 1) | bit
        self._n += 1
        if self._n == 8:
            self.out.append(self._acc & 0xFF)
            self._acc = 0
            self._n = 0
        self.bits += 1

    def _emit_plus_pending(self, bit):
        self._emit(bit)
        for _ in range(self.pending):
            self._emit(1 - bit)
        self.pending = 0

    def encode(self, cum_lo, cum_hi, total):
        r = self.high - self.low + 1
        self.high = self.low + (r * cum_hi) // total - 1
        self.low = self.low + (r * cum_lo) // total
        while True:
            if self.high < self.HALF:
                self._emit_plus_pending(0)
            elif self.low >= self.HALF:
                self._emit_plus_pending(1)
                self.low -= self.HALF
                self.high -= self.HALF
            elif self.low >= self.QUARTER and self.high < self.THREE:
                self.pending += 1
                self.low -= self.QUARTER
                self.high -= self.QUARTER
            else:
                break
            self.low = (self.low << 1) & self.MASK
            self.high = ((self.high << 1) | 1) & self.MASK

    def finish(self):
        self.pending += 1
        self._emit_plus_pending(0 if self.low < self.QUARTER else 1)
        if self._n:
            self.out.append((self._acc << (8 - self._n)) & 0xFF)
        return bytes(self.out)


class ArithDecoder:
    MASK = 0xFFFFFFFF
    HALF = 0x80000000
    QUARTER = 0x40000000
    THREE = 0xC0000000

    def __init__(self, buf):
        self.buf = buf
        self.pos = 0
        self.low = 0
        self.high = self.MASK
        self.value = 0
        for _ in range(32):
            self.value = ((self.value << 1) | self._bit()) & self.MASK

    def _bit(self):
        i, j = divmod(self.pos, 8)
        self.pos += 1
        if i >= len(self.buf):
            return 0
        return (self.buf[i] >> (7 - j)) & 1

    def target(self, total):
        r = self.high - self.low + 1
        return ((self.value - self.low + 1) * total - 1) // r

    def update(self, cum_lo, cum_hi, total):
        r = self.high - self.low + 1
        self.high = self.low + (r * cum_hi) // total - 1
        self.low = self.low + (r * cum_lo) // total
        while True:
            if self.high < self.HALF:
                pass
            elif self.low >= self.HALF:
                self.low -= self.HALF
                self.high -= self.HALF
                self.value -= self.HALF
            elif self.low >= self.QUARTER and self.high < self.THREE:
                self.low -= self.QUARTER
                self.high -= self.QUARTER
                self.value -= self.QUARTER
            else:
                break
            self.low = (self.low << 1) & self.MASK
            self.high = ((self.high << 1) | 1) & self.MASK
            self.value = ((self.value << 1) | self._bit()) & self.MASK


def zipf_prefix(V, scale_bits=20):
    """Cumulative counts of the index prior p(j) ~ (j+1)^-0.7 over [0, V)."""
    w = (np.arange(V) + 1.0) ** (-ZIPF_EXPONENT)
    f = np.maximum(1, np.round(w / w.sum() * (1 << scale_bits))).astype(np.int64)
    return np.concatenate([[0], np.cumsum(f)])


# ------------------------------------------------------ the rule ladder

PHI = (1.0 + 5.0 ** 0.5) / 2.0

LADDER_B = 3            # index bits; the ladder has B = 2^b intervals
DEPTH_BITS = 4          # fixed by the format; the bias keeps every span <= 15


def variable_bits(x, N):
    """`x` in `[0, N)` as a variable-width integer: `L` bits, plus one if needed."""
    if N <= 1:
        return 0
    L = N.bit_length() - 1
    s = N - (1 << L)
    if x < (1 << L):
        return L + (1 if x >= (1 << L) - s else 0)
    return L + 1


def variable_put(bw, x, N):
    if N <= 1:
        return
    L, s = N.bit_length() - 1, N - (1 << (N.bit_length() - 1))
    if x < (1 << L):
        bw.put(x, L)
        if x >= (1 << L) - s:
            bw.put(0, 1)                # the ambiguous half: this is the low one
    else:
        bw.put(x - s, L)
        bw.put(1, 1)                    # the ambiguous half: this is the high one


def variable_get(br, N):
    if N <= 1:
        return 0
    L, s = N.bit_length() - 1, N - (1 << (N.bit_length() - 1))
    v = br.get(L)
    if v < (1 << L) - s:
        return v
    return v if br.get(1) == 0 else v + s


def ladder_edges(N, b=LADDER_B):
    """Interval edges of the base-2 geometric ladder over `[0, N)`, in integers.

    The i-th edge is `N (2^i - 1) / (2^B - 1)` with `B = 2^b`, so a decoder
    derives them from `N` and `b` alone — the code stores no table.
    """
    B = 1 << b
    den = (1 << B) - 1
    return [(N * ((1 << i) - 1)) // den for i in range(B + 1)]


def ladder_bits(x, N, b=LADDER_B):
    """`b` bits of interval index, then the residual as a variable integer."""
    if N <= 1:
        return 0
    edges = ladder_edges(N, b)
    i = 0
    for i in range((1 << b) - 1, -1, -1):
        if x >= edges[i]:
            break
    w = max(1, edges[i + 1] - edges[i])
    return b + variable_bits(min(max(x - edges[i], 0), w - 1), w)


def ladder_put(bw, x, N, b=LADDER_B):
    edges = ladder_edges(N, b)
    i = 0
    for i in range((1 << b) - 1, -1, -1):
        if x >= edges[i]:
            break
    bw.put(i, b)
    w = max(1, edges[i + 1] - edges[i])
    variable_put(bw, min(max(x - edges[i], 0), w - 1), w)


def ladder_get(br, N, b=LADDER_B):
    edges = ladder_edges(N, b)
    i = br.get(b)
    w = max(1, edges[i + 1] - edges[i])
    return edges[i] + variable_get(br, w)


# ------------------------------------------------------- canonical codes

def canonical_codes(depths, mode='max', complete=True):
    """Canonical codes for one tree, from the depths.

    ``mode='min'``: code 0 belongs to the lowest label at the minimum depth.
    ``mode='max'``: code 0 belongs to the lowest label at the maximum depth.

    ``complete=False`` admits a tree whose Kraft sum is below one, whose
    codewords leave holes in the space.  Such a code is still prefix-free and
    still decodable — nothing the encoder emits lands in a hole — but the holes
    are wasted code space.  It is passed for ``q > 1``, where a truncated build
    is only guaranteed to tile the space if each survivor's leaves land at the
    same depth: measured at ``q = 2`` on 8192/16 every tree *is* complete
    (Kraft 1.0000 on all 32), so the flag is a guard, not a cost.

    Returns ``codes`` as a list of ``(value, length)`` indexed by leaf position.
    """
    depths = [int(d) for d in depths]
    n = len(depths)
    if n == 0:
        return []
    codes = [(0, 0)] * n
    if mode == 'min':
        code = 0
        prev = None
        for i in sorted(range(n), key=lambda i: (depths[i], i)):
            L = depths[i]
            code = 0 if prev is None else (code + 1) << (L - prev)
            codes[i] = (code, L)
            prev = L
    else:
        maxd = max(depths)
        nxt = 0                       # next free value, in units of 2^-maxd
        for L in range(maxd, -1, -1):
            blk = 1 << (maxd - L)
            start = (nxt + blk - 1) // blk
            labels = [i for i in range(n) if depths[i] == L]
            for k, i in enumerate(labels):
                codes[i] = (start + k, L)
            nxt = (start + len(labels)) * blk
    # complete and prefix-free, checked without allocating the code space
    maxd = max(depths)
    total = sum(1 << (maxd - d) for d in depths)
    if complete:
        assert total == 1 << maxd, f'not complete: Kraft {total} != 2^{maxd}'
    else:
        assert total <= 1 << maxd, f'over-full: Kraft {total} > 2^{maxd}'
    spans = sorted((v << (maxd - L), 1 << (maxd - L)) for v, L in codes)
    free = 0
    for start, blk in spans:
        assert start == free, 'not prefix-free or not complete'
        free = start + blk
    if complete:
        assert free == 1 << maxd, 'codes do not cover the space'
    return codes


def codebook(codes):
    return {(L, v): i for i, (v, L) in enumerate(codes)}


def walk(book, maxlen, read_bit):
    if (0, 0) in book:              # a one-leaf tree: the word step is free
        return book[(0, 0)]
    v = 0
    for L in range(1, maxlen + 1):
        v = (v << 1) | read_bit()
        if (L, v) in book:
            return book[(L, v)]
    raise ValueError('no codeword within maxlen bits')


# ------------------------------------------------------------ the build

def huffman_trunc(weights, survivors, bias=False):
    """Huffman depths, stopping the merge at `survivors` trees.

    `quarter_accounting.huffman` returns one group when `n <= stop_at`; the
    truncation at `n` survivors must return `n` singletons instead.

    `bias` adds a depth-flattening offset to every leaf *before* the merge, so
    that each tree's depths span at most 15 levels and the field can be 4 bits
    (`MODEL_FORMAT.md` §3.1).  The span is a property of the whole distribution,
    not of its extremes, so the offset is not computed: it is bracketed by
    doubling, then bisected for the least value that holds every tree to 15.
    Zero-weight leaves are left alone: they are the terminator, and they must
    stay deepest.
    """
    n = len(weights)
    if survivors >= n:
        return np.zeros(n), 0.0, [[i] for i in range(n)]
    w = np.asarray(weights, dtype=np.float64)
    if not bias:
        return huffman(w, stop_at=survivors)
    live = w[w > 0]
    if live.size <= 1:
        return huffman(w, stop_at=survivors)
    pmax, pmin = float(live.max()), float(live.min())
    T = float(live.sum())

    def build(b):
        lens, cost, groups = huffman(np.where(w > 0, w + b, w),
                                     stop_at=survivors)
        return lens, cost, groups, int(lens.max()) - int(lens.min())

    lens, cost, groups, span = build(0.0)
    if span <= 15:                      # no flattening needed
        return lens, cost, groups

    # Bracket a working bias by doubling from a scale guess.  `phi^-15` is a
    # sufficient upper bound, so the doubling cannot run away.
    b = max((pmax - 32768.0 * pmin) / 32767.0, T * 2.0 ** -20)
    while span > 15:
        b *= 2.0
        lens, cost, groups, span = build(b)
        if b > T:
            raise AssertionError('the bias did not bring the span to 15')

    # Bisect the bracket for the least bias that works, so the tail is no
    # flatter than the 4-bit field requires.  The unbiased build failed, so 0
    # is the low end.
    lo = 0.0
    for _ in range(16):
        mid = 0.5 * (lo + b)
        lens2, cost2, groups2, span2 = build(mid)
        if span2 <= 15:
            b, lens, cost, groups, span = mid, lens2, cost2, groups2, span2
        else:
            lo = mid
    return lens, cost, groups
def to_file_id(i, nchars):
    """Build symbol id -> file symbol id.

    The build's own numbering has the stop as symbol `nchars`, because the
    corpus tokeniser emits it.  The file has no stop: its characters are ids
    `0 .. nchars-1` and its words follow, so every build id above the stop
    shifts down by one.
    """
    i = int(i)
    if i == nchars:
        raise ValueError('the stop is not a symbol of the file')
    return i if i < nchars else i - 1


def shared_labels(M, k, rng, weight=1.0, block=512):
    """One Hellinger k-means over the concatenated row and column profiles."""
    V = M.shape[0]
    r = M.sum(1)
    c = M.sum(0)
    X = np.empty((V, 2 * V), dtype=np.float32)
    for i0 in range(0, V, block):
        rows = M[i0:i0 + block]
        X[i0:i0 + block, :V] = np.sqrt(np.maximum(
            rows / np.maximum(r[i0:i0 + block, None], 1e-300), 0.0))
        col_profiles = M[:, i0:i0 + block].T       # (block, V): M[b, a]
        X[i0:i0 + block, V:] = weight * np.sqrt(np.maximum(
            col_profiles / np.maximum(c[i0:i0 + block, None], 1e-300), 0.0))
    labels, _centers, _inertia = csl.kmeans_sphere(X, r, k, rng)
    return labels.astype(np.int64)


def prepared_matrix(directory, kappa):
    """The build's matrix: prior added, stop column dropped, stop row kept.

    Returns `Mw` (V x V over the file's symbols), `start` (the V-vector of
    first-token counts, i.e. the old stop row), `end` (the stop column, i.e.
    how many identifiers *finish* with each symbol — used only by the ablation
    that gives the stop its true weight) and the dictionary.
    """
    chars, rules, _sym = tw.load_dictionary(directory)
    M, _uni, _, _, _ = hf.dense_matrix(directory)
    V0, nchars = M.shape[0], len(chars)
    stop = nchars
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = kappa * V0 * c0 / T0
    for i0 in range(0, V0, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del cb, r0
    # rows: the symbols, plus the start state (the old stop row); columns: the
    # symbols only.  A file id is a position in `keep`, so no shifting is left.
    keep = np.ones(V0, dtype=bool)
    keep[stop] = False
    keep_idx = np.flatnonzero(keep)
    start = M[stop, keep_idx].astype(np.float64)
    end = M[keep_idx, stop].astype(np.float64)
    Mw = M[np.ix_(keep_idx, keep_idx)]
    del M
    return dict(Mw=Mw, start=start, end=end, chars=chars, rules=rules,
                nchars=nchars, V=V0 - 1)


def build_model(directory, k, q, kappa=300.0, seed=1, shared=True,
                shared_weight=1.0, bias=True, labels=None, prepared=None,
                stop_weight=False):
    """Build the model tables from a dictionary directory.

    The file has no stop symbol.  The corpus tokeniser emits one, but it is not
    a symbol of the model: it has no bottom leaf, no membership and no depth.
    Its *row* of the adjacency matrix survives as the **start state**, which is
    what makes the first token's distribution available to the top stage; its
    column does not, because nothing is coded after the end of an identifier.
    So the matrix loses a row and a column: `V0 x (V0-1)` for `V0 = V + 1`
    tokens, which is the `V x (V+1)` of `MODEL_FORMAT.md` in its own numbering.

    The start state needs a left cluster, and it is fixed by convention: the
    identifier starts in left cluster 0.  The build chooses which cluster that
    is — the one whose top tree codes the first-token distribution cheapest —
    and then permutes the labels so it is numbered 0.
    """
    p = prepared or prepared_matrix(directory, kappa)
    Mw, start, chars, rules = p['Mw'], p['start'], p['chars'], p['rules']
    end = p['end'] if stop_weight else None
    V, nchars = p['V'], p['nchars']
    c = Mw.sum(0)                      # unigram: the column mass

    if labels is not None:
        # codesign: take the assignment as given and build the trees for it.
        lcl = rcl = np.asarray(labels, dtype=np.int64)
        assert lcl.shape == (V,), lcl.shape
    elif shared:
        lcl = rcl = shared_labels(Mw, k, np.random.default_rng(seed),
                                  shared_weight)
    else:
        lcl, _ = cw.cluster_axis(Mw, k, np.random.default_rng(seed), 0)
        rcl, _ = cw.cluster_axis(Mw, k, np.random.default_rng(seed + 1), 1)

    # ---- quarters: truncate each right cluster's Huffman build at q --------
    ql = np.zeros(V, dtype=np.int64)
    bot_depth = np.zeros(V, dtype=np.int64)
    empty = []
    for j in range(k):
        mem = np.flatnonzero(rcl == j)
        if mem.size == 0:
            empty.append(j)
            continue
        lens, _, groups = huffman_trunc(c[mem].astype(np.float64), q,
                                        bias=bias)
        for pos, i in enumerate(mem):
            bot_depth[i] = int(lens[pos])
        for gi, g in enumerate(groups):
            for i in g:
                ql[mem[i]] = j * q + gi
    kq = k * q
    lcl = ql // q if shared else lcl

    # ---- top trees: mass of each quarter after each left cluster ----------
    # Leaf 0 is a zero-weight STOP leaf: the padding decodes as it, so the
    # terminator lives in the top stage and every identifier ends for free.
    # `S[L][J]` is the mass from left cluster `L` into quarter `J`, so it must be
    # accumulated over the rows of `L`.  When the maps are shared, the quarters
    # of `L` are exactly `L*q .. L*q+q-1` and the two readings agree; when they
    # are separate, a quarter holds words of several left clusters and only the
    # row split is correct.
    S = np.zeros((k, kq))
    for L in range(k):
        rows = np.flatnonzero(lcl == L)
        if rows.size:
            S[L] = np.bincount(ql, weights=Mw[rows].sum(0), minlength=kq)

    # the stop's mass per left cluster, for the ablation that charges for it
    stopmass = (np.bincount(np.asarray(lcl, dtype=np.int64), weights=end,
                            minlength=k).astype(np.float64)
                if end is not None else None)

    def top_depths(Smass):
        out = np.zeros((k, kq + 1), dtype=np.int64)
        for L in range(k):
            w0 = 0.0 if stopmass is None else stopmass[L]
            w = np.concatenate([[w0], Smass[L]])
            lens, _, _ = huffman_trunc(w, 1, bias=bias)
            out[L] = lens.astype(np.int64)
        return out

    top_depth = top_depths(S)

    # ---- where does the identifier start?  Left cluster 0, chosen cheapest --
    # the start state enters the top stage as a distribution over quarters; the
    # bottom step is the same in every left cluster, so it cannot change argmin
    start_q = np.zeros(kq)
    np.add.at(start_q, ql, start)
    codes = [canonical_codes([int(x) for x in top_depth[L]])
             for L in range(k)]
    lens_L = np.array([[codes[L][1 + int(j)][1] for j in range(kq)]
                       for L in range(k)])
    L0 = int(np.argmin(lens_L @ start_q))
    S[L0] += start_q                          # the start state joins its tree
    top_depth = top_depths(S)

    # renumber so the start's left cluster is 0.  A label permutes the trees
    # *and* the leaves inside them, so both are reordered by the same `perm`.
    perm = np.arange(k)
    perm[0], perm[L0] = L0, 0
    ql = perm[ql // q] * q + ql % q
    # leaf `1 + J` holds quarter `J = j*q + g`, so relabelling right cluster
    # `j` as `perm[j]` moves that leaf to `1 + perm[j]*q + g` — not to `1 + perm[J]`,
    # which would truncate the tree whenever `q > 1`.
    if kq > 1:
        J = np.arange(kq)
        leaves = 1 + perm[J // q] * q + J % q
        top_depth = top_depth[perm][:, np.concatenate(([0], leaves))]
    else:
        top_depth = top_depth[perm]
    lcl = ql // q if shared else perm[lcl]

    rules_file = [(to_file_id(a, nchars), to_file_id(b, nchars))
                  for _kind, (a, b), _nid in rules]

    return dict(directory=directory, alphabet=''.join(chars),
                rules=rules_file, memberships=ql, bottom=bot_depth,
                top=top_depth, lcl=np.asarray(lcl, dtype=np.int64),
                V=V, k=k, q=q, nchars=nchars, start=L0, empty=empty,
                shared=shared)


# ------------------------------------------------------------- the YAML

def model_yaml(m):
    lines = ['format: varnames-model',
             # A JSON string is a valid YAML double-quoted scalar, and
             # json.dumps escapes everything above `~`: the published file
             # stays ASCII, so no editor or renormalising filter can change
             # which characters the alphabet means.
             f'alphabet: {json.dumps(m["alphabet"])}',
             f'left_clusters: {m["k"]}',
             f'right_clusters_per_left: {m["q"]}',
             'rules:']
    for a, b in m['rules']:
        lines.append(f'  - [{a}, {b}]')
    lines.append('memberships: [' + ', '.join(str(int(x))
                                               for x in m['memberships']) + ']')
    lines.append('bottom_trees:')
    for J in range(m['k'] * m['q']):
        # `memberships` is an ndarray in a built model and a list in the
        # self-test fixture, so index it rather than compare an array.
        ids = [i for i, c in enumerate(m['memberships']) if c == J]
        lines.append('  - [' + ', '.join(str(int(m['bottom'][i]))
                                         for i in ids) + ']')
    lines.append('top_trees:')
    for L in range(m['k']):
        lines.append('  - [' + ', '.join(str(int(x))
                                         for x in m['top'][L]) + ']')
    return '\n'.join(lines) + '\n'


def parse_flat_list(s):
    s = s.strip()
    assert s.startswith('[') and s.endswith(']'), s[:40]
    body = s[1:-1].strip()
    return [int(x) for x in body.split(',')] if body else []


def read_yaml(path):
    """An independent reader: reads the YAML back and checks the invariants.

    The file is ASCII by policy (`model_yaml` escapes above U+007E), so a
    `model.yaml` that is not ASCII is refused here rather than guessed at.
    """
    with open(path, encoding='ascii') as f:
        lines = [l.rstrip('\n') for l in f]
    m = {}
    section = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        stripped = line.strip()
        if not line.startswith(' '):
            key, _, rest = stripped.partition(':')
            rest = rest.split('#')[0].strip()
            section = None
            if key in ('rules', 'bottom_trees', 'top_trees'):
                m[key] = []
                section = key
                if rest:
                    m[key].append(parse_flat_list(rest))
            elif key == 'memberships':
                m[key] = parse_flat_list(rest)
            elif key == 'alphabet':
                m[key] = json.loads(rest)
            elif key == 'format':
                m[key] = rest
            else:
                m[key] = int(rest)
        else:
            assert section is not None, line
            m[section].append(parse_flat_list(stripped[1:].strip()))
    assert m['format'] == 'varnames-model', m['format']
    k, q = m['left_clusters'], m['right_clusters_per_left']
    nchars = len(m['alphabet'])
    V = nchars + len(m['rules'])
    assert len(m['memberships']) == V, (len(m['memberships']), V)
    assert len(m['bottom_trees']) == k * q
    assert len(m['top_trees']) == k
    total = 0
    for J, tree in enumerate(m['bottom_trees']):
        ids = [i for i in range(V) if m['memberships'][i] == J]
        assert len(tree) == len(ids), (J, len(tree), len(ids))
        total += len(tree)
        if tree:
            mx = max(tree)
            assert sum(1 << (mx - d) for d in tree) == 1 << mx, \
                f'bottom tree {J} is not complete'
    assert total == V, (total, V)
    for L, tree in enumerate(m['top_trees']):
        assert len(tree) == k * q + 1, (L, len(tree))
        mx = max(tree)
        assert sum(1 << (mx - d) for d in tree) == 1 << mx, \
            f'top tree {L} is not complete'
    seen = set()
    for i, (a, b) in enumerate(m['rules']):
        assert a != b and 0 <= a < nchars + i and 0 <= b < nchars + i
        assert (a, b) not in seen, f'rule {i} repeats an earlier rule'
        seen.add((a, b))
    bottom = np.zeros(V, dtype=np.int64)
    for J, tree in enumerate(m['bottom_trees']):
        ids = [i for i in range(V) if m['memberships'][i] == J]
        for i, d in zip(ids, tree):
            bottom[i] = d
    m.update(V=V, k=k, q=q, nchars=nchars, bottom=bottom,
             top=np.asarray(m['top_trees'], dtype=np.int64))
    return m


# ------------------------------------------------------------- the binary

def pack_rules(rules, V, nchars):
    """The ladder-coded rule table on its own: `(bytes, bits)`.

    Kept separate from `pack` so the other accounting scripts can charge the
    dictionary the price the file actually pays instead of a formula.  Child `j`
    of rule `i` lies in `[0, nchars + i)`, so the number's range is known at
    both ends and nothing is stored for the code.
    """
    bw = BitWriter()
    for i, pair in enumerate(rules):
        N = nchars + i
        for x in pair:
            ladder_put(bw, x, N)
    return bw.finish(), bw.total


def unpack_rules(buf, V, nchars):
    """Read the ladder stream back into `V - nchars` index pairs.

    The checks are the readers' (`MODEL_FORMAT.md` §2, invariant 5): a child
    must exist, a rule may not name one child twice, and no two rules may name
    the same pair.  A stream read past its end looks like the last two, since
    padding zeros decode as `(0, 0)`.
    """
    br = BitReader(buf)
    rules = []
    seen = set()
    for i in range(V - nchars):
        N = nchars + i
        a, b = ladder_get(br, N), ladder_get(br, N)
        assert a < N and b < N, f'rule {i} names a child that does not exist'
        assert a != b, f'rule {i} names the same child twice'
        assert (a, b) not in seen, f'rule {i} repeats an earlier rule'
        seen.add((a, b))
        rules.append((a, b))
    assert (br.total + 7) // 8 == len(buf), \
        'the rule table is not the length of its rules'
    return rules


def depth_offsets(depths):
    """Depths of one tree as `depth - min`, which is what the field holds.

    The decoder recovers the offset because every tree is complete:
    `sum 2^-depth = 1`, so with `depth = o + delta`, `2^o = sum 2^-delta`.
    """
    if not depths:                  # an empty right cluster has no depths
        return [], 0
    lo = min(int(d) for d in depths)
    return [int(d) - lo for d in depths], lo


def depth_from_offsets(deltas):
    """The inverse: `sum 2^-delta` is a power of two and its exponent is `o`."""
    if not deltas:
        return []
    total = sum(1 << (15 - int(x)) for x in deltas)
    o = total.bit_length() - 1 - 15
    assert total == 1 << (o + 15), f'Kraft {total} is not 2^{o + 15}'
    return [int(x) + o for x in deltas]


def pack(m, depth_bits=DEPTH_BITS, packed_rules=True):
    """Pack the model into MODEL_FORMAT.md §3.  Returns (bytes, sections)."""
    V, k, q = m['V'], m['k'], m['q']
    nchars = len(m['alphabet'])
    kq = k * q
    sections = {}

    # the rule table comes first because its length is stored
    if packed_rules:
        rules_data, rule_bits = pack_rules(m['rules'], V, nchars)
    else:
        bw = BitWriter()
        width = ceil_log2(V)
        for pair in m['rules']:
            for x in pair:
                bw.put(x, width)
        rules_data = bw.finish()
        rule_bits = width * 2 * len(m['rules'])

    out = bytearray()

    def add(name, data):
        sections[name] = len(data)
        out.extend(data)

    add('magic', MAGIC)
    add('header', varint(V) + varint(k) + varint(q) + varint(nchars))
    add('rules_length', varint(len(rules_data)))
    add('rules', rules_data)
    sections['rules_bits'] = rule_bits
    add('alphabet', m['alphabet'].encode('utf-8'))

    width = ceil_log2(kq)
    bw = BitWriter()
    for label in m['memberships']:
        bw.put(int(label), width)
    add('memberships', bw.finish())
    sections['membership_bits'] = width

    # the depths: 4 bits each, as offsets inside their own tree.  The offset is
    # not stored — the Kraft equality of a complete tree fixes it (below).
    widths = []
    bw = BitWriter()
    for J in range(kq):
        ids = np.flatnonzero(np.asarray(m['memberships']) == J)
        deltas, _o = depth_offsets([int(m['bottom'][i]) for i in ids])
        widths += deltas
        assert not deltas or max(deltas) <= 15, \
            f'bottom tree {J} spans {max(deltas)} levels: needs the weight bias'
        for d in deltas:
            bw.put(d, depth_bits)
    add('bottom_depths', bw.finish())
    bw = BitWriter()
    for L in range(k):
        deltas, _o = depth_offsets([int(x) for x in m['top'][L]])
        widths += deltas
        assert max(deltas) <= 15, \
            f'top tree {L} spans {max(deltas)} levels: needs the weight bias'
        for d in deltas:
            bw.put(d, depth_bits)
    add('top_depths', bw.finish())
    sections['depth_bits'] = depth_bits

    return bytes(out), sections


def decode_alphabet(buf, pos, nchars):
    """Read `nchars` characters of UTF-8: `(alphabet, bytes used)`.

    The header stores the number of *characters*, not the number of bytes.
    UTF-8 is self-delimiting, so the section ends where the `nchars`-th
    character ends and no second length is needed.  An ASCII alphabet is one
    byte a character, which is why the shipped model's section is still
    `len(alphabet)` bytes.
    """
    dec = codecs.getincrementaldecoder('utf-8')()
    out = []
    used = 0
    while len(out) < nchars:
        if pos + used >= len(buf):
            raise ValueError('truncated alphabet')
        try:
            ch = dec.decode(buf[pos + used:pos + used + 1])
        except UnicodeDecodeError:
            raise ValueError('the alphabet is not valid UTF-8') from None
        used += 1
        if ch:
            out.append(ch)
    return ''.join(out), used


def unpack(buf, packed_rules=True):
    """Read the binary back; the only thing the decoder sees."""
    assert buf[:4] == MAGIC, 'bad magic'
    pos = 4
    V, pos = read_varint(buf, pos)
    k, pos = read_varint(buf, pos)
    q, pos = read_varint(buf, pos)
    nchars, pos = read_varint(buf, pos)
    rules_len, pos = read_varint(buf, pos)
    kq = k * q
    if packed_rules:
        rules = unpack_rules(buf[pos:pos + rules_len], V, nchars)
        for i, (a, b) in enumerate(rules):
            assert a < nchars + i and b < nchars + i, (i, a, b)
    else:
        br = BitReader(buf[pos:pos + rules_len])
        width = ceil_log2(V)
        children = [br.get(width) for _ in range(2 * (V - nchars))]
        rules = [tuple(children[2 * i:2 * i + 2])
                 for i in range(V - nchars)]
    pos += rules_len
    alphabet, used = decode_alphabet(buf, pos, nchars)
    pos += used

    width = ceil_log2(kq)
    nbytes = (V * width + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    memberships = np.array([br.get(width) for _ in range(V)])
    assert len(memberships) == V and memberships.max() < kq

    depth_bits = DEPTH_BITS          # fixed by the format, not stored
    nbytes = (V * depth_bits + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    bottom = np.zeros(V, dtype=np.int64)
    for J in range(kq):
        ids = np.flatnonzero(memberships == J)
        deltas = [br.get(depth_bits) for _ in ids]
        for i, d in zip(ids, depth_from_offsets(deltas)):
            bottom[i] = d
    nbytes = (k * (kq + 1) * depth_bits + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    top = np.zeros((k, kq + 1), dtype=np.int64)
    for L in range(k):
        deltas = [br.get(depth_bits) for _ in range(kq + 1)]
        top[L] = depth_from_offsets(deltas)
    assert pos == len(buf), (pos, len(buf))
    return dict(alphabet=alphabet, rules=[list(p) for p in rules],
                memberships=list(memberships), bottom=bottom, top=top,
                V=V, k=k, q=q, nchars=nchars)


# ------------------------------------------------------------ the codes

def codes_from(m, lcl):
    """Canonical codes for every tree, with the terminator on all zeros."""
    k, kq = m['k'], m['k'] * m['q']
    memberships = np.asarray(m['memberships'])
    bottom = {}
    for J in range(kq):
        ids = np.flatnonzero(memberships == J)
        if ids.size == 0:
            bottom[J] = None
            continue
        depths = [int(m['bottom'][i]) for i in ids]
        coded = canonical_codes(depths, mode='max', complete=(m['q'] == 1))
        bottom[J] = dict(ids=[int(i) for i in ids], codes=coded,
                         book=codebook(coded), maxlen=max(depths))
    top = {}
    for L in range(k):
        depths = [int(x) for x in m['top'][L]]      # position 0 = the STOP leaf
        coded = canonical_codes(depths, mode='max')
        top[L] = dict(codes=coded, book=codebook(coded), maxlen=max(depths))
    return bottom, top


def check_terminator(m):
    """The conditions that make the padding decode as the terminator."""
    problems = []
    for L in range(m['k']):
        dep = [int(x) for x in m['top'][L]]
        if len(dep) > 1 and dep[0] != max(dep):
            problems.append(f'top tree {L}: the STOP leaf is at depth {dep[0]}, '
                            f'not the maximum {max(dep)}')
    return problems


def encode(seq, m, lcl, bottom, top, write_stop=False):
    """Bits of one identifier.

    `seq` is a list of file symbol ids — there is no stop among them.  The code
    alternates (right cluster | left cluster) and (symbol | right cluster),
    starting in left cluster 0, and ends with the STOP leaf of the last top
    tree.  The STOP codeword is all zeros, so writing it changes nothing: the
    padding supplies it, and the trailing zeros of the last real codeword are
    not stored either.  `write_stop` keeps them, for the nominal-length count.
    """
    bits = []

    def put(code):
        v, L = code
        for pos in range(L - 1, -1, -1):
            bits.append((v >> pos) & 1)

    L = 0
    for v in seq:
        J = int(m['memberships'][v])
        put(top[L]['codes'][1 + J])
        e = bottom[J]
        put(e['codes'][e['ids'].index(int(v))])
        L = int(lcl[v])
    put(top[L]['codes'][0])          # the STOP leaf: all zeros
    if write_stop:
        return bits
    while bits and bits[-1] == 0:
        bits.pop()
    return bits


def decode(bits, m, lcl, bottom, top, limit=100000):
    it = iter(bits)

    def read_bit():
        return next(it, 0)          # past the end: padding zeros

    out = []
    L = 0
    for _ in range(limit):
        slot = walk(top[L]['book'], top[L]['maxlen'], read_bit)
        if slot == 0:
            return out
        J = slot - 1
        e = bottom[J]
        if e is None:
            raise ValueError(f'right cluster {J} is empty')
        v = e['ids'][walk(e['book'], e['maxlen'], read_bit)]
        out.append(v)
        L = int(lcl[v])
    raise ValueError('did not terminate')


def flat_model(directory, k, kappa=300.0, seed=1):
    """The flat yardstick: one Huffman tree per left cluster over all `V` words.

    This is the code `ENCODING.md` 2 describes, at `q = 1`: each left cluster
    has one tree of `V + 1` leaves, one per word plus the zero-weight STOP leaf
    that terminates the identifier.  It is not shippable (`k*V` depths instead
    of `V`) and exists to bound what a Huffman code can do at the same
    `(V, k)` under the shipped convention.
    """
    p = prepared_matrix(directory, kappa)
    Mw, start = p['Mw'], p['start']
    V, nchars = p['V'], p['nchars']
    lcl, _ = cw.cluster_axis(Mw, k, np.random.default_rng(seed), 0)
    G = np.zeros((k, V))
    np.add.at(G, lcl, Mw)
    del Mw

    def one_tree(L):
        w = np.concatenate([[0.0], G[L].astype(np.float64)])
        lens, _, _ = huffman_trunc(w, 1)
        return lens.astype(np.int64)

    depths = np.zeros((k, V + 1), dtype=np.int64)       # position 0 = STOP
    for L in range(k):
        depths[L] = one_tree(L)
    # the start state joins the left cluster that codes it cheapest, then that
    # cluster is renumbered 0 — the same convention as the shipped build
    codes = [canonical_codes([int(x) for x in depths[L]]) for L in range(k)]
    lens_L = np.array([[codes[L][1 + int(v)][1] for v in range(V)]
                       for L in range(k)])
    L0 = int(np.argmin(lens_L @ start))
    G[L0] += start
    depths[L0] = one_tree(L0)
    perm = np.arange(k)
    perm[0], perm[L0] = L0, 0
    lcl = perm[lcl]
    depths = depths[perm]
    return dict(depths=depths, lcl=lcl, k=k, V=V, nchars=nchars,
                rules=[(to_file_id(a, nchars), to_file_id(b, nchars))
                       for _kind, (a, b), _nid in p['rules']],
                alphabet=''.join(p['chars']))


def flat_report(args):
    m = flat_model(args.dir, args.k, args.kappa, args.seed)
    V, k = m['V'], m['k']
    books = []
    for L in range(k):
        codes = canonical_codes(list(m['depths'][L]), mode='max')
        books.append(dict(codes=codes, book=codebook(codes),
                          maxlen=int(m['depths'][L].max())))
    width = max(1, int(m['depths'].max()).bit_length())
    rules_bytes = len(pack_rules(m['rules'], V, m['nchars'])[0])
    map_bits = ceil_log2(k)
    code_bytes = (k * (V + 1) * width + 7) // 8
    map_bytes = (V * map_bits + 7) // 8
    total = (4 + 5 + 2 + rules_bytes + m['nchars'] + map_bytes + 1
             + code_bytes)
    print(f"{args.dir}: flat yardstick V={V}, k={k}, depth field {width} bits, "
          f"max depth {int(m['depths'].max())}")
    print(f'  codebook {code_bytes} B ({k} trees of {V + 1} depths), map '
          f'{map_bytes} B, rules {rules_bytes} B, total {total} B')

    lines = tw.read_lines(args.validation, stride=args.stride)
    bchars, brules, _bsym = tw.load_dictionary(args.dir)
    seqs = mfr.tokenise(lines, bchars, brules, m['nchars'])
    nchars = m['nchars']
    written, bad = [], 0
    for seq in seqs:
        assert seq[-1] == nchars
        fseq = [to_file_id(s, nchars) for s in seq[:-1]]
        bits = []
        L = 0
        for v in fseq:
            c = books[L]['codes'][1 + v]
            for pos in range(c[1] - 1, -1, -1):
                bits.append((c[0] >> pos) & 1)
            L = int(m['lcl'][v])
        while bits and bits[-1] == 0:       # the STOP codeword is all zeros
            bits.pop()
        # decode the same stream: one stage, padding ends it.  The word budget
        # is known, so the loop is bounded; the terminator must then be leaf 0.
        it = iter(bits)
        read = lambda: next(it, 0)
        out, L, ok = [], 0, True
        for _ in range(len(fseq)):
            try:
                v = walk(books[L]['book'], books[L]['maxlen'], read)
            except ValueError:
                ok = False
                break
            if v == 0:
                ok = False
                break
            out.append(v - 1)
            L = int(m['lcl'][v - 1])
        if ok:
            try:
                ok = walk(books[L]['book'], books[L]['maxlen'], read) == 0
            except ValueError:
                ok = False
        if not ok or out != fseq:
            bad += 1
        written.append(len(bits))
    written = np.array(written)
    print(f'  held-out n={len(seqs)}: round-trip failures {bad}; '
          f'bits/id {written.mean():.3f}, fit<=64 '
          f'{100 * (written <= 64).mean():.1f}%, <=128 '
          f'{100 * (written <= 128).mean():.1f}%')


# ------------------------------------------------------------- the report

def self_test():
    """The worked example of `MODEL_FORMAT.md` §6, end to end."""
    m = dict(V=7, k=2, q=2, nchars=5, alphabet='abcde',
             rules=[(1, 2), (3, 4)],
             memberships=[0, 1, 2, 2, 2, 1, 3],
             bottom=np.array([0, 1, 1, 2, 2, 1, 0]),
             top=np.array([[4, 1, 2, 3, 4], [4, 2, 1, 3, 4]]))
    lcl = [i // m['q'] for i in m['memberships']]
    bottom, top = codes_from(m, lcl)
    assert check_terminator(m) == [], check_terminator(m)
    # the STOP leaf of every top tree is the all-zeros codeword
    assert ''.join(str(top[0]['codes'][0][0] >> p & 1)
                   for p in range(3, -1, -1)) == '0000'
    assert ''.join(str(top[1]['codes'][0][0] >> p & 1)
                   for p in range(3, -1, -1)) == '0000'
    # right cluster 2 holds ids 2, 3, 4 at depths 1, 2, 2
    assert [''.join(str(c[0] >> p & 1) for p in range(c[1] - 1, -1, -1))
            for c in bottom[2]['codes']] == ['1', '00', '01']
    # a one-symbol right cluster spends nothing on the word step
    assert bottom[0]['codes'] == [(0, 0)]
    for name, seq, want in (('b', [1], '01'),
                            ('bc', [1, 2], '0100011'),
                            ('abc', [0, 1, 2], '10100011')):
        got = encode(seq, m, lcl, bottom, top)
        assert ''.join(map(str, got)) == want, (name, got, want)
        assert decode(got, m, lcl, bottom, top) == seq, name
    buf, sections = pack(m)
    back = unpack(buf)
    assert list(back['memberships']) == m['memberships']
    assert np.array_equal(back['bottom'], m['bottom'])
    assert np.array_equal(back['top'], m['top'])
    assert [tuple(p) for p in back['rules']] == m['rules']
    # The alphabet is UTF-8 and counted in characters: `abé世€` is five
    # characters in ten bytes, and the header still says five.
    wide = dict(m, alphabet='ab\u00e9\u4e16\u20ac')
    buf_wide, sections_wide = pack(wide)
    assert len(buf_wide) == len(buf) + 5, (len(buf_wide), len(buf))
    back_wide = unpack(buf_wide)
    assert back_wide['alphabet'] == wide['alphabet']
    assert back_wide['nchars'] == 5
    assert sections_wide['alphabet'] == 10
    # The YAML carries the same alphabet in JSON escapes and reads back:
    # literal UTF-8 would also be legal YAML, but the published file is ASCII.
    text = model_yaml(wide)
    assert text.isascii(), text
    fd, path = tempfile.mkstemp(suffix='.yaml')
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as f:
            f.write(text)
        assert read_yaml(path)['alphabet'] == wide['alphabet']
    finally:
        os.unlink(path)
    print(f'self-test ok: {len(buf)} B packed, sections '
          + ', '.join(f'{k}={v}' for k, v in sections.items()
                      if not k.endswith('_bits')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--flat', action='store_true',
                    help='measure the flat yardstick instead of the model')
    ap.add_argument('--dir', default='')
    ap.add_argument('--k', type=int, default=16)
    ap.add_argument('--q', type=int, default=1)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--assignment', default='one', choices=('one', 'two'))
    ap.add_argument('--shared-weight', type=float, default=1.0)
    ap.add_argument('--no-depth-bias', dest='depth_bias', action='store_false',
                    help='flatten the depths before the Huffman build')
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=10)
    ap.add_argument('--yaml', default='')
    ap.add_argument('--bin', default='')
    ap.add_argument('--json', default='')
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.dir:
        ap.error('--dir is required unless --self-test')
    if args.flat:
        flat_report(args)
        return

    m = build_model(args.dir, args.k, args.q, args.kappa, args.seed,
                    shared=(args.assignment == 'one'),
                    shared_weight=args.shared_weight,
                    bias=args.depth_bias)
    V, k, q, kq = m['V'], m['k'], m['q'], m['k'] * m['q']
    tag = (f'{args.dir}: V={V}, k={k}, q={q}, assignment={args.assignment}, '
           )
    print(tag)
    if m['empty']:
        print(f'  empty right clusters: {len(m["empty"])} of {k}')

    # ---- structure --------------------------------------------------------
    problems = check_terminator(m)
    print(f'  terminator: {"ok" if not problems else "BROKEN"}')
    for p in problems[:6]:
        print(f'    ! {p}')

    bd = np.asarray(m['bottom'], dtype=int)
    td = np.asarray(m['top'], dtype=int)
    mem = np.asarray(m['memberships'], dtype=int)
    bspan = max(int(bd[mem == J].max() - bd[mem == J].min())
                for J in range(kq) if (mem == J).any())
    tspan = max(int(td[L, 1:].max() - td[L, 1:].min()) for L in range(k))
    span_field = max(1, max(bspan, tspan).bit_length())
    print(f'  depths: bottom max {bd.max()}, top max {td.max()}, '
          f'per-tree span {max(bspan, tspan)} (bottom {bspan}, top {tspan}), '
          f'stored as offsets in a {DEPTH_BITS}-bit field '
          f'(offsets need {span_field})')
    counts = {d: int((bd == d).sum()) for d in range(int(bd.max()) + 1)}
    print('  bottom depths: ' + ' '.join(f'{d}:{counts[d]}' for d in counts
                                         if counts[d]))

    lcl = [i // q for i in m['memberships']] if args.assignment == 'one' \
        else [int(x) for x in m['lcl']]
    bottom, top = codes_from(m, lcl)

    # ---- the YAML and the binary -----------------------------------------
    text = model_yaml(m)
    if args.yaml:
        with open(args.yaml, 'w', encoding='ascii') as f:
            f.write(text)
    print(f'  YAML: {len(text)} bytes' + (f' -> {args.yaml}' if args.yaml else ''))
    if args.yaml:
        back = read_yaml(args.yaml)
        assert list(back['memberships']) == [int(x) for x in m['memberships']]
        assert np.array_equal(np.asarray(back['bottom']),
                              np.asarray(m['bottom']))
        assert np.array_equal(np.asarray(back['top']), np.asarray(m['top']))
        assert [tuple(p) for p in back['rules']] == \
               [tuple(p) for p in m['rules']]
        print('  YAML round-trip: ok')

    buf, sections = pack(m)
    plain, plain_sections = pack(m, packed_rules=False)
    if args.bin:
        with open(args.bin, 'wb') as f:
            f.write(buf)
    print(f'  binary: {len(buf)} bytes packed, {len(plain)} plain rules')
    print(f'    {"section":<16} {"bytes":>7} {"plain":>7}')
    for name, size in sections.items():
        if name.endswith('_bits'):
            continue
        print(f'    {name:<16} {size:>7} {plain_sections.get(name, 0):>7}')
    print(f'    {"total":<16} {len(buf):>7} {len(plain):>7}')
    print(f'    rule bits {sections["rules_bits"]} packed, '
          f'{plain_sections["rules_bits"]} plain')

    back = unpack(buf)
    assert back['V'] == V and back['k'] == k and back['q'] == q
    assert back['alphabet'] == m['alphabet']
    assert [tuple(p) for p in back['rules']] == [tuple(p) for p in m['rules']]
    assert list(back['memberships']) == [int(x) for x in m['memberships']]
    assert np.array_equal(back['bottom'], np.asarray(m['bottom']))
    assert np.array_equal(back['top'], np.asarray(m['top']))
    print('  binary round-trip: ok')
    pb = check_terminator(back)
    print(f'  packed terminator: {"ok" if not pb else "BROKEN"}')

    # ---- held-out identifiers --------------------------------------------
    lines = tw.read_lines(args.validation, stride=args.stride)
    bchars, brules, _bsym = tw.load_dictionary(args.dir)
    seqs = mfr.tokenise(lines, bchars, brules, m['nchars'])
    del lines
    nchars = m['nchars']
    b_bottom, b_top = codes_from(back, lcl)

    written, nominal, bad = [], [], 0
    for seq in seqs:
        assert seq[-1] == nchars, 'the tokeniser ends an identifier with the stop'
        fseq = [to_file_id(s, nchars) for s in seq[:-1]]
        w = encode(fseq, back, lcl, b_bottom, b_top)
        if decode(w, back, lcl, b_bottom, b_top) != fseq:
            bad += 1
        written.append(len(w))
        nominal.append(len(encode(fseq, back, lcl, b_bottom, b_top,
                                  write_stop=True)))
    written = np.array(written)
    nominal = np.array(nominal)
    print(f'  held-out n={len(seqs)}: round-trip failures {bad}')
    print(f'    bits/id {written.mean():.3f} written '
          f'({nominal.mean():.3f} with the stop coded), '
          f'fit<=64 {100 * (written <= 64).mean():.1f}%, '
          f'<=128 {100 * (written <= 128).mean():.1f}%')

    # ---- the one-map claim: what a second map would cost ------------------
    extra_map = (V * ceil_log2(k) + 7) // 8
    if args.assignment == 'two':
        print(f'    two maps: +{extra_map} bytes for the left map, '
              f'rejected by the one-map format')
        print(f'    one-map total would be {len(buf) + extra_map} bytes')

    if args.json:
        with open(args.json, 'w') as f:
            json.dump(dict(dir=args.dir, V=V, k=k, q=q,
                           seed=args.seed,
                           assignment=args.assignment,
                           sections=sections, total=len(buf),
                           total_two_maps=len(buf) + extra_map,
                           plain=len(plain), yaml=len(text),
                           terminator_problems=problems,
                           bits_written=float(written.mean()),
                           bits_nominal=float(nominal.mean()),
                           written_bits=[int(w) for w in written],
                           fit64=float((written <= 64).mean()),
                           fit128=float((written <= 128).mean()),
                           roundtrip_failures=bad), f, indent=1)
        print(f'  wrote {args.json}')


if __name__ == '__main__':
    main()
