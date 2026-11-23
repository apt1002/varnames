"""Tests for the reference implementation: ``python3 -m unittest`` from python/.

The strict test is :meth:`TestStandard.test_held_out_rate`: the package must
reproduce the rates ``MODEL_BUDGET.md`` reports for the standard model.  It
walks the held-out corpus; the whole suite takes a few seconds.
"""

from __future__ import annotations

import contextlib
import doctest
import hashlib
import io
import os
import unittest
from collections.abc import Sequence
from typing import cast

from varnames import Codec, DecodeError, EncodeError, Model, ModelError
from varnames.bitio import BitReader, BitWriter, bits_length, bits_to_int
from varnames.case import cased, classify, from_camel, is_upper, to_camel
from varnames.cli import main
from varnames.codec import _MergePairs, _spell
from varnames.ladder import (
    ceil_log2,
    ladder_bits,
    ladder_edges,
    ladder_get,
    ladder_interval,
    ladder_put,
    read_varint,
    varint,
)
from varnames.model import DEPTH_BITS, MAGIC, Tree, _canonical_codes
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

    def test_lsb_first_round_trip(self) -> None:
        w = BitWriter()
        values = [(0, 1), (1, 1), (5, 3), (0x1FF, 9), (0, 4)]
        for value, width in values:
            w.put(value, width)
        r = BitReader(w.finish())
        for value, width in values:
            self.assertEqual(r.get(width), value)

    def test_padding_reads_as_zeros(self) -> None:
        r = BitReader(b"\xff")
        self.assertEqual(r.get(8), 0xFF)
        self.assertEqual(r.get(8), 0)
        self.assertEqual(r.get(1), 0)

    def test_integers_are_little_endian_in_bits(self) -> None:
        self.assertEqual(bits_to_int([1, 0, 1, 0, 0]), 0b00101)
        self.assertEqual(bits_length([1, 0, 1]), 3)
        self.assertEqual(bits_length([0, 0, 0]), 0)


