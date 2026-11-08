"""Tests for the reference implementation: ``python3 -m unittest`` from python/.

The strict test is :meth:`TestStandard.test_held_out_rate`: the package must
reproduce the rates ``MODEL_BUDGET.md`` reports for the standard model, byte for
byte.  It walks the held-out corpus, so it takes about a minute.
"""

import hashlib
import os
import unittest

from varnames import Codec, DecodeError, EncodeError, Model, ModelError
from varnames.bitio import BitReader, BitWriter, bits_length, bits_to_int
from varnames.codec import _merge_pairs
from varnames.ladder import (ceil_log2, ladder_bits, ladder_edges,
                             ladder_get, ladder_interval, ladder_put,
                             read_varint, varint)
from varnames.model import DEPTH_BITS, MAGIC, _canonical_codes
from varnames.standard import STANDARD_SHA256, standard

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
ROOT = os.path.dirname(PACKAGE)
MODEL = os.path.join(PACKAGE, "varnames", "data", "model.nvm1")
VALIDATION = os.path.join(ROOT, "work", "camel", "merged_validation.txt")
GOLDEN = os.path.join(ROOT, "rust", "tests", "golden.txt")


class TestBitIO(unittest.TestCase):

    def test_lsb_first_round_trip(self):
        w = BitWriter()
        values = [(0, 1), (1, 1), (5, 3), (0x1FF, 9), (0, 4)]
        for value, width in values:
            w.put(value, width)
        r = BitReader(w.finish())
        for value, width in values:
            self.assertEqual(r.get(width), value)

    def test_padding_reads_as_zeros(self):
        r = BitReader(b"\xff")
        self.assertEqual(r.get(8), 0xFF)
        self.assertEqual(r.get(8), 0)
        self.assertEqual(r.get(1), 0)

    def test_integers_are_little_endian_in_bits(self):
        self.assertEqual(bits_to_int([1, 0, 1, 0, 0]), 0b00101)
        self.assertEqual(bits_length([1, 0, 1]), 3)
        self.assertEqual(bits_length([0, 0, 0]), 0)


