#!/usr/bin/env python3
"""The size oracle: build a model, write its YAML, pack the binary, decode.

Every byte the budget quotes should come from this script rather than from a
formula (`docs/MODEL_BUDGET.md` §7).  One run builds the model that the shipped
format can express, writes it as the YAML of `docs/MODEL_FORMAT.md`, packs that
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

Symbol numbering is the file's (`MODEL_FORMAT.md` §2): id 0 is the stop, the
characters are ids 1..len(alphabet), the words follow.  A build numbers the
characters 0..62 and the stop 63, so the codec shifts the characters by one and
maps the stop to 0.  That shift is not cosmetic: it is what puts the stop first
in every tree's canonical order.

The terminator
--------------
The stop is never written; the padding zeros are its codeword.  The padding meets
the *top* stage first, so each top tree carries one extra leaf: a zero-weight
**STOP** leaf 0, which is therefore the deepest leaf of that tree.  Both stages
then use one convention, and it is the mirror of DEFLATE's: the all-zeros
codeword belongs to the *first* leaf at the **maximum** depth, and the remaining
codes are handed out in ascending depth order from the far end of the space.

  * bottom trees: symbol 0 is the zero-weight leaf, so it takes code 0;
  * top trees: leaf 0 is STOP, so it takes code 0; the stop's own bottom leaf
    exists only to keep symbol 0 in the alphabet.

The orientation is derivable from the depths and the labels, so the file needs no
orientation table; `check_terminator` asserts it on the built model.

`--flat` measures the flat yardstick instead: one Huffman tree per left cluster
over all `V` words, which is the upper bound `docs/MODEL_BUDGET.md` §5.3 prices
the factored code against.  Its `k·V` depths are not shippable.

Usage:
    model_size.py --dir work/tw512ns --k 16 --q 2
    model_size.py --dir work/tw8192ns --k 16 --q 2 --yaml work/model.yaml
"""
import argparse
import json
import os
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import cluster_substrings_lib as csl
import model_fit_rates as mfr
from quarter_accounting import huffman

MAGIC = b'VNAM'
VERSION = 1
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
        self.out = bytearray()

    def put(self, value, width):
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

    def get(self, width):
        while self.n < width:
            byte = self.buf[self.pos] if self.pos < len(self.buf) else 0
            self.pos += 1
            self.acc |= byte << self.n
            self.n += 8
        v = self.acc & ((1 << width) - 1)
        self.acc >>= width
        self.n -= width
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


# ------------------------------------------------------- canonical codes

