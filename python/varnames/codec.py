"""The codec: identifier <-> bit string <-> integer (``ENCODING.md`` §2).

The code alternates two steps: *which right cluster comes next, given the left
cluster we are in*, then *which word in that right cluster*.  The identifier
starts in left cluster 0 by convention and ends when the top stage reaches its
STOP leaf, whose codeword is all zeros — which is also the padding above the
integer, so the end costs nothing and is not stored.
"""

import heapq

from .bitio import bits_length, bits_to_int


class EncodeError(ValueError):
    """The identifier cannot be encoded by this model."""


class DecodeError(ValueError):
    """The integer is not a code of this model."""


class Codec:
    """Ties a :class:`~varnames.model.Model` to the encoding loop."""

    def __init__(self, model):
        self.model = model

    # --------------------------------------------------------------- encoding

    def tokenise(self, identifier):
        """Split an identifier into the model's symbols (``ENCODING.md`` §1)."""
        model = self.model
        try:
            tokens = [model._char_id[c] for c in identifier]
        except KeyError as exc:
            raise EncodeError(f"character {exc.args[0]!r} is not in the "
                              "model's alphabet") from None
        return _merge_pairs(tokens, model._plan)

    def encode_bits(self, identifier):
        """The codeword as a list of bits, stream order, trailing zeros cut."""
        model = self.model
        bits = []

        def emit(tree, position):
            value, length = tree.codes[position]
            for shift in range(length - 1, -1, -1):
                bits.append((value >> shift) & 1)

        left = 0
        for symbol in self.tokenise(identifier):
            cluster = model.memberships[symbol]
            emit(model.top_trees[left], 1 + cluster)
            emit(model.bottom_trees[cluster], model.pos_in_cluster[symbol])
            left = model.left[symbol]
        emit(model.top_trees[left], 0)          # the STOP leaf: all zeros
        while bits and bits[-1] == 0:
            bits.pop()
        return bits

    def encode(self, identifier):
        """``(integer, bits)`` for an identifier.

        The integer's bit *i* is the *i*-th bit of the codeword, so the code
        sits in the low bits of the integer and the length is where its top
        bit lands.
        """
        bits = self.encode_bits(identifier)
        return bits_to_int(bits), bits_length(bits)

    # --------------------------------------------------------------- decoding

    def decode_bits(self, bits, limit=1_000_000):
        """Decode a bit list; bits past the end read as zeros."""
        model = self.model
        reader = _ListReader(bits)
        out = []
        left = 0
        for _ in range(limit):
            slot = model.top_trees[left].read(reader)
            if slot == 0:
                return _spell(model, out)
            cluster = slot - 1
            tree = model.bottom_trees.get(cluster)
            if tree is None:
                raise DecodeError(f"right cluster {cluster} is empty")
            symbol = model.cluster_ids[cluster][tree.read(reader)]
            out.append(symbol)
            left = model.left[symbol]
        raise DecodeError("the identifier does not terminate")

    def decode(self, value, bits=None):
        """Decode an integer; ``bits`` is optional and only a sanity bound."""
        if value < 0:
            raise DecodeError("a code is a non-negative integer")
        reader = _IntReader(value)
        model = self.model
        out = []
        left = 0
        for _ in range(1_000_000):
            slot = model.top_trees[left].read(reader)
            if slot == 0:
                break
            cluster = slot - 1
            tree = model.bottom_trees.get(cluster)
            if tree is None:
                raise DecodeError(f"right cluster {cluster} is empty")
            symbol = model.cluster_ids[cluster][tree.read(reader)]
            out.append(symbol)
            left = model.left[symbol]
        else:
            raise DecodeError("the identifier does not terminate")
        if bits is not None and bits_length_of(value) > bits:
            raise DecodeError("the integer has bits above the stated length")
        return _spell(model, out)


def _spell(model, symbols):
    """Word ids back to characters, by replaying the rule list."""
    text = {}
    for i, c in enumerate(model.alphabet):
        text[i] = c
    for rank, (a, b) in enumerate(model.rules):
        text[model.nchars + rank] = text[a] + text[b]
    return "".join(text[s] for s in symbols)


def bits_length_of(value):
    return value.bit_length()


class _ListReader:
    __slots__ = ("bits", "pos")

    def __init__(self, bits):
        self.bits = bits
        self.pos = 0

    def get(self, width):
        value = 0
        for i in range(width):
            bit = self.bits[self.pos] if self.pos < len(self.bits) else 0
            self.pos += 1
            value = (value << 1) | bit
        return value


class _IntReader:
    __slots__ = ("value", "pos")

    def __init__(self, value):
        self.value = value
        self.pos = 0

    def get(self, width):
        chunk = (self.value >> self.pos) & ((1 << width) - 1)
        self.pos += width
        # bits arrive most-significant first, so reverse the chunk
        out = 0
        for _ in range(width):
            out = (out << 1) | (chunk & 1)
            chunk >>= 1
        return out


def _merge_pairs(tokens, plan):
    """The production tokeniser of `ENCODING.md` §1, in one pass.

    Ranks are nested — a merge's rank exceeds the ranks that built its operands
    — so sweeping ranks in ascending order and merging every still-valid pair
    performs the same merges as repeatedly taking the lowest rank.  A linked
    list over positions makes it O(n); the heap holds ranks, never positions, so
    it stays small.  A rank can be exhausted and later seen again, so the heap
    may hold duplicates and the bucket table is the authority.
    """
    n = len(tokens)
    if n < 2 or not plan:
        return tokens
    nxt = list(range(1, n + 1))
    prv = list(range(-1, n - 1))
    dead = [False] * n
    value = tokens[:]
    buckets = {}
    ranks = []
    get = plan.get

    def push(i):
        j = nxt[i]
        if j >= n or dead[j]:
            return
        found = get((value[i], value[j]))
        if found is None:
            return
        rank = found[0]
        bucket = buckets.get(rank)
        if bucket is None:
            buckets[rank] = [i]
            heapq.heappush(ranks, rank)
        else:
            bucket.append(i)

    for i in range(n - 1):
        push(i)
    while ranks:
        rank = ranks[0]                  # peek: drain a rank fully first
        bucket = buckets.get(rank)
        if bucket is None:               # a stale entry for an empty rank
            heapq.heappop(ranks)
            continue
        if not bucket:
            heapq.heappop(ranks)
            del buckets[rank]
            continue
        i = bucket.pop()
        if dead[i]:
            continue
        j = nxt[i]
        if j >= n or dead[j]:
            continue
        found = get((value[i], value[j]))
        if found is None or found[0] != rank:
            continue
        value[i] = found[1]
        dead[j] = True
        nxt[i] = nxt[j]
        following = nxt[j]
        if following < n:
            prv[following] = i
        for k in (prv[i], i):
            if k >= 0 and not dead[k]:
                push(k)
    out = []
    i = 0
    while i < n:
        out.append(value[i])
        i = nxt[i]
    return out
