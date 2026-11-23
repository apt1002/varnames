"""Bit-level primitives shared by the codec and the model reader.

The standard is LSB-first at the byte level (`MODEL_FORMAT.md` §3): bit *i* of
the stream is bit *i* mod 8 of byte *i* // 8.  A codeword is written from its
most-significant bit, which is the usual Huffman convention, so a bit list is
"stream order" and the integer a caller sees is that list read as a binary
number with the first bit as the least significant.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class BitSource(Protocol):
    """Anything a tree can read bits from: a byte buffer or an integer."""

    def get(self, width: int) -> int:
        """The next ``width`` bits, the first one most significant."""


class BitWriter:
    """Collect bits in stream order; `finish()` packs them LSB-first."""

    __slots__ = ("_acc", "_n", "_out", "total")

    def __init__(self) -> None:
        self._acc = 0
        self._n = 0
        self._out = bytearray()
        self.total = 0

    def put(self, value: int, width: int) -> None:
        """Append the low ``width`` bits of ``value``, least significant first."""
        if width <= 0:
            return
        self.total += width
        self._acc |= (int(value) & ((1 << width) - 1)) << self._n
        self._n += width
        while self._n >= 8:
            self._out.append(self._acc & 0xFF)
            self._acc >>= 8
            self._n -= 8

    def put_bit(self, bit: int) -> None:
        """Append one bit."""
        self.put(bit, 1)

    def finish(self) -> bytes:
        """The bytes written so far, the last one zero-padded."""
        if self._n:
            self._out.append(self._acc & 0xFF)
        return bytes(self._out)


class BitReader:
    """Read bits in stream order from an LSB-first byte string or an integer.

    Past the end of the buffer the reader returns zeros, which is exactly the
    padding the terminator relies on (`ENCODING.md` §2).
    """

    __slots__ = ("_acc", "_buf", "_n", "_pos", "total")

    def __init__(self, buf: bytes | bytearray | memoryview) -> None:
        self._buf = bytes(buf)
        self._pos = 0
        self._acc = 0
        self._n = 0
        self.total = 0

    def get(self, width: int) -> int:
        """Read ``width`` bits as an integer, first bit most significant."""
        if width <= 0:
            return 0
        self.total += width
        while self._n < width:
            byte = self._buf[self._pos] if self._pos < len(self._buf) else 0
            self._pos += 1
            self._acc |= byte << self._n
            self._n += 8
        value = self._acc & ((1 << width) - 1)
        self._acc >>= width
        self._n -= width
        return value

    def get_bit(self) -> int:
        """Read one bit."""
        return self.get(1)


def bits_to_int(bits: Sequence[int]) -> int:
    """The integer a bit list denotes: bit *i* of the list is bit *i* of it."""
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def bits_length(bits: Sequence[int]) -> int:
    """The number of significant bits: the position of the last set bit + 1."""
    for i in range(len(bits) - 1, -1, -1):
        if bits[i]:
            return i + 1
    return 0