def canonical_codes(depths, mode='max'):
    """Canonical codes for one tree, from the depths.

    ``mode='min'``: code 0 belongs to the lowest label at the minimum depth.
    ``mode='max'``: code 0 belongs to the lowest label at the maximum depth.

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
    assert total == 1 << maxd, f'not complete: Kraft {total} != 2^{maxd}'
    spans = sorted((v << (maxd - L), 1 << (maxd - L)) for v, L in codes)
    free = 0
    for start, blk in spans:
        assert start == free, 'not prefix-free or not complete'
        free = start + blk
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

def huffman_trunc(weights, survivors):
    """Huffman depths, stopping the merge at `survivors` trees.

    `quarter_accounting.huffman` returns one group when `n <= stop_at`; the
    truncation at `n` survivors must return `n` singletons instead.
    """
    n = len(weights)
    if survivors >= n:
        return np.zeros(n), 0.0, [[i] for i in range(n)]
    return huffman(weights, stop_at=survivors)


def to_file_id(i, nchars):
    """Build symbol id -> file symbol id (stop 0, characters 1..n)."""
    i = int(i)
    if i == nchars:
        return 0
    if i < nchars:
        return i + 1
    return i


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


def build_model(directory, k, q, kappa=300.0, seed=1, shared=True,
                shared_weight=1.0, stop_weight='zero', reserve_stop=False):
    """Build the model tables from a dictionary directory."""
    chars, rules, sym = tw.load_dictionary(directory)
    M, uni, _, _, _ = hf.dense_matrix(directory)
    V, nchars = M.shape[0], len(chars)
    stop = nchars

    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    alpha = kappa * V
    cb = alpha * c0 / T0
    for i0 in range(0, V, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    del cb, r0
    c = M.sum(0)                       # unigram: the column mass

    if shared:
        lcl = rcl = shared_labels(M, k, np.random.default_rng(seed),
                                  shared_weight)
    else:
        lcl, _ = cw.cluster_axis(M, k, np.random.default_rng(seed), 0)
        rcl, _ = cw.cluster_axis(M, k, np.random.default_rng(seed + 1), 1)

    # ---- quarters: truncate each right cluster's Huffman build at q --------
    ql = np.zeros(V, dtype=np.int64)
    bot_depth = np.zeros(V, dtype=np.int64)
    empty = []
    for j in range(k):
        words = np.flatnonzero(rcl == j)
        if words.size == 0:
            empty.append(j)
            continue
        if reserve_stop and stop in words and words.size > 1:
            rest = words[words != stop]
            lens, _, groups = huffman_trunc(c[rest], max(1, q - 1))
            for pos, i in enumerate(rest):
                bot_depth[i] = int(lens[pos])
            groups = [[stop]] + [[int(rest[i]) for i in g] for g in groups]
        else:
            w = c[words].astype(np.float64)
            if stop_weight == 'zero' and stop in words:
                w[list(words).index(stop)] = 0.0
            lens, _, groups = huffman_trunc(w, q)
            for pos, i in enumerate(words):
                bot_depth[i] = int(lens[pos])
            groups = [[int(words[i]) for i in g] for g in groups]
        for gi, g in enumerate(groups):
            for i in g:
                ql[i] = j * q + gi
    kq = k * q
    lcl = ql // q if shared else lcl

    # ---- top trees: mass of each quarter after each left cluster ----------
    # Leaf 0 is a zero-weight STOP leaf: the padding decodes as it, so the
    # terminator lives in the top stage and every identifier ends for free.
    G = np.zeros((k, V))
    np.add.at(G, lcl, M)
    S = np.zeros((k, kq))
    for L in range(k):
        S[L] = np.bincount(ql, weights=G[L], minlength=kq)
    top_depth = np.zeros((k, kq + 1), dtype=np.int64)
    for L in range(k):
        w = np.concatenate([[0.0], S[L]])
        lens, _, _ = huffman_trunc(w, 1)
        top_depth[L] = lens.astype(np.int64)
    del G

    memberships = np.empty(V, dtype=np.int64)
    file_bottom = np.empty(V, dtype=np.int64)
    for s in range(V):
        memberships[to_file_id(s, nchars)] = int(ql[s])
        file_bottom[to_file_id(s, nchars)] = int(bot_depth[s])
    rules_file = [(to_file_id(a, nchars), to_file_id(b, nchars))
                  for _kind, (a, b), _nid in rules]

    file_lcl = np.empty(V, dtype=np.int64)
    for s in range(V):
        file_lcl[to_file_id(s, nchars)] = int(lcl[s])

    return dict(directory=directory, alphabet=''.join(chars),
                rules=rules_file, memberships=memberships, bottom=file_bottom,
                top=top_depth, lcl=file_lcl, V=V, k=k, q=q, nchars=nchars,
                stop_build=stop, empty=empty, shared=shared)


# ------------------------------------------------------------- the YAML

def model_yaml(m):
    lines = ['format: varnames-model',
             f'version: {VERSION}',
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
        ids = np.flatnonzero(m['memberships'] == J)
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
    """An independent reader: reads the YAML back and checks the invariants."""
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
    assert m['version'] == VERSION
    k, q = m['left_clusters'], m['right_clusters_per_left']
    nchars = len(m['alphabet'])
    V = nchars + 1 + len(m['rules'])
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
    for i, (a, b) in enumerate(m['rules']):
        assert a != b and 0 <= a < nchars + 1 + i and 0 <= b < nchars + 1 + i
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
    """The Zipf-coded rule table on its own: `(bytes, bits)`.

    Kept separate from `pack` so the other accounting scripts can charge the
    dictionary the price the file actually pays instead of a formula.  The
    prior is a function of `V` alone, so the decoder stores no table for it.
    """
    prefix = zipf_prefix(V)
    enc = ArithEncoder()
    for i, (a, b) in enumerate(rules):
        total = int(prefix[nchars + 1 + i])
        for x in (a, b):
            enc.encode(int(prefix[x]), int(prefix[x + 1]), total)
    return enc.finish(), enc.bits


def pack(m, depth_bits=None, packed_rules=True):
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
    add('version', bytes([VERSION]))
    add('header', varint(V) + varint(k) + varint(q) + varint(nchars))
    add('rules_length', varint(len(rules_data)))
    add('rules', rules_data)
    sections['rules_bits'] = rule_bits
    add('alphabet', m['alphabet'].encode('ascii'))

    width = ceil_log2(kq)
    bw = BitWriter()
    for label in m['memberships']:
        bw.put(int(label), width)
    add('memberships', bw.finish())
    sections['membership_bits'] = width

    depths = list(m['bottom']) + list(np.asarray(m['top']).ravel())
    if depth_bits is None:
        depth_bits = max(1, int(max(depths)).bit_length())
    add('depth_width', bytes([depth_bits]))
    bw = BitWriter()
    for J in range(kq):
        for i in np.flatnonzero(np.asarray(m['memberships']) == J):
            bw.put(int(m['bottom'][i]), depth_bits)
    add('bottom_depths', bw.finish())
    bw = BitWriter()
    for L in range(k):
        for d in m['top'][L]:
            bw.put(int(d), depth_bits)
    add('top_depths', bw.finish())

    add('crc32', zlib.crc32(bytes(out)).to_bytes(4, 'little'))
    return bytes(out), sections


def unpack(buf, packed_rules=True):
    """Read the binary back; the only thing the decoder sees."""
    assert buf[:4] == MAGIC, 'bad magic'
    pos = 4
    version = buf[pos]
    assert version == VERSION
    pos += 1
    V, pos = read_varint(buf, pos)
    k, pos = read_varint(buf, pos)
    q, pos = read_varint(buf, pos)
    nchars, pos = read_varint(buf, pos)
    rules_len, pos = read_varint(buf, pos)
    kq = k * q
    prefix = zipf_prefix(V)
    if packed_rules:
        dec = ArithDecoder(buf[pos:pos + rules_len])
        rules = []
        for i in range(V - 1 - nchars):
            total = int(prefix[nchars + 1 + i])
            pair = []
            for _ in range(2):
                t = dec.target(total)
                x = int(np.searchsorted(prefix, t, side='right') - 1)
                assert 0 <= x < nchars + 1 + i, (i, x)
                dec.update(int(prefix[x]), int(prefix[x + 1]), total)
                pair.append(x)
            rules.append(tuple(pair))
    else:
        br = BitReader(buf[pos:pos + rules_len])
        width = ceil_log2(V)
        children = [br.get(width) for _ in range(2 * (V - 1 - nchars))]
        rules = [tuple(children[2 * i:2 * i + 2])
                 for i in range(V - 1 - nchars)]
    pos += rules_len
    alphabet = buf[pos:pos + nchars].decode('ascii')
    pos += nchars

    width = ceil_log2(kq)
    nbytes = (V * width + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    memberships = np.array([br.get(width) for _ in range(V)])
    assert len(memberships) == V and memberships.max() < kq

    depth_bits = buf[pos]
    pos += 1
    nbytes = (V * depth_bits + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    bottom = np.zeros(V, dtype=np.int64)
    for J in range(kq):
        for i in np.flatnonzero(memberships == J):
            bottom[i] = br.get(depth_bits)
    nbytes = (k * (kq + 1) * depth_bits + 7) // 8
    br = BitReader(buf[pos:pos + nbytes])
    pos += nbytes
    top = np.zeros((k, kq + 1), dtype=np.int64)
    for L in range(k):
        for J in range(kq + 1):
            top[L, J] = br.get(depth_bits)
    crc = int.from_bytes(buf[pos:pos + 4], 'little')
    assert crc == zlib.crc32(buf[:pos]), 'CRC mismatch'
    pos += 4
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
        coded = canonical_codes(depths, mode='max')
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
    memberships = np.asarray(m['memberships'])
    problems = []
    for L in range(m['k']):
        dep = [int(x) for x in m['top'][L]]
        if len(dep) > 1 and dep[0] != max(dep):
            problems.append(f'top tree {L}: the STOP leaf is at depth {dep[0]}, '
                            f'not the maximum {max(dep)}')
    J = int(memberships[0])
    ids = np.flatnonzero(memberships == J)
    dep = [int(m['bottom'][i]) for i in ids]
    if len(ids) > 1 and int(m['bottom'][0]) != max(dep):
        problems.append(f'bottom tree {J}: the stop is at depth '
                        f'{int(m["bottom"][0])}, not the maximum {max(dep)}')
    return problems


def encode(seq, m, lcl, bottom, top, write_stop=False, strip=True):
    """Bits of one identifier (list of file symbol ids ending in the stop).

    The stop's codeword is not written -- the padding supplies it -- and the
    trailing zeros of the last real codeword need not be either.
    """
    bits = []
    u = 0
    for v in seq:
        if v == 0:
            if not write_stop:
                break               # the padding is the terminator
            # the old convention: the stop as an ordinary symbol (top + bottom)
            J = int(m['memberships'][0])
            t = top[lcl[u]]['codes'][1 + J]
            e = bottom[J]
            c = e['codes'][e['ids'].index(0)]
            for pos in range(t[1] - 1, -1, -1):
                bits.append((t[0] >> pos) & 1)
            for pos in range(c[1] - 1, -1, -1):
                bits.append((c[0] >> pos) & 1)
            break
        J = int(m['memberships'][v])
        t = top[lcl[u]]['codes'][1 + J]
        for pos in range(t[1] - 1, -1, -1):
            bits.append((t[0] >> pos) & 1)
        e = bottom[J]
        c = e['codes'][e['ids'].index(v)]
        for pos in range(c[1] - 1, -1, -1):
            bits.append((c[0] >> pos) & 1)
        u = v
    if strip:
        while bits and bits[-1] == 0:
            bits.pop()
    return bits


def decode(bits, m, lcl, bottom, top, limit=100000):
    it = iter(bits)

    def read_bit():
        return next(it, 0)          # past the end: padding zeros

    out = []
    L = lcl[0]
    for _ in range(limit):
        slot = walk(top[L]['book'], top[L]['maxlen'], read_bit)
        if slot == 0:
            return out
        J = slot - 1
        e = bottom[J]
        if e is None:
            raise ValueError(f'right cluster {J} is empty')
        v = e['ids'][walk(e['book'], e['maxlen'], read_bit)]
        if v == 0:
            return out
        out.append(v)
        L = lcl[v]
    raise ValueError('did not terminate')


def flat_model(directory, k, kappa=300.0, seed=1, stop_weight='zero'):
    """The flat yardstick: one Huffman tree per left cluster over all `V` words.

    This is the code `ENCODING.md` 2 describes: the stop is a zero-weight leaf
    of every tree, so the padding decodes as it in any context.  It is not
    shippable (`k*V` lengths) and exists to bound what a Huffman code can do at
    the same `(V, k)` under the shipped convention.
    """
    chars, rules, sym = tw.load_dictionary(directory)
    M, _uni, _, _, _ = hf.dense_matrix(directory)
    V, nchars = M.shape[0], len(chars)
    stop = nchars
    r0, c0, T0 = M.sum(1), M.sum(0), float(M.sum())
    cb = kappa * V * c0 / T0
    for i0 in range(0, V, 512):
        M[i0:i0 + 512] += np.outer(r0[i0:i0 + 512] / T0, cb)
    c = M.sum(0)
    lcl, _ = cw.cluster_axis(M, k, np.random.default_rng(seed), 0)
    G = np.zeros((k, V))
    np.add.at(G, lcl, M)
    del M
    depths = np.zeros((k, V), dtype=np.int64)
    for L in range(k):
        w = G[L].astype(np.float64)
        if stop_weight == 'zero':
            w[stop] = 0.0
        lens, _, _ = huffman_trunc(w, 1)
        depths[L] = lens.astype(np.int64)
    file_lcl = np.empty(V, dtype=np.int64)
    file_depths = np.empty((k, V), dtype=np.int64)
    for s in range(V):
        f = to_file_id(s, nchars)
        file_lcl[f] = int(lcl[s])
        file_depths[:, f] = depths[:, s]
    return dict(depths=file_depths, lcl=file_lcl, k=k, V=V, nchars=nchars,
                rules=[(to_file_id(a, nchars), to_file_id(b, nchars))
                       for _kind, (a, b), _nid in rules],
                alphabet=''.join(chars))


def flat_report(args):
    m = flat_model(args.dir, args.k, args.kappa, args.seed, args.stop_weight)
    V, k = m['V'], m['k']
    books = []
    for L in range(k):
        codes = canonical_codes(list(m['depths'][L]), mode='max')
        books.append(dict(codes=codes, book=codebook(codes),
                          maxlen=int(m['depths'][L].max())))
    width = max(1, int(m['depths'].max()).bit_length())
    prefix = zipf_prefix(V)
    enc = ArithEncoder()
    for i, (a, b) in enumerate(m['rules']):
        total = int(prefix[m['nchars'] + 1 + i])
        for x in (a, b):
            enc.encode(int(prefix[x]), int(prefix[x + 1]), total)
    rules_bytes = len(enc.finish())
    map_bits = ceil_log2(k)
    code_bytes = (k * V * width + 7) // 8
    map_bytes = (V * map_bits + 7) // 8
    total = (4 + 1 + 5 + 2 + rules_bytes + len(m['alphabet']) + map_bytes
             + 1 + code_bytes + 4)
    print(f"{args.dir}: flat yardstick V={V}, k={k}, depth field {width} bits, "
          f"max depth {int(m['depths'].max())}")
    print(f'  codebook {code_bytes} B ({k} trees of {V} depths), map '
          f'{map_bytes} B, rules {rules_bytes} B, total {total} B')

    lines = tw.read_lines(args.validation, stride=args.stride)
    bchars, brules, _bsym = tw.load_dictionary(args.dir)
    seqs = mfr.tokenise(lines, bchars, brules, m['nchars'])
    nchars = m['nchars']
    written, bad = [], 0
    for seq in seqs:
        fseq = [to_file_id(s, nchars) for s in seq]
        bits = []
        u = 0
        for v in fseq:
            if v == 0:
                break
            c = books[m['lcl'][u]]['codes'][v]
            for pos in range(c[1] - 1, -1, -1):
                bits.append((c[0] >> pos) & 1)
            u = v
        while bits and bits[-1] == 0:
            bits.pop()
        # decode the same stream: one stage, padding ends it.  The word budget
        # is known, so the loop is bounded; the terminator must then be the
        # stop leaf.  (Unbounded padding reads would follow the all-zeros path
        # into a fresh leaf every time.)
        it = iter(bits)
        read = lambda: next(it, 0)
        out, L, ok = [], m['lcl'][0], True
        for _ in range(len(fseq) - 1):
            try:
                v = walk(books[L]['book'], books[L]['maxlen'], read)
            except ValueError:
                ok = False
                break
            if v == 0:
                ok = False
                break
            out.append(v)
            L = m['lcl'][v]
        if ok:
            try:
                ok = walk(books[L]['book'], books[L]['maxlen'], read) == 0
            except ValueError:
                ok = False
        if not ok or out != fseq[:-1]:
            bad += 1
        written.append(len(bits))
    written = np.array(written)
    print(f'  held-out n={len(seqs)}: round-trip failures {bad}; '
          f'bits/id {written.mean():.3f}, fit<=64 '
          f'{100 * (written <= 64).mean():.1f}%, <=128 '
          f'{100 * (written <= 128).mean():.1f}%')


# ------------------------------------------------------------- the report

def self_test():
    """The worked example of MODEL_FORMAT.md §5, end to end."""
    m = dict(V=8, k=2, q=2, nchars=5, alphabet='abcde', rules=[(1, 2), (6, 3)],
             memberships=[3, 0, 1, 2, 2, 2, 1, 3],
             bottom=np.array([1, 0, 1, 1, 2, 2, 1, 1]),
             top=np.array([[4, 1, 2, 3, 4], [4, 2, 1, 3, 4]]))
    lcl = [i // m['q'] for i in m['memberships']]
    bottom, top = codes_from(m, lcl)
    assert check_terminator(m) == [], check_terminator(m)
    assert ''.join(str(top[0]['codes'][0][0] >> p & 1)
                   for p in range(3, -1, -1)) == '0000'
    assert [''.join(str(c[0] >> p & 1) for p in range(c[1] - 1, -1, -1))
            for c in bottom[2]['codes']] == ['1', '00', '01']
    for name, seq, want in (('a', [1, 0], '01'),
                            ('ab', [1, 2, 0], '0101'),
                            ('abc', [1, 2, 3, 0], '010100011')):
        got = encode(seq, m, lcl, bottom, top)
        assert ''.join(map(str, got)) == want, (name, got, want)
        assert decode(got, m, lcl, bottom, top) == seq[:-1], name
    buf, sections = pack(m)
    back = unpack(buf)
    assert list(back['memberships']) == m['memberships']
    assert np.array_equal(back['bottom'], m['bottom'])
    assert np.array_equal(back['top'], m['top'])
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
    ap.add_argument('--stop-weight', default='zero', choices=('zero', 'mass'))
    ap.add_argument('--reserve-stop', action='store_true')
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
                    stop_weight=args.stop_weight,
                    reserve_stop=args.reserve_stop)
    V, k, q, kq = m['V'], m['k'], m['q'], m['k'] * m['q']
    tag = (f'{args.dir}: V={V}, k={k}, q={q}, assignment={args.assignment}, '
           f'stop weight={args.stop_weight}'
           + (', stop reserved' if args.reserve_stop else ''))
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
    width_needed = max(1, int(max(bd.max(), td.max())).bit_length())
    print(f'  depths: bottom max {bd.max()}, top max {td.max()}, '
          f'field {width_needed} bits')
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
        fseq = [to_file_id(s, nchars) for s in seq]
        w = encode(fseq, back, lcl, b_bottom, b_top)
        if decode(w, back, lcl, b_bottom, b_top) != fseq[:-1]:
            bad += 1
        written.append(len(w))
        nominal.append(len(encode(fseq, back, lcl, b_bottom, b_top,
                                  write_stop=True, strip=False)))
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
                           assignment=args.assignment,
                           stop_weight=args.stop_weight,
                           reserve_stop=args.reserve_stop,
                           sections=sections, total=len(buf),
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
