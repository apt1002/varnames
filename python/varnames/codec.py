"""The codec: identifier <-> bit string <-> integer (``ENCODING.md`` §2).

The code alternates two steps: *which right cluster comes next, given the left
cluster we are in*, then *which word in that right cluster*.  The identifier
starts in left cluster 0 by convention and ends when the top stage reaches its
STOP leaf, whose codeword is all zeros — which is also the padding above the
integer, so the end costs nothing and is not stored.

One codec can be shared: encoding and decoding mutate nothing, so the only
state is the model, which is read-only after it is loaded.
"""

from __future__ import annotations

import heapq
from collections.abc import Sequence

from .bitio import BitSource, bits_length, bits_to_int
from .model import Leaf, Model, Rule, Tree, Word

#: A decode that has not reached STOP after this many words is not a code.
MAX_WORDS = 1_000_000


class EncodeError(ValueError):
    """The identifier cannot be encoded by this model."""


class DecodeError(ValueError):
    """The integer cannot be decoded as an identifier of this model."""


class Codec:
    """Ties a :class:`~varnames.model.Model` to the encoding loop."""

    def __init__(self, model: Model) -> None:
        self.model = model

    # --------------------------------------------------------------- encoding

    def tokenise(self, identifier: str) -> list[Word]:
        """Split an identifier into the model's words (``ENCODING.md`` §1).

        The result is word ids, which mean something only relative to
        :attr:`model`: ``0 .. num_chars() - 1`` are characters, and the rest
        are the words the rules define.
        """
        model = self.model
        words: list[Word] = []
        for c in identifier:
            word = model.char_id(c)
            if word is None:
                raise EncodeError(f"character {c!r} is not in the "
                                  "model's alphabet")
            words.append(word)
        return _MergePairs(words, model).run()

    def encode_bits(self, identifier: str) -> list[int]:
        """The codeword as a list of bits, stream order, trailing zeros cut."""
        model = self.model
        bits: list[int] = []

        def emit(tree: Tree, position: Leaf) -> None:
            value, length = tree.code(position)
            for shift in range(length - 1, -1, -1):
                bits.append((value >> shift) & 1)

        left = 0
        for word in self.tokenise(identifier):
            right = model.right(word)
            emit(model.top_tree(left), 1 + right)
            emit(model.bottom_tree(right), model.position(word))
            left = model.left(word)
        emit(model.top_tree(left), 0)           # the STOP leaf: all zeros
        while bits and bits[-1] == 0:
            bits.pop()
        return bits

    def encode(self, identifier: str) -> tuple[int, int]:
        """``(integer, bits)`` for an identifier.

        The integer's bit *i* is the *i*-th bit of the codeword, so the code
        sits in the low bits of the integer and the length is where its top
        bit lands.
        """
        bits = self.encode_bits(identifier)
        return bits_to_int(bits), bits_length(bits)

    # --------------------------------------------------------------- decoding

    def decode_bits(self, bits: Sequence[int],
                    limit: int = MAX_WORDS) -> str:
        """Decode a bit list; bits past the end read as zeros."""
        return self._decode(_ListReader(bits), limit)

    def decode(self, value: int, bits: int | None = None) -> str:
        """Decode an integer; ``bits`` is optional and only a sanity bound.

        A value with a set bit above position ``bits`` is rejected.
        """
        if value < 0:
            raise DecodeError("a code is a non-negative integer")
        if bits is not None and value.bit_length() > bits:
            raise DecodeError("the integer has bits above the stated length")
        return self._decode(_IntReader(value), MAX_WORDS)

    def _decode(self, reader: BitSource, limit: int) -> str:
        model = self.model
        words: list[Word] = []
        left = 0
        for _ in range(limit):
            slot = model.top_tree(left).read(reader)
            if slot == 0:
                return _spell(model, words)
            right = slot - 1
            word = model.word_at(right, model.bottom_tree(right).read(reader))
            words.append(word)
            left = model.left(word)
        raise DecodeError("the identifier does not terminate")


def _spell(model: Model, words: Sequence[Word]) -> str:
    """Words back to characters, expanding only the words that are present.

    A rule names children whose ids are smaller than its own, so expansion is a
    walk down a finite tree of the words this identifier actually contains.
    Spelling one identifier never replays the rule list, so the cost follows
    the output, not the model.
    """
    limit = model.num_words()
    out: list[str] = []
    stack = list(reversed(words))
    while stack:
        word = stack.pop()
        if not 0 <= word < limit:
            raise DecodeError("a word is outside the model")
        if model.is_char(word):
            out.append(model.char_at(word))
        else:
            a, b = model.children(model.rule_of_word(word))
            stack.append(b)               # the left operand comes off first
            stack.append(a)
    return "".join(out)