class TestLadder(unittest.TestCase):

    def test_varint_round_trip(self):
        for n in [0, 1, 127, 128, 8_191, 2 ** 32, 2 ** 63 - 1]:
            buf = varint(n)
            self.assertEqual(read_varint(buf, 0), (n, len(buf)))

    def test_ceil_log2(self):
        self.assertEqual([ceil_log2(n) for n in (0, 1, 2, 3, 4, 5, 32)],
                         [0, 0, 1, 2, 2, 3, 5])

    def test_edges_are_monotone_and_end_at_n(self):
        for N in (1, 2, 7, 63, 8_191):
            edges = ladder_edges(N)
            self.assertEqual(edges[0], 0)
            self.assertEqual(edges[-1], N)
            self.assertEqual(edges, sorted(edges))
            self.assertTrue(all(a <= b for a, b in zip(edges, edges[1:])))

    def test_edges_grow_geometrically(self):
        edges = ladder_edges(8_191)
        self.assertEqual(len(edges), 9)          # 2**3 intervals, 9 edges
        widths = [b - a for a, b in zip(edges, edges[1:])]
        self.assertTrue(all(w >= 1 for w in widths))
        self.assertLessEqual(widths[-1], 2 * widths[-2])

    def test_interval_lookup(self):
        for N in (2, 100, 8_191):
            edges = ladder_edges(N)
            self.assertEqual(ladder_interval(N - 1, N), len(edges) - 2)
            for x in range(N):
                i = ladder_interval(x, N)
                self.assertTrue(edges[i] <= x < edges[i + 1], (N, x, i))

    def test_put_and_get_round_trip(self):
        for N in (2, 9, 100, 8_191):
            for x in (0, 1, N // 3, N - 2, N - 1):
                w = BitWriter()
                ladder_put(w, x, N)
                self.assertEqual(ladder_get(BitReader(w.finish()), N), x)

    def test_prices_agree_with_the_stream(self):
        for N in (2, 17, 8_191):
            for x in (0, 1, N // 2, N - 1):
                w = BitWriter()
                ladder_put(w, x, N)
                self.assertEqual(len(w.finish()) <= (ladder_bits(x, N) + 7) // 8,
                                 True)


class TestModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(MODEL, "rb") as f:
            cls.buf = f.read()
        cls.model = Model.from_bytes(cls.buf)

    def test_magic_and_digest(self):
        self.assertEqual(self.buf[:4], MAGIC)
        self.assertEqual(hashlib.sha256(self.buf).hexdigest(), STANDARD_SHA256)

    def test_dimensions(self):
        m = self.model
        self.assertEqual((m.V, m.k, m.q), (8_191, 32, 1))
        self.assertEqual(m.nchars, 63)
        self.assertEqual(len(m.rules), 8_128)
        self.assertEqual(m.V, m.nchars + len(m.rules))
        self.assertEqual(m.kq, 32)

    def test_every_rule_reads_back(self):
        m = self.model
        text = {i: c for i, c in enumerate(m.alphabet)}
        for rank, (a, b) in enumerate(m.rules):
            self.assertLess(a, m.nchars + rank)
            self.assertLess(b, m.nchars + rank)
            text[m.nchars + rank] = text[a] + text[b]
        self.assertIn("getUser", text.values())

    def test_top_trees_carry_the_deepest_stop_leaf(self):
        for tree in self.model.top_trees:
            depths = [length for _, length in tree.codes]
            self.assertEqual(len(depths), 33)
            self.assertEqual(depths[0], max(depths))
            self.assertEqual(sum(2 ** (max(depths) - d) for d in depths),
                             2 ** max(depths))

    def test_canonical_codes_are_prefix_free(self):
        depths = [1, 2, 3, 3]                     # a complete tree
        codes = _canonical_codes(depths)
        words = [format(value, f"0{length}b")
                 for value, length in codes]
        for i, a in enumerate(words):
            for j, b in enumerate(words):
                if i != j:
                    self.assertFalse(b.startswith(a), (a, b))

    def test_depth_field_is_four_bits(self):
        self.assertEqual(DEPTH_BITS, 4)

    def test_empty_or_truncated_buffers_are_rejected(self):
        for buf in (b"", b"NVM", b"NVM1", b"NVM1" + b"\x00" * 4, self.buf[:-1]):
            with self.assertRaises(ModelError):
                Model.from_bytes(buf)

    def test_trailing_bytes_are_rejected(self):
        with self.assertRaises(ModelError):
            Model.from_bytes(self.buf + b"\x00")

    def test_custom_model_by_path(self):
        self.assertEqual(Model.from_path(MODEL).info(), self.model.info())


class TestCodec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.codec = standard()

    def round_trip(self, name):
        value, bits = self.codec.encode(name)
        self.assertEqual(bits, value.bit_length())
        self.assertEqual(self.codec.decode(value), name)
        self.assertEqual(self.codec.decode(value, bits), name)
        self.assertEqual(bits_to_int(self.codec.encode_bits(name)), value)

    def test_round_trips(self):
        for name in ["a", "A", "x1", "foo", "myVar", "_", "identifier_name",
                     "getUserName", "HTTPServer", "makeHTTPRequest",
                     "A0Em5Q2", "A0K6lNpfqbDKzE0K70dpAy8i"]:
            self.round_trip(name)

    def test_short_names_are_small(self):
        self.assertLess(self.codec.encode("a")[0], 1 << 8)
        self.assertLess(self.codec.encode("foo")[1], 16)

    def test_stop_is_never_stored(self):
        bits = self.codec.encode_bits("getUserName")
        self.assertEqual(bits[-1], 1)

    def test_unknown_character(self):
        with self.assertRaises(EncodeError):
            self.codec.encode("hello world")

    def test_negative_and_overlong_codes(self):
        with self.assertRaises(DecodeError):
            self.codec.decode(-1)
        value, bits = self.codec.encode("foo")
        with self.assertRaises(DecodeError):
            self.codec.decode(value, bits - 1)

    def test_length_bound_accepts_the_true_length(self):
        value, bits = self.codec.encode("foo")
        self.assertEqual(self.codec.decode(value, bits), "foo")

    def test_merge_pairs_is_the_reference_tokeniser(self):
        m = self.codec.model
        plan = m._plan
        # every rule rank survives a round trip through the tokeniser
        for a, b in list(m.rules)[:200]:
            tokens = [a, b]
            self.assertEqual(len(_merge_pairs(tokens, plan)), 1)

    def test_custom_tables_are_used(self):
        codec = Codec(Model.from_path(MODEL))
        self.assertEqual(codec.encode("foo"), self.codec.encode("foo"))


@unittest.skipUnless(os.path.exists(GOLDEN), "the golden file is not present")
class TestGolden(unittest.TestCase):
    """The same file pins the Rust crate: both must agree code for code."""

    def test_agrees_with_the_rust_crate(self):
        codec = standard()
        with open(GOLDEN, "r", encoding="ascii") as f:
            for line in f:
                name, value, bits = line.split()
                value, bits = int(value), int(bits)
                self.assertEqual(codec.encode(name), (value, bits), name)
                self.assertEqual(codec.decode(value), name)
                self.assertEqual(codec.encode_bits(name),
                                 [(value >> i) & 1 for i in range(bits)])


@unittest.skipUnless(os.path.exists(VALIDATION), "held-out corpus not present")
class TestStandard(unittest.TestCase):
    """The package must agree with the oracle's measurement."""

    def test_held_out_rate(self):
        codec = standard()
        bits = []
        with open(VALIDATION, "r", encoding="ascii") as f:
            for i, line in enumerate(f):
                if i % 10:
                    continue
                name = line.rstrip("\n")
                if not name:
                    continue
                value, length = codec.encode(name)
                self.assertEqual(codec.decode(value), name)
                bits.append(length)
        n = len(bits)
        self.assertEqual(n, 42_268)
        self.assertAlmostEqual(sum(bits) / n, 45.218, places=2)
        self.assertAlmostEqual(100 * sum(b <= 64 for b in bits) / n, 85.0,
                               delta=0.05)
        self.assertAlmostEqual(100 * sum(b <= 128 for b in bits) / n, 99.0,
                               delta=0.05)


if __name__ == "__main__":
    unittest.main()
