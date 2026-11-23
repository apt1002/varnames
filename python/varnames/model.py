"""Reading the ``NVM1`` model file of ``standard/MODEL_FORMAT.md``.

A model is a word list (a pair-merge dictionary), one depth table for the word
trees and one for the cluster trees, plus the membership map.  Everything else
— the codewords, the leaf lists, the cluster of a word — is derived here, once,
at load time.

The reader is deliberately strict: every invariant the format states is checked,
so a corrupt or truncated file fails at load rather than at decode.

The tables are private.  A caller reads them through accessors named as in the
Rust crate's ``model`` module (``num_words``, ``left``, ``right``, ``word_at``,
…), which keep a right cluster from being passed where a left cluster is meant.
The aliases below are plain ``int`` — Python has no distinct index types — but
they carry the same names, so an annotation can say which integer is which.
"""

from __future__ import annotations

import codecs

from .bitio import BitReader
from .ladder import ceil_log2, ladder_get, read_varint

MAGIC = b"NVM1"
DEPTH_BITS = 4

#: A character's id, ``0 .. num_chars() - 1``.
Char = int
#: A word id: ``0 .. num_chars() - 1`` are characters, the rest rules.
Word = int
#: A rule's rank, which is also its word's id less ``num_chars()``.
Rule = int
#: A left cluster, ``0 .. num_lefts() - 1``.
Left = int
#: A right cluster, ``0 .. num_rights() - 1``.
Right = int
#: A leaf's position within one tree.
Leaf = int


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
    """One canonical Huffman tree: a codeword per leaf position.

    Position is the leaf's place in the stored depth sequence: a word's
    position in its right cluster for a bottom tree, and ``0 = STOP,
    1 + J = right cluster J`` for a top tree.

    A right cluster with no words has an empty tree.  It is a tree like any
    other -- no leaves, no codewords -- so reading from it fails and writing
    any position fails.
    """

    __slots__ = ("_codes", "_book", "_maxlen")

    def __init__(self, depths):
        self._codes = _canonical_codes(depths)
        self._book = {(length, value): pos
                      for pos, (value, length) in enumerate(self._codes)}
        self._maxlen = max(depths) if depths else 0

    def __len__(self):
        return len(self._codes)

    def code(self, position):
        """``(value, length)`` of the codeword at ``position``, MSB first."""
        return self._codes[position]

    def depths(self):
        """The length of the codeword at each position, in stored order."""
        return tuple(length for _value, length in self._codes)

    def write(self, writer, position):
        """Append the codeword of ``position`` to ``writer``, MSB first."""
        value, length = self._codes[position]
        for shift in range(length - 1, -1, -1):
            writer.put((value >> shift) & 1, 1)

    def read(self, reader):
        """Read one codeword; returns the leaf position.

        A codeword is a prefix of the stream, so the depths are tried from 0
        upwards: the test at each depth asks whether the bits read so far are
        one of that depth's leaves, and if not, one more bit is read.  Depth 0
        is a tree with one leaf -- the empty codeword -- so it is found before
        any bit is read.
        """
        if not self._codes:
            raise ModelError("an empty tree has no codewords")
        value = 0
        for length in range(self._maxlen + 1):
            pos = self._book.get((length, value))
            if pos is not None:
                return pos
            value = (value << 1) | reader.get(1)
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
    """A loaded model: the tables, and the codes derived from them at load."""

    def __init__(self, alphabet, rules, memberships, bottom, top, V, k, q):
        self._alphabet = alphabet
        self._rules = [tuple(p) for p in rules]
        self._memberships = list(memberships)
        self._bottom = list(bottom)
        self._top = [list(row) for row in top]
        self._V, self._k, self._q = V, k, q
        self._nchars = len(alphabet)
        self._kq = k * q
        self._left = [m // q for m in self._memberships]
        self._check()

        ids = [[] for _ in range(self._kq)]
        for word, cluster in enumerate(self._memberships):
            ids[cluster].append(word)
        self._ids_per_right = ids
        self._position = [0] * self._V
        self._bottom_trees = []
        for right, words in enumerate(ids):
            self._bottom_trees.append(
                Tree([self._bottom[i] for i in words]))
            for pos, word in enumerate(words):
                self._position[word] = pos
        self._top_trees = [Tree(row) for row in self._top]
        self._char_to_id = {c: i for i, c in enumerate(alphabet)}
        self._rule_by_pair = {(a, b): rank
                              for rank, (a, b) in enumerate(self._rules)}

    # ---------------------------------------------------------------- loading

    @classmethod
    def from_bytes(cls, buf):
        """Load a model from the bytes of an ``NVM1`` file."""
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
        if (reader.total + 7) // 8 != rules_len:
            raise ModelError(
                "the rule table's length is not the length of its rules")
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
        """Load a model from an ``NVM1`` file."""
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())

    # ------------------------------------------------------------- invariants

    def _check(self):
        if len(set(self._alphabet)) != self._nchars:
            # Two ids for one character would make the code ambiguous: `encode`
            # uses one of them and the other is unreachable, so decode could
            # not be the inverse of encode.
            raise ModelError("the alphabet repeats a character")
        if self._V != self._nchars + len(self._rules):
            raise ModelError("V is not the alphabet plus the rule list")
        seen = set()
        for i, (a, b) in enumerate(self._rules):
            N = self._nchars + i
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
        if len(self._memberships) != self._V:
            raise ModelError("the membership map does not cover V")
        if len(self._bottom) != self._V:
            raise ModelError("the word-depth table does not cover V")
        if len(self._top) != self._k:
            raise ModelError("the cluster-depth table does not cover k")
        for L, depths in enumerate(self._top):
            if len(depths) != self._kq + 1:
                raise ModelError("a cluster tree does not have kq + 1 leaves")
            if len(depths) > 1 and depths[0] != max(depths):
                raise ModelError(
                    f"cluster tree {L}: the STOP leaf is not the deepest")
            _require_complete(depths)
        for cluster in range(self._kq):
            depths = [self._bottom[i] for i, m in enumerate(self._memberships)
                      if m == cluster]
            if depths:
                # `q = 1` trees are complete; a truncated `q > 1` build may
                # leave holes (MODEL_FORMAT.md §1), so only check the bound.
                _require_kraft(depths)

    # ------------------------------------------------------------------ sizes

    def num_chars(self):
        """The size of the alphabet, ``len(alphabet)``."""
        return self._nchars

    def num_rules(self):
        """The number of pair-merge rules, which is also the number of ranks."""
        return len(self._rules)

    def num_words(self):
        """The size of the word space, ``V`` -- characters and rules."""
        return self._V

    def num_lefts(self):
        """The number of left clusters, ``k``."""
        return self._k

    def num_rights(self):
        """The number of right clusters, ``kq``."""
        return self._kq

    def num_rights_per_left(self):
        """The number of right clusters per left cluster, ``q``."""
        return self._q

    def alphabet(self):
        """The characters the model can code, as one string."""
        return self._alphabet

    # ---------------------------------------------------------------- lookups

    def char_at(self, char):
        """The character with id ``char``."""
        return self._alphabet[char]

    def char_id(self, c):
        """The id of character ``c``, or ``None`` if the model cannot code it."""
        return self._char_to_id.get(c)

    def children(self, rule):
        """The two child words of ``rule``; both are smaller than its word."""
        return self._rules[rule]

    def word_of_rule(self, rule):
        """The word that ``rule`` defines: ``num_chars() + rule``."""
        return self._nchars + rule

    def rule_of_word(self, word):
        """The rule that defines ``word``, which must be a rule's word."""
        return word - self._nchars

    def is_char(self, word):
        """True when ``word`` is one character rather than a merged pair."""
        return word < self._nchars

    def rule_for(self, a, b):
        """The rank of the rule that merges ``a`` then ``b``, or ``None``."""
        return self._rule_by_pair.get((a, b))

    # --------------------------------------------------------------- clusters

    def right(self, word):
        """The right cluster of ``word`` — the membership stored in the file."""
        return self._memberships[word]

    def left(self, word):
        """The left cluster of ``word``, which is its right cluster // q."""
        return self._left[word]

    def left_of(self, right):
        """The left cluster that owns right cluster ``right``."""
        return right // self._q

    def position(self, word):
        """``word``'s leaf position in the bottom tree of its right cluster."""
        return self._position[word]

    def word_at(self, right, at):
        """The word at leaf ``at`` of the bottom tree of right cluster ``right``."""
        return self._ids_per_right[right][at]

    def top_tree(self, left):
        """The top tree of left cluster ``left``."""
        return self._top_trees[left]

    def bottom_tree(self, right):
        """The bottom tree of right cluster ``right``."""
        return self._bottom_trees[right]

    # ------------------------------------------------------------------ views

    def __repr__(self):
        return (f"<varnames model V={self._V} k={self._k} q={self._q} "
                f"alphabet={self._nchars} rules={len(self._rules)}>")

    def info(self):
        """A one-line description for the CLI and for audit logs."""
        return (f"V={self._V} k={self._k} q={self._q} "
                f"alphabet={self._nchars} rules={len(self._rules)} "
                f"kq={self._kq}")


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
