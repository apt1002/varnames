"""Reading the ``NVM1`` model file of ``standard/MODEL_FORMAT.md``.

A model is a word list (a pair-merge dictionary), one depth table for the word
trees and one for the cluster trees, plus the membership map.  Everything else
— the codewords, the leaf lists, the cluster of a word — is derived here, once,
at load time.

The reader is deliberately strict: every invariant the format states is checked,
so a corrupt or truncated file fails at load rather than at decode.
"""

import codecs

from .bitio import BitReader
from .ladder import ceil_log2, ladder_get, read_varint

MAGIC = b"NVM1"
DEPTH_BITS = 4


class ModelError(ValueError):
    """The bytes are not a model this reader understands."""


def _read_alphabet(buf, pos, nchars):
    """Decode exactly `nchars` characters of UTF-8: `(alphabet, bytes used)`.

    The header counts characters, not bytes.  UTF-8 delimits itself, so the
    section ends where the `nchars`-th character ends; an ASCII alphabet is one
    byte a character, which is why the shipped file's section is `nchars`
    bytes.  A byte that cannot start or continue a sequence is a model error,
    not a decode fallback: the file has no other way to say "unknown".
    """
    dec = codecs.getincrementaldecoder("utf-8")()
    out = []
    used = 0
    while len(out) < nchars:
        if pos + used >= len(buf):
            raise ModelError("truncated alphabet")
        try:
            ch = dec.decode(buf[pos + used:pos + used + 1])
        except UnicodeDecodeError:
            raise ModelError("the alphabet is not valid UTF-8") from None
        used += 1
        if ch:
            out.append(ch)
    return "".join(out), used


class Tree:
    """One canonical Huffman tree: ``codes[position] = (value, length)``.

    Position is the leaf's place in the stored depth sequence, which is the
    symbol id for a word tree and ``0 = STOP, 1 + J = right cluster J`` for a
    top tree.
    """

    __slots__ = ("codes", "book", "maxlen")

    def __init__(self, depths):
        self.codes = _canonical_codes(depths)
        self.book = {(length, value): pos
                     for pos, (value, length) in enumerate(self.codes)}
        self.maxlen = max(depths) if depths else 0

    def __len__(self):
        return len(self.codes)

    def write(self, writer, position):
        """Append the codeword of ``position`` to ``writer``, MSB first."""
        value, length = self.codes[position]
        for shift in range(length - 1, -1, -1):
            writer.put((value >> shift) & 1, 1)

    def read(self, reader):
        """Read one codeword; returns the leaf position."""
        if (0, 0) in self.book:          # a one-leaf tree codes in zero bits
            return self.book[(0, 0)]
        value = 0
        for length in range(1, self.maxlen + 1):
            value = (value << 1) | reader.get(1)
            pos = self.book.get((length, value))
            if pos is not None:
                return pos
        raise ModelError("no codeword within the tree's maximum depth")


def _canonical_codes(depths):
    """``MODEL_FORMAT.md`` §2: code 0 is the first leaf at the maximum depth.

    Codes ascend within a depth and the space is filled from the top down, so
    the deepest leaves take the low values — which is what puts the all-zeros
    path on leaf 0 of a top tree, the STOP leaf.
    """
    depths = [int(d) for d in depths]
    n = len(depths)
    if n == 0:
        return []
    maxd = max(depths)
    codes = [(0, 0)] * n
    nxt = 0
    for length in range(maxd, -1, -1):
        block = 1 << (maxd - length)
        start = (nxt + block - 1) // block
        labels = [i for i in range(n) if depths[i] == length]
        for step, pos in enumerate(labels):
            codes[pos] = (start + step, length)
        nxt = (start + len(labels)) * block
    return codes


def _depths_from_offsets(deltas):
    """Add back the per-tree offset, which is recovered from the Kraft sum.

    A complete tree has ``sum 2**-d = 1``; with ``d = o + delta`` that is
    ``2**o = sum 2**-delta``, so ``o`` is the (whole) exponent of the sum.
    """
    if not deltas:
        return []
    total = sum(1 << (15 - d) for d in deltas)
    offset = total.bit_length() - 1 - 15
    if total != 1 << (offset + 15):
        raise ModelError("a depth table's Kraft sum is not a power of two")
    return [d + offset for d in deltas]