class _ListReader:
    """Read a bit list; past the end it yields the padding zeros."""

    __slots__ = ("bits", "pos")

    def __init__(self, bits: Sequence[int]) -> None:
        self.bits = bits
        self.pos = 0

    def get(self, width: int) -> int:
        value = 0
        for _ in range(width):
            bit = self.bits[self.pos] if self.pos < len(self.bits) else 0
            self.pos += 1
            value = (value << 1) | bit
        return value


class _IntReader:
    """Read the bits of a non-negative integer, least significant first.

    Bits above the top set bit are zeros forever, which is the padding the
    terminator relies on.
    """

    __slots__ = ("pos", "value")

    def __init__(self, value: int) -> None:
        self.value = value
        self.pos = 0

    def get(self, width: int) -> int:
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

    __slots__ = ("next", "prev", "word")

    def __init__(self, word: Word,
                 next: int | None = None,
                 prev: int | None = None) -> None:
        self.word: Word = word
        self.next: int | None = next
        self.prev: int | None = prev


class _Candidate:
    """A queued merge: the rule, the word it defines, and the position.

    Only the rule's rank orders the heap.  Two occurrences of one rule cannot
    overlap — a rule's two children differ, and the rule index has one entry
    per pair — so merges of equal rank are independent, and the order among
    them cannot matter.  That is why nothing here has to implement "the
    leftmost of a tie".
    """

    __slots__ = ("position", "rank", "word")

    def __init__(self, rank: Rule, word: Word, position: int) -> None:
        self.rank: Rule = rank
        self.word: Word = word
        self.position: int = position

    def __lt__(self, other: _Candidate) -> bool:
        return self.rank < other.rank


class _MergePairs:
    """The tokeniser of ``ENCODING.md`` §1: one sweep over the adjacent pairs.

    Ranks are nested — a merge's rank exceeds the ranks that built its operands
    — so any pair a merge creates has a rank above the one just used, and a
    sweep that always takes the lowest rank performs the merges in the order the
    model defines.

    The pair at a position can change after it has been queued, so when an
    entry surfaces the rule's children are compared with the words now at the
    position; an entry whose pair has gone is dropped.  The children are a
    list index, where asking the rule index again would hash the pair.
    """

    __slots__ = ("heap", "model", "nodes")

    def __init__(self, words: Sequence[Word], model: Model) -> None:
        n = len(words)
        self.nodes: list[_Node | None] = [
            _Node(word, i + 1 if i + 1 < n else None, i - 1 if i > 0 else None)
            for i, word in enumerate(words)
        ]
        self.model: Model = model
        self.heap: list[_Candidate] = []

    def push(self, i: int) -> None:
        """Offer the pair that starts at ``i``, if the model has a rule for it."""
        node = self.nodes[i]
        if node is None or node.next is None:
            return
        j = node.next
        right = self.nodes[j]
        if right is None:
            return
        rank = self.model.rule_for(node.word, right.word)
        if rank is not None:
            heapq.heappush(
                self.heap, _Candidate(rank, self.model.word_of_rule(rank), i))

    def run(self) -> list[Word]:
        """Merge until no adjacent pair has a rule; return the words that remain."""
        for i in range(len(self.nodes) - 1):
            self.push(i)
        while self.heap:
            candidate = heapq.heappop(self.heap)
            rank, merged, i = candidate.rank, candidate.word, candidate.position
            # The pair at `i` may have gone, or changed, since it was queued.
            node = self.nodes[i]
            if node is None or node.next is None:
                continue
            j = node.next
            right = self.nodes[j]
            if right is None:
                continue
            # The rank says which rule was queued; its children say whether
            # the rule still applies here, without hashing the pair again.
            if self.model.children(rank) != (node.word, right.word):
                continue                    # not the pair we queued: stale
            following = right.next
            node.word = merged
            node.next = following
            self.nodes[j] = None
            if following is not None:
                after = self.nodes[following]
                if after is not None:
                    after.prev = i
            # The pair before `i` is new too, because `i`'s word has changed.
            if node.prev is not None:
                self.push(node.prev)
            self.push(i)
        # A merge keeps the left node, so the survivors are still in order.
        return [node.word for node in self.nodes if node is not None]
