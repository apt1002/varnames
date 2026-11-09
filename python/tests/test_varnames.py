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
from varnames.case import cased, classify, from_camel, to_camel
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
GOLDEN = os.path.join(ROOT, "standard", "golden.txt")
CASE_PAIRS = os.path.join(ROOT, "standard", "case-pairs.txt")
CASE_COPIES = [os.path.join(PACKAGE, "varnames", "data", "case-pairs.txt"),
               os.path.join(ROOT, "rust", "data", "case-pairs.txt")]


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


class TestUtf8Alphabet(unittest.TestCase):
    """The alphabet section is UTF-8, counted in characters, not bytes.

    The fixture is the smallest model that can say so: V = 4, k = q = 1, two
    characters, two rules.  Its alphabet is `aé` — two characters in three
    bytes — so the header says 2 and the section is longer than 2.  The Rust
    crate builds the same 17 bytes in `model::tests`.
    """

    @staticmethod
    def fixture():
        bw = BitWriter()
        for i, (a, b) in enumerate([(0, 1), (0, 2)]):
            N = 2 + i
            ladder_put(bw, a, N)
            ladder_put(bw, b, N)
        rules = bw.finish()
        out = bytearray(b"NVM1")
        out += varint(4) + varint(1) + varint(1) + varint(2)
        out += varint(len(rules)) + rules
        out += "a\u00e9".encode("utf-8")
        bw = BitWriter()
        for _ in range(4):                      # bottom depths, 4 leaves
            bw.put(0, 4)
        out += bw.finish()
        bw = BitWriter()
        for _ in range(2):                      # top depths, 2 leaves
            bw.put(0, 4)
        out += bw.finish()
        return bytes(out)

    def test_section_is_utf8(self):
        buf = self.fixture()
        self.assertEqual(len(buf), 17)
        self.assertEqual(buf[11:14], "a\u00e9".encode("utf-8"))
        m = Model.from_bytes(buf)
        self.assertEqual(m.alphabet, "a\u00e9")
        self.assertEqual(m.nchars, 2)
        self.assertEqual(m.nchars, len(m.alphabet))
        codec = Codec(m)
        value, bits = codec.encode("a\u00e9")
        self.assertEqual(bits, 2)
        self.assertEqual(codec.decode(value), "a\u00e9")

    def test_zero_rules_is_legal(self):
        out = bytearray(b"NVM1")
        out += varint(2) + varint(1) + varint(1) + varint(2) + varint(0)
        out += "a\u00e9".encode("utf-8")
        out += bytes(2)                     # one depth byte per tree
        m = Model.from_bytes(bytes(out))
        self.assertEqual(len(m.rules), 0)
        codec = Codec(m)
        value, _bits = codec.encode("a\u00e9")
        self.assertEqual(codec.decode(value), "a\u00e9")

    def test_broken_utf8_is_refused(self):
        buf = bytearray(self.fixture())
        buf[12] = 0xFF                          # the lead byte of é
        with self.assertRaises(ModelError):
            Model.from_bytes(bytes(buf))


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


class TestCaseConversion(unittest.TestCase):
    """`STANDARD.md` §11: the cased set, the transform, and its inverse."""

    @staticmethod
    def pairs():
        out = []
        with open(CASE_PAIRS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    up, lo = line.split()
                    out.append((up, lo))
        return out

    def test_table_is_the_published_one(self):
        pairs = self.pairs()
        self.assertEqual(len(pairs), 266)
        for path in CASE_COPIES:
            with open(path, "rb") as f:
                with open(CASE_PAIRS, "rb") as g:
                    self.assertEqual(f.read(), g.read(), path)

    def test_every_pair_is_a_one_to_one_inverse(self):
        for up, lo in self.pairs():
            self.assertEqual(len(up), 1)
            self.assertEqual(len(lo), 1)
            self.assertNotEqual(up, lo)
            self.assertTrue(cased(up) and cased(lo))
            self.assertEqual(to_camel("x_" + lo + "y"), "x" + up + "y")

    def test_the_cased_set_is_the_ranges_minus_six_letters(self):
        want = set()
        for a, b in ((0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x17F), (0x400, 0x52F)):
            for cp in range(a, b + 1):
                ch = chr(cp)
                if ch.isalpha() and cased(ch):
                    want.add(ch)
        outside = {"ß", "İ", "ı", "ŉ", "ſ", "ĸ", "Σ", "σ", "ς", "ǅ", "あ", "א"}
        for ch in outside:
            self.assertFalse(cased(ch), ch)
            self.assertNotIn(ch, want)
        have = {ch for up, lo in self.pairs() for ch in (up, lo)}
        self.assertEqual(have, want - outside)

    def test_ascii_is_the_behaviour_that_shipped(self):
        for name, want in [("a_b", "aB"), ("a__b", "a_B"), ("a_3", "a_3"),
                           ("a_", "a_"), ("FOO_BAR", "fooBar"),
                           ("_ABC", "Abc"), ("__a", "_A"), ("A_B", "aB"),
                           ("__3a", "__3a"), ("_3a", "_3a"),
                           ("a__3b", "a__3b"),
                           ("get_user_name", "getUserName"),
                           ("fooBar", "fooBar")]:
            self.assertEqual(to_camel(name), want, name)
        self.assertEqual(classify("fooBar"), "camel")
        self.assertEqual(classify("FOO"), "upper")
        self.assertEqual(classify("foo"), "lower")
        self.assertEqual(classify("123_"), "lower")

    def test_the_leading_accented_capital_is_now_lowered(self):
        # inert characters used to leave the leading letter alone, so an
        # upper-case class did not reach CamelCase and did not merge
        self.assertEqual(to_camel("ÄRGER"), "ärger")
        self.assertEqual(to_camel("_ÄRGER"), "Ärger")
        self.assertEqual(to_camel("ПРИВЕТ_МИР"), "приветМир")
        self.assertEqual(to_camel("données_brutes"), "donnéesBrutes")

    def test_inert_characters_do_not_vote_and_are_not_moved(self):
        for name in ["straße", "Ελληνικά", "a_日本", "кириллица", "ǅabc"]:
            self.assertEqual(to_camel(name), name)
            self.assertEqual(from_camel(name, classify(name)), name)

    def test_the_round_trip_is_exact(self):
        for up, lo in self.pairs():
            for name, cls in [("x_" + lo + "y", "lower"),
                              ("x" + lo + "y", "lower"),
                              ("X_" + up + "Y", "upper"),
                              ("X" + up + "Y", "upper")]:
                camel = to_camel(name)
                self.assertEqual(len(camel), len(name) - name.count("_"), name)
                self.assertEqual(from_camel(camel, cls), name)

    def test_to_camel_is_idempotent(self):
        for name in ["a_b", "A_B", "fooBar", "_ABC", "ÄRGER", "straße",
                     "a_日本", "a__b", "a__3"]:
            once = to_camel(name)
            self.assertEqual(to_camel(once), once, name)

    def test_an_unknown_class_is_refused(self):
        with self.assertRaises(ValueError):
            from_camel("aB", "mixed")


if __name__ == "__main__":
    unittest.main()