class Model:
    """A loaded model: the tables plus the codes derived from them."""

    def __init__(self, alphabet, rules, memberships, bottom, top, V, k, q):
        self.alphabet = alphabet
        self.rules = [tuple(p) for p in rules]
        self.memberships = list(memberships)
        self.bottom = list(bottom)
        self.top = [list(row) for row in top]
        self.V, self.k, self.q = V, k, q
        self.nchars = len(alphabet)
        self.kq = k * q
        self.left = [m // q for m in self.memberships]
        self._check()
        self.word_ids = [None] * self.kq
        for word, cluster in enumerate(self.memberships):
            if self.word_ids[cluster] is None:
                self.word_ids[cluster] = []
            self.word_ids[cluster].append(word)
        self.bottom_trees = {}
        self.cluster_ids = [ids or [] for ids in self.word_ids]
        self.pos_in_cluster = [0] * self.V
        for cluster, ids in enumerate(self.cluster_ids):
            if not ids:
                continue
            self.bottom_trees[cluster] = Tree([self.bottom[i] for i in ids])
            for pos, word in enumerate(ids):
                self.pos_in_cluster[word] = pos
        self.top_trees = [Tree(row) for row in self.top]
        self._char_id = {c: i for i, c in enumerate(alphabet)}
        self._plan = {(a, b): (rank, self.nchars + rank)
                      for rank, (a, b) in enumerate(self.rules)}

    # ---------------------------------------------------------------- loading

    @classmethod
    def from_bytes(cls, buf):
        buf = bytes(buf)
        if buf[:4] != MAGIC:
            raise ModelError("bad magic: not an NVM1 model")
        pos = 4
        try:
            V, pos = read_varint(buf, pos)
            k, pos = read_varint(buf, pos)
            q, pos = read_varint(buf, pos)
            nchars, pos = read_varint(buf, pos)
            rules_len, pos = read_varint(buf, pos)
        except IndexError:
            raise ModelError("the header is truncated") from None
        if V < nchars:
            raise ModelError("V is smaller than the alphabet")
        if pos + rules_len > len(buf):
            raise ModelError("the rule table runs past the end of the file")
        kq = k * q

        reader = BitReader(buf[pos:pos + rules_len])
        rules = []
        for i in range(V - nchars):
            N = nchars + i
            rules.append((ladder_get(reader, N), ladder_get(reader, N)))
        pos += rules_len

        alphabet, used = _read_alphabet(buf, pos, nchars)
        pos += used

        width = ceil_log2(kq)
        nbytes = (V * width + 7) // 8
        if pos + nbytes > len(buf):
            raise ModelError("truncated membership map")
        reader = BitReader(buf[pos:pos + nbytes])
        pos += nbytes
        memberships = [reader.get(width) for _ in range(V)]
        if any(m >= kq for m in memberships):
            raise ModelError("a membership names a cluster that does not exist")

        nbytes = (V * DEPTH_BITS + 7) // 8
        if pos + nbytes > len(buf):
            raise ModelError("truncated word-depth table")
        reader = BitReader(buf[pos:pos + nbytes])
        pos += nbytes
        bottom = [0] * V
        for cluster in range(kq):
            ids = [i for i, m in enumerate(memberships) if m == cluster]
            deltas = [reader.get(DEPTH_BITS) for _ in ids]
            for i, d in zip(ids, _depths_from_offsets(deltas)):
                bottom[i] = d

        nbytes = (k * (kq + 1) * DEPTH_BITS + 7) // 8
        if pos + nbytes > len(buf):
            raise ModelError("truncated cluster-depth table")
        reader = BitReader(buf[pos:pos + nbytes])
        pos += nbytes
        top = []
        for _ in range(k):
            deltas = [reader.get(DEPTH_BITS) for _ in range(kq + 1)]
            top.append(_depths_from_offsets(deltas))
        if pos != len(buf):
            raise ModelError("trailing bytes after the model")

        return cls(alphabet, rules, memberships, bottom, top, V, k, q)

    @classmethod
    def from_path(cls, path):
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())

    # ------------------------------------------------------------- invariants

    def _check(self):
        if self.V != self.nchars + len(self.rules):
            raise ModelError("V is not the alphabet plus the rule list")
        seen = set()
        for i, (a, b) in enumerate(self.rules):
            N = self.nchars + i
            if not (0 <= a < N and 0 <= b < N):
                raise ModelError(f"rule {i} names a child that does not exist")
            # `a != b` rejects a run word; `seen` rejects a second id for a
            # word the file already defines, which the encoder's pair map
            # cannot represent.  Both catch a rule stream that was read past
            # its end: padding zeros decode as (0, 0).
            if a == b:
                raise ModelError(f"rule {i} names the same child twice")
            if (a, b) in seen:
                raise ModelError(f"rule {i} repeats an earlier rule")
            seen.add((a, b))
        if len(self.memberships) != self.V:
            raise ModelError("the membership map does not cover V")
        if len(self.bottom) != self.V:
            raise ModelError("the word-depth table does not cover V")
        if len(self.top) != self.k:
            raise ModelError("the cluster-depth table does not cover k")
        for L, depths in enumerate(self.top):
            if len(depths) != self.kq + 1:
                raise ModelError("a cluster tree does not have kq + 1 leaves")
            if len(depths) > 1 and depths[0] != max(depths):
                raise ModelError(
                    f"cluster tree {L}: the STOP leaf is not the deepest")
            _require_complete(depths)
        for cluster in range(self.kq):
            depths = [self.bottom[i] for i, m in enumerate(self.memberships)
                      if m == cluster]
            if depths:
                # `q = 1` trees are complete; a truncated `q > 1` build may
                # leave holes (MODEL_FORMAT.md §1), so only check the bound.
                _require_kraft(depths)

    # ------------------------------------------------------------------ views

    def __repr__(self):
        return (f"<varnames model V={self.V} k={self.k} q={self.q} "
                f"alphabet={self.nchars} rules={len(self.rules)}>")

    def info(self):
        """A one-line description for the CLI and for audit logs."""
        return (f"V={self.V} k={self.k} q={self.q} alphabet={self.nchars} "
                f"rules={len(self.rules)} kq={self.kq}")


def _require_complete(depths):
    """A tree must tile the code space: ``sum 2**(max-d) == 2**max``."""
    if not depths:
        return
    maxd = max(depths)
    total = sum(1 << (maxd - d) for d in depths)
    if total != 1 << maxd:
        raise ModelError("a depth table is not a complete tree")


def _require_kraft(depths):
    """A tree must not over-fill the code space."""
    if not depths:
        return
    maxd = max(depths)
    total = sum(1 << (maxd - d) for d in depths)
    if total > 1 << maxd:
        raise ModelError("a depth table over-fills the code space")