class TestLadder(unittest.TestCase):

    def test_varint_round_trip(self) -> None:
        for n in [0, 1, 127, 128, 8_191, 2 ** 32, 2 ** 63 - 1]:
            buf = varint(n)
            self.assertEqual(read_varint(buf, 0), (n, len(buf)))

    def test_ceil_log2(self) -> None:
        self.assertEqual([ceil_log2(n) for n in (0, 1, 2, 3, 4, 5, 32)],
                         [0, 0, 1, 2, 2, 3, 5])

    def test_edges_are_monotone_and_end_at_n(self) -> None:
        for N in (1, 2, 7, 63, 8_191):
            edges = ladder_edges(N)
            self.assertEqual(edges[0], 0)
            self.assertEqual(edges[-1], N)
            self.assertEqual(edges, sorted(edges))
            self.assertTrue(all(a <= b for a, b in zip(edges, edges[1:])))

    def test_edges_grow_geometrically(self) -> None:
        edges = ladder_edges(8_191)
        self.assertEqual(len(edges), 9)          # 2**3 intervals, 9 edges
        widths = [b - a for a, b in zip(edges, edges[1:])]
        self.assertTrue(all(w >= 1 for w in widths))
        self.assertLessEqual(widths[-1], 2 * widths[-2])

    def test_interval_lookup(self) -> None:
        for N in (2, 100, 8_191):
            edges = ladder_edges(N)
            self.assertEqual(ladder_interval(N - 1, N), len(edges) - 2)
            for x in range(N):
                i = ladder_interval(x, N)
                self.assertTrue(edges[i] <= x < edges[i + 1], (N, x, i))

    def test_put_and_get_round_trip(self) -> None:
        for N in (2, 9, 100, 8_191):
            for x in (0, 1, N // 3, N - 2, N - 1):
                w = BitWriter()
                ladder_put(w, x, N)
                self.assertEqual(ladder_get(BitReader(w.finish()), N), x)

    def test_prices_agree_with_the_stream(self) -> None:
        for N in (2, 17, 8_191):
            for x in (0, 1, N // 2, N - 1):
                w = BitWriter()
                ladder_put(w, x, N)
                self.assertEqual(len(w.finish()) <= (ladder_bits(x, N) + 7) // 8,
                                 True)


class TestModel(unittest.TestCase):

    buf: bytes
    model: Model

    @classmethod
    def setUpClass(cls) -> None:
        with open(MODEL, "rb") as f:
            cls.buf = f.read()
        cls.model = Model.from_bytes(cls.buf)

    def test_magic_and_digest(self) -> None:
        self.assertEqual(self.buf[:4], MAGIC)
        self.assertEqual(hashlib.sha256(self.buf).hexdigest(), STANDARD_SHA256)

    def test_dimensions(self) -> None:
        m = self.model
        self.assertEqual((m.num_words(), m.num_lefts(), m.num_rights_per_left()),
                         (8_191, 32, 1))
        self.assertEqual(m.num_chars(), 63)
        self.assertEqual(m.num_rules(), 8_128)
        self.assertEqual(m.num_words(), m.num_chars() + m.num_rules())
        self.assertEqual(m.num_rights(), 32)

    def test_every_rule_reads_back(self) -> None:
        m = self.model
        text = {i: m.char_at(i) for i in range(m.num_chars())}
        for rank in range(m.num_rules()):
            a, b = m.children(rank)
            self.assertLess(a, m.num_chars() + rank)
            self.assertLess(b, m.num_chars() + rank)
            text[m.word_of_rule(rank)] = text[a] + text[b]
        self.assertIn("getUser", text.values())

    def test_top_trees_carry_the_deepest_stop_leaf(self) -> None:
        m = self.model
        for left in range(m.num_lefts()):
            depths = list(m.top_tree(left).depths())
            self.assertEqual(len(depths), 33)
            self.assertEqual(depths[0], max(depths))
            self.assertEqual(sum(2 ** (max(depths) - d) for d in depths),
                             2 ** max(depths))

    def test_canonical_codes_are_prefix_free(self) -> None:
        depths = [1, 2, 3, 3]                     # a complete tree
        codes = _canonical_codes(depths)
        words = [format(value, f"0{length}b")
                 for value, length in codes]
        for i, a in enumerate(words):
            for j, b in enumerate(words):
                if i != j:
                    self.assertFalse(b.startswith(a), (a, b))

    def test_depth_field_is_four_bits(self) -> None:
        self.assertEqual(DEPTH_BITS, 4)

    def test_empty_or_truncated_buffers_are_rejected(self) -> None:
        for buf in (b"", b"NVM", b"NVM1", b"NVM1" + b"\x00" * 4, self.buf[:-1]):
            with self.assertRaises(ModelError):
                Model.from_bytes(buf)

    def test_trailing_bytes_are_rejected(self) -> None:
        with self.assertRaises(ModelError):
            Model.from_bytes(self.buf + b"\x00")

    def test_the_packaged_model_is_the_standard_file(self) -> None:
        # The digest pins the bytes to `STANDARD_SHA256`, but the constant
        # could be edited to match a corrupted copy.  The file in `standard/`
        # is the published one, so compare against it directly.
        with open(os.path.join(ROOT, "standard", "model.nvm1"), "rb") as f:
            self.assertEqual(self.buf, f.read())

    def test_a_repeated_alphabet_character_is_refused(self) -> None:
        # `V = 2`, no rules, alphabet "aa": two ids for one character.  The
        # reader must refuse it, or `encode` would use one id and leave the
        # other unreachable, and `decode` would not be its inverse.
        out = bytearray(b"NVM1")
        out += varint(2) + varint(1) + varint(1) + varint(2) + varint(0)
        out += b"aa"                    # membership map: zero width
        out += b"\x11"                  # bottom depths, one leaf each: 1, 1
        out += b"\x11"                  # top depths: STOP, cluster 0
        with self.assertRaisesRegex(ModelError, "repeats a character"):
            Model.from_bytes(bytes(out))

    def test_custom_model_by_path(self) -> None:
        self.assertEqual(Model.from_path(MODEL).info(), self.model.info())


class TestEmptyCluster(unittest.TestCase):
    """`V = 4`, `k = 1`, `q = 2` with every word in cluster 0.

    Right cluster 1 then has no words.  The top tree still names it -- its
    `kq + 1` leaves are fixed whatever the clusters contain -- so a code can
    point at it; the bottom stage has no word to name, and says so.
    """

    @staticmethod
    def fixture() -> bytes:
        bw = BitWriter()
        for i, (a, b) in enumerate(((0, 1), (0, 2))):
            N = 2 + i
            ladder_put(bw, a, N)
            ladder_put(bw, b, N)
        rules = bw.finish()
        out = bytearray(b"NVM1")
        out += varint(4) + varint(1) + varint(2) + varint(2)
        out += varint(len(rules)) + rules
        out += "a\u00e9".encode("utf-8")
        bw = BitWriter()
        for _ in range(4):              # memberships: one bit a word, all 0
            bw.put(0, 1)
        out += bw.finish()
        bw = BitWriter()
        for _ in range(4):              # word depths: cluster 0's four words
            bw.put(0, 4)
        out += bw.finish()              # cluster 1 contributes no bits
        bw = BitWriter()
        for depth in (2, 1, 2):         # STOP, cluster 0, cluster 1
            bw.put(depth, 4)
        out += bw.finish()
        return bytes(out)

    def test_the_empty_cluster_has_a_tree_with_no_leaves(self) -> None:
        m = Model.from_bytes(self.fixture())
        self.assertEqual((m.num_words(), m.num_rights()), (4, 2))
        self.assertEqual([len(m.bottom_tree(r)) for r in range(m.num_rights())],
                         [4, 0])
        with self.assertRaisesRegex(ModelError, "empty tree"):
            m.bottom_tree(1).read(BitReader(b"\xff"))

    def test_a_code_that_names_it_fails(self) -> None:
        codec = Codec(Model.from_bytes(self.fixture()))
        value, _bits = codec.encode("a\u00e9")
        self.assertEqual(codec.decode(value), "a\u00e9")
        # The top tree's codeword `01` names the empty cluster.
        with self.assertRaisesRegex(ModelError, "empty tree"):
            codec.decode(2)

    def test_an_empty_tree_is_a_tree(self) -> None:
        tree = Tree([])
        self.assertEqual(len(tree), 0)
        with self.assertRaisesRegex(ModelError, "empty tree"):
            tree.read(BitReader(b"\x00"))


class TestUtf8Alphabet(unittest.TestCase):
    """The alphabet section is UTF-8, counted in characters, not bytes.

    The fixture is the smallest model that can say so: V = 4, k = q = 1, two
    characters, two rules.  Its alphabet is `aé` — two characters in three
    bytes — so the header says 2 and the section is longer than 2.  The Rust
    crate builds the same 17 bytes in `model::tests`.
    """

    @staticmethod
    def fixture(
        rules: Sequence[tuple[int, int]] = ((0, 1), (0, 2)),
    ) -> bytes:
        bw = BitWriter()
        for i, (a, b) in enumerate(rules):
            N = 2 + i
            ladder_put(bw, a, N)
            ladder_put(bw, b, N)
        table = bw.finish()
        out = bytearray(b"NVM1")
        out += varint(4) + varint(1) + varint(1) + varint(2)
        out += varint(len(table)) + table
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

    def test_section_is_utf8(self) -> None:
        buf = self.fixture()
        self.assertEqual(len(buf), 17)
        self.assertEqual(buf[11:14], "a\u00e9".encode("utf-8"))
        m = Model.from_bytes(buf)
        self.assertEqual(m.alphabet(), "a\u00e9")
        self.assertEqual(m.num_chars(), 2)
        self.assertEqual(m.num_chars(), len(m.alphabet()))
        codec = Codec(m)
        value, bits = codec.encode("a\u00e9")
        self.assertEqual(bits, 2)
        self.assertEqual(codec.decode(value), "a\u00e9")

    def test_zero_rules_is_legal(self) -> None:
        out = bytearray(b"NVM1")
        out += varint(2) + varint(1) + varint(1) + varint(2) + varint(0)
        out += "a\u00e9".encode("utf-8")
        out += bytes(2)                     # one depth byte per tree
        m = Model.from_bytes(bytes(out))
        self.assertEqual(m.num_rules(), 0)
        codec = Codec(m)
        value, _bits = codec.encode("a\u00e9")
        self.assertEqual(codec.decode(value), "a\u00e9")

    def test_broken_utf8_is_refused(self) -> None:
        buf = bytearray(self.fixture())
        buf[12] = 0xFF                          # the lead byte of é
        with self.assertRaises(ModelError):
            Model.from_bytes(bytes(buf))

    def test_a_rule_naming_one_child_twice_is_refused(self) -> None:
        with self.assertRaisesRegex(ModelError, "same child twice"):
            Model.from_bytes(self.fixture([(0, 0), (0, 2)]))

    def test_a_repeated_rule_is_refused(self) -> None:
        with self.assertRaisesRegex(ModelError, "repeats an earlier rule"):
            Model.from_bytes(self.fixture([(0, 1), (0, 1)]))

    def test_a_rule_table_with_a_spare_byte_is_refused(self) -> None:
        buf = bytearray(self.fixture())
        buf[8] += 1                      # the length varint: two bytes -> three
        buf.insert(11, 0)                # one byte of slack in the table
        with self.assertRaisesRegex(ModelError, "length"):
            Model.from_bytes(bytes(buf))

    def test_a_rule_table_too_short_for_its_rules_is_refused(self) -> None:
        buf = bytearray(self.fixture())
        buf[8] -= 1                      # the length varint: two bytes -> one
        del buf[10]                      # and the second byte of the table
        with self.assertRaisesRegex(ModelError, "length"):
            Model.from_bytes(bytes(buf))

    def test_a_zero_filled_rule_stream_is_refused(self) -> None:
        """Read past its end, the ladder gives `(0, 0)` for every rule."""
        buf = bytearray(self.fixture())
        start = 4 + 4 + 1        # magic, the four header varints, the length
        end = buf.index(b"a\xc3\xa9")
        buf[start:end] = bytes(end - start)
        with self.assertRaisesRegex(ModelError, "same child twice"):
            Model.from_bytes(bytes(buf))


class TestCodec(unittest.TestCase):

    codec: Codec

    @classmethod
    def setUpClass(cls) -> None:
        cls.codec = standard()

    def round_trip(self, name: str) -> None:
        value, bits = self.codec.encode(name)
        self.assertEqual(bits, value.bit_length())
        self.assertEqual(self.codec.decode(value), name)
        self.assertEqual(self.codec.decode(value, bits), name)
        self.assertEqual(bits_to_int(self.codec.encode_bits(name)), value)

    def test_round_trips(self) -> None:
        for name in ["a", "A", "x1", "foo", "myVar", "_", "identifier_name",
                     "getUserName", "HTTPServer", "makeHTTPRequest",
                     "A0Em5Q2", "A0K6lNpfqbDKzE0K70dpAy8i"]:
            self.round_trip(name)

    def test_short_names_are_small(self) -> None:
        self.assertLess(self.codec.encode("a")[0], 1 << 8)
        self.assertLess(self.codec.encode("foo")[1], 16)

    def test_stop_is_never_stored(self) -> None:
        bits = self.codec.encode_bits("getUserName")
        self.assertEqual(bits[-1], 1)

    def test_unknown_character(self) -> None:
        with self.assertRaises(EncodeError):
            self.codec.encode("hello world")

    def test_negative_and_overlong_codes(self) -> None:
        with self.assertRaises(DecodeError):
            self.codec.decode(-1)
        value, bits = self.codec.encode("foo")
        with self.assertRaises(DecodeError):
            self.codec.decode(value, bits - 1)

    def test_length_bound_accepts_the_true_length(self) -> None:
        value, bits = self.codec.encode("foo")
        self.assertEqual(self.codec.decode(value, bits), "foo")

    def test_every_rule_pair_is_one_word(self) -> None:
        m = self.codec.model
        # a rule's own two children tokenise to the word the rule defines
        for rank in range(min(200, m.num_rules())):
            a, b = m.children(rank)
            self.assertEqual(len(_MergePairs([a, b], m).run()), 1)

    def test_the_sweep_agrees_with_the_definition(self) -> None:
        # The definition of ENCODING.md section 1, written the slow obvious
        # way: repeatedly merge the lowest-rank adjacent pair.  The leftmost of
        # a tie is taken here, but the choice cannot matter (STANDARD.md §5);
        # the sweep in _MergePairs is the fast form of the definition.
        model = self.codec.model
        n_words = model.num_words()

        def naive(words: list[int]) -> list[int]:
            out = list(words)
            while True:
                best: tuple[int, int, int] | None = None
                for i in range(len(out) - 1):
                    rank = model.rule_for(out[i], out[i + 1])
                    if rank is not None and (best is None or rank < best[0]):
                        best = (rank, i, model.word_of_rule(rank))
                if best is None:
                    return out
                _, i, new_word = best
                out[i] = new_word
                del out[i + 1]

        state = 0x2545F4914F6CDD1D
        mask = (1 << 64) - 1

        def roll() -> int:
            nonlocal state
            state ^= (state << 13) & mask
            state ^= state >> 7
            state ^= (state << 17) & mask
            return state

        for _ in range(20000):
            words = []
            for _ in range(roll() % 10):
                r = roll()
                wide = (r // 4) % n_words
                # Mostly characters, sometimes a longer word, so that the same
                # pair can turn up in several places at once.
                words.append(wide if r % 4 == 0 else (r // 4) % 64)
            self.assertEqual(_MergePairs(words, model).run(), naive(words), words)

    def test_a_stale_heap_entry_does_not_merge_early(self) -> None:
        # "Find".  The pairs are (F,i) rank 92, (i,n) rank 4 and (n,d) rank
        # 998, so the sweep merges (i,n) first.  That changes the pair at
        # position 0 to (F,in) rank 978, but the entry queued there at rank 92
        # is still in the heap; taken at face value it would merge (F,in) long
        # before rank 978, and the (in,d) rule at rank 125 -- the merge that
        # leads to the answer -- could never then fire.  Comparing the queued
        # rank's children with the words now at the position, when the entry
        # surfaces, is what prevents this; the random test above only stumbles
        # on such a case by luck of the draw.
        model = self.codec.model
        words: list[int] = []
        for c in "Find":
            word = model.char_id(c)
            assert word is not None, c
            words.append(word)
        self.assertEqual(len(_MergePairs(words, model).run()), 1)

    def test_spelling_expands_only_the_words_present(self) -> None:
        # The second rule names children that do not exist.  Replaying the rule
        # list would trip over it; expanding the words present cannot, because
        # no word here is that rule.
        class _Stub:
            def num_words(self) -> int:
                return 3

            def num_chars(self) -> int:
                return 1

            def is_char(self, word: int) -> bool:
                return word < 1

            def char_at(self, char: int) -> str:
                return "a"

            def rule_of_word(self, word: int) -> int:
                return word - 1

            def children(self, rule: int) -> tuple[int, int]:
                return [(0, 0), (7, 7)][rule]

        # Not a Model: _spell must consult only the methods above, so that a
        # rule naming children that do not exist can still be expanded over
        # the words that are present.
        stub = cast(Model, _Stub())
        self.assertEqual(_spell(stub, []), "")
        self.assertEqual(_spell(stub, [0]), "a")
        self.assertEqual(_spell(stub, [1]), "aa")
        self.assertEqual(_spell(stub, [1, 0, 1]), "aaaaa")

    def test_a_word_outside_the_model_is_an_error(self) -> None:
        with self.assertRaises(DecodeError):
            _spell(self.codec.model, [10 ** 6])
        with self.assertRaises(DecodeError):
            _spell(self.codec.model, [-1])

    def test_custom_tables_are_used(self) -> None:
        codec = Codec(Model.from_path(MODEL))
        self.assertEqual(codec.encode("foo"), self.codec.encode("foo"))


@unittest.skipUnless(os.path.exists(GOLDEN), "the golden file is not present")
class TestGolden(unittest.TestCase):
    """The same file pins the Rust crate: both must agree code for code."""

    def test_agrees_with_the_rust_crate(self) -> None:
        codec = standard()
        with open(GOLDEN, encoding="ascii") as f:
            for line in f:
                name, value_text, bits_text = line.split()
                value, bits = int(value_text), int(bits_text)
                self.assertEqual(codec.encode(name), (value, bits), name)
                self.assertEqual(codec.decode(value), name)
                self.assertEqual(codec.encode_bits(name),
                                 [(value >> i) & 1 for i in range(bits)])


@unittest.skipUnless(os.path.exists(VALIDATION), "held-out corpus not present")
class TestStandard(unittest.TestCase):
    """The package must agree with the oracle's measurement."""

    def test_held_out_rate(self) -> None:
        codec = standard()
        bits = []
        with open(VALIDATION, encoding="ascii") as f:
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
    def pairs() -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        with open(CASE_PAIRS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    up, lo = line.split()
                    out.append((up, lo))
        return out

    def check(self, cased: str, cls: str, camel: str) -> None:
        """`cased` has class `cls`, maps to `camel`, and `camel` maps back.

        The length check is `STANDARD.md` §11's "conversion shortens an
        identifier by exactly the separators it swallows and by nothing else":
        in the normal form an upper-case cased character always marks a
        swallowed separator, and no other character can be upper-case, so the
        two counts move together.
        """
        self.assertEqual(classify(cased), cls, cased)
        self.assertEqual(to_camel(cased), camel, cased)
        self.assertEqual(from_camel(camel, cls), cased, camel)
        if cls == "camel":
            # the identity, so this arm checks the classification alone
            self.assertEqual(cased, camel, cased)
        else:
            swallowed = sum(1 for ch in camel if is_upper(ch))
            self.assertEqual(
                len(camel) + swallowed, len(cased),
                f"{cased}: one swallowed separator per capital in {camel}")

    def test_table_is_the_published_one(self) -> None:
        pairs = self.pairs()
        self.assertEqual(len(pairs), 266)
        for path in CASE_COPIES:
            with open(path, "rb") as f, open(CASE_PAIRS, "rb") as g:
                self.assertEqual(f.read(), g.read(), path)

    def test_every_pair_is_a_one_to_one_inverse(self) -> None:
        for up, lo in self.pairs():
            self.assertEqual(len(up), 1)
            self.assertEqual(len(lo), 1)
            self.assertNotEqual(up, lo)
            self.assertTrue(cased(up) and cased(lo))
            self.assertEqual(to_camel("x_" + lo + "y"), "x" + up + "y")

    def test_the_cased_set_is_the_ranges_minus_six_letters(self) -> None:
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

    def test_ascii_is_the_behaviour_that_shipped(self) -> None:
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

    def test_a_caseless_name_is_camel(self) -> None:
        # there is nothing to convert, so the name is already in the normal
        # form; the transform is the identity, and the round trip agrees
        for name in ["", "_", "123_", "_123", "Ελληνικά", "日本"]:
            self.assertEqual(classify(name), "camel", name)
            self.assertEqual(to_camel(name), name, name)
            self.assertEqual(from_camel(name, "camel"), name, name)
            self.assertEqual(from_camel(to_camel(name), classify(name)), name)

    def test_the_leading_accented_capital_is_now_lowered(self) -> None:
        # inert characters used to leave the leading letter alone, so an
        # upper-case class did not reach CamelCase and did not merge
        self.assertEqual(to_camel("ÄRGER"), "ärger")
        self.assertEqual(to_camel("_ÄRGER"), "Ärger")
        self.assertEqual(to_camel("ПРИВЕТ_МИР"), "приветМир")
        self.assertEqual(to_camel("données_brutes"), "donnéesBrutes")

    def test_inert_characters_do_not_vote_and_are_not_moved(self) -> None:
        for name in ["straße", "Ελληνικά", "a_日本", "кириллица", "ǅabc"]:
            self.assertEqual(to_camel(name), name)
            self.assertEqual(from_camel(name, classify(name)), name)

    def test_the_round_trip_is_exact(self) -> None:
        for up, lo in self.pairs():
            self.check("x_" + lo + "y", "lower", "x" + up + "y")
            self.check("x" + lo + "y", "lower", "x" + lo + "y")
            self.check("X_" + up + "Y", "upper", "x" + up + "y")
            self.check("X" + up + "Y", "upper", "x" + lo + "y")

    def test_a_retained_underscore_is_not_swallowed(self) -> None:
        # an underscore the transform keeps — before a digit, before an inert
        # character, or at the end — costs no capital, so it does not shorten
        # the name either
        for text, cls, camel in [
            ("A_B_", "upper", "aB_"),
            ("A_3_", "upper", "a_3_"),
            ("_A_3B", "upper", "A_3b"),
            ("__3A", "upper", "__3a"),
            ("A__3B", "upper", "a__3b"),
            ("A_日本", "upper", "a_日本"),
        ]:
            self.check(text, cls, camel)

    def test_to_camel_is_not_idempotent(self) -> None:
        # The transform is defined up to the class, so it cannot be idempotent:
        # `_a` normalises to `A`, which is *upper*, so a second pass lower-cases
        # it to `a`.  The examples below are fixed points only because each one
        # normalises to a `camel` name, which `to_camel` returns unchanged.
        for name in ["a_b", "A_B", "fooBar", "_ABC", "ÄRGER", "straße",
                     "a_日本", "a__b", "a__3"]:
            once = to_camel(name)
            self.assertEqual(to_camel(once), once, name)
        self.assertEqual(to_camel("_a"), "A")
        self.assertEqual(classify(to_camel("_a")), "upper")
        self.assertEqual(to_camel(to_camel("_a")), "a")
        # a run of underscores peels one per pass until the class settles
        self.assertEqual(to_camel("__a"), "_A")
        self.assertEqual(to_camel("_A"), "A")
        self.assertEqual(to_camel(to_camel(to_camel("__A__B"))), "ab")

    def test_an_unknown_class_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            from_camel("aB", "mixed")


class TestCli(unittest.TestCase):
    """`python -m varnames`: the same three commands as the console script."""

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(list(argv))
        return status, out.getvalue(), err.getvalue()

    def test_encode(self) -> None:
        status, out, err = self.run_cli("encode", "getUserName")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("124101637", out)
        self.assertIn("27 bits", out)

    def test_encode_prints_one_column_on_request(self) -> None:
        self.assertEqual(self.run_cli("encode", "-i", "foo")[1].strip(), "7043")
        self.assertEqual(self.run_cli("encode", "-b", "foo")[1].strip(), "13")

    def test_decode(self) -> None:
        status, out, err = self.run_cli("decode", "124101637")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("getUserName", out)
        self.assertIn("27 bits", out)

    def test_decode_prints_the_bit_length_on_request(self) -> None:
        # Regression: this printed `name.bit_length()`, which a `str` does not
        # have, so `varnames decode -b` raised AttributeError.
        status, out, err = self.run_cli("decode", "-b", "124101637")
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(out.strip(), "27")

    def test_decode_rejects_a_code_above_the_stated_length(self) -> None:
        status, _out, err = self.run_cli("decode", "-l", "10", "124101637")
        self.assertEqual(status, 1)
        self.assertIn("above the stated length", err)

    def test_info(self) -> None:
        status, out, _err = self.run_cli("info")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("standard model 976670d7"), out)
        self.assertIn("V=8191", out)

    def test_encode_reports_a_character_outside_the_alphabet(self) -> None:
        status, out, err = self.run_cli("encode", "hello world")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("not in the model's alphabet", err)

    def test_an_unreadable_model_is_an_error_not_a_traceback(self) -> None:
        status, _out, err = self.run_cli("--model", MODEL + ".missing", "info")
        self.assertEqual(status, 2)
        self.assertTrue(err.startswith("varnames: "), err)


class TestDoctests(unittest.TestCase):
    """The examples in the docstrings must keep working."""

    def test_docstring_examples(self) -> None:
        import varnames.case
        import varnames.codec
        import varnames.model
        for module in (varnames, varnames.case, varnames.codec,
                       varnames.model):
            result = doctest.testmod(module)
            self.assertEqual(result.failed, 0, module.__name__)


if __name__ == "__main__":
    unittest.main()
