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
        """Split an identifier into the model's words (``ENCODING.md`` §1)."""
        model = self.model
        try:
            words = [model._char_id[c] for c in identifier]
        except KeyError as exc:
            raise EncodeError(f"character {exc.args[0]!r} is not in the "
                              "model's alphabet") from None
        return _MergePairs(words, model._plan).run()

    def encode_bits(self, identifier):
        """The codeword as a list of bits, stream order, trailing zeros cut."""
        model = self.model
        bits = []

        def emit(tree, position):
            value, length = tree.codes[position]
            for shift in range(length - 1, -1, -1):
                bits.append((value >> shift) & 1)

        left = 0
        for word in self.tokenise(identifier):
            cluster = model.memberships[word]
            emit(model.top_trees[left], 1 + cluster)
            emit(model.bottom_trees[cluster], model.pos_in_cluster[word])
            left = model.left[word]
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
            word = model.cluster_ids[cluster][tree.read(reader)]
            out.append(word)
            left = model.left[word]
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
            word = model.cluster_ids[cluster][tree.read(reader)]
            out.append(word)
            left = model.left[word]
        else:
            raise DecodeError("the identifier does not terminate")
        if bits is not None and bits_length_of(value) > bits:
            raise DecodeError("the integer has bits above the stated length")
        return _spell(model, out)


def _spell(model, words):
    """Words back to characters, expanding only the words that are present.

    A rule names children whose ids are smaller than its own, so expansion is a
    walk down a finite tree of the words this identifier actually contains.
    Spelling one identifier never replays the rule list, so the cost follows
    the output, not the model.
    """
    first_rule = model.nchars
    limit = first_rule + len(model.rules)
    out = []
    stack = list(reversed(words))
    while stack:
        word = stack.pop()
        if not 0 <= word < limit:
            raise DecodeError("a word is outside the model")
        if word < first_rule:
            out.append(model.alphabet[word])
        else:
            a, b = model.rules[word - first_rule]
            stack.append(b)               # the left operand comes off first
            stack.append(a)
    return "".join(out)


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


class _Node:
    """One word of the identifier, with the neighbours it can merge with.

    A merge keeps the left node and removes the right one, so the head of the
    list is always position 0 and the last node has no ``next``.  A node that
    has been merged away is replaced by ``None``.
    """

    __slots__ = ("word", "next", "prev")

    def __init__(self, word, next=None, prev=None):
        self.word = word
        self.next = next
        self.prev = prev


class _Candidate:
    """A queued merge: the rank of the rule, and the position it applies at.

    Only the rank orders the heap.  Two occurrences of one rule cannot overlap
    — a rule's two children differ, and the plan holds one entry per pair — so
    merges of equal rank are independent, and the order among them cannot
    matter.  That is why nothing here has to implement "the leftmost of a tie".
    """

    __slots__ = ("rank", "position")

    def __init__(self, rank, position):
        self.rank = rank
        self.position = position

    def __lt__(self, other):
        return self.rank < other.rank


class _MergePairs:
    """The tokeniser of ``ENCODING.md`` §1: one sweep over the adjacent pairs.

    Ranks are nested — a merge's rank exceeds the ranks that built its operands
    — so any pair a merge creates has a rank above the one just used, and a
    sweep that always takes the lowest rank performs the merges in the order the
    model defines.

    The pair at a position can change after it has been queued, so the rank is
    read from the plan again when an entry surfaces, and an entry that no longer
    matches is dropped.
    """

    __slots__ = ("nodes", "plan", "heap")

    def __init__(self, words, plan):
        n = len(words)
        self.nodes = [
            _Node(word, i + 1 if i + 1 < n else None, i - 1 if i > 0 else None)
            for i, word in enumerate(words)
        ]
        self.plan = plan
        self.heap = []

    def push(self, i):
        """Offer the pair that starts at ``i``, if the model has a rule for it."""
        node = self.nodes[i]
        if node is None or node.next is None:
            return
        right = self.nodes[node.next]
        if right is None:
            return
        found = self.plan.get((node.word, right.word))
        if found is not None:
            heapq.heappush(self.heap, _Candidate(found[0], i))

    def run(self):
        """Merge until no adjacent pair has a rule; return the words that remain."""
        for i in range(len(self.nodes) - 1):
            self.push(i)
        while self.heap:
            candidate = heapq.heappop(self.heap)
            rank, i = candidate.rank, candidate.position
            # The pair at `i` may have gone, or changed, since it was queued.
            node = self.nodes[i]
            if node is None or node.next is None:
                continue
            j = node.next
            right = self.nodes[j]
            if right is None:
                continue
            found = self.plan.get((node.word, right.word))
            if found is None or found[0] != rank:
                continue                    # not the pair we queued: stale
            following = right.next
            node.word = found[1]
            node.next = following
            self.nodes[j] = None
            if following is not None:
                self.nodes[following].prev = i
            # The pair before `i` is new too, because `i`'s word has changed.
            if node.prev is not None:
                self.push(node.prev)
            self.push(i)
        # A merge keeps the left node, so the survivors are still in order.
        return [node.word for node in self.nodes if node is not None]
