# The model file

Status: **`NVM1` specified; implemented by the size oracle.**  The model is
published as a portable, uncompressed YAML file; a binary form is derived from
it, and its size is what the budget measures.  `scripts/model_size.py` writes
the YAML, packs it, reads it back and decodes held-out identifiers through the
packed file, so every byte quoted here is a measurement of an artefact the
decoder read.

The YAML is the normative description of a model's *meaning*; the binary form is
normative for its *bytes*, and is a deterministic function of the YAML, so a
published binary can be checked by converting it back.  Nothing in the file
depends on how the model was generated: any build that produces the same tables
produces a byte-identical file.

## 1. What the file contains

It is the three published tables of [`MODEL_BUDGET.md`](MODEL_BUDGET.md) §1,
plus enough header to identify the format:

| table (MODEL_BUDGET §1) | key | derivation |
|---|---|---|
| the word list, `V − len(alphabet)` index pairs | `rules:` | — |
| the word trees, `V` leaves over `k·q` trees | `bottom_trees:`, `memberships:` | right cluster → words; canonical codes |
| the cluster trees, `k` trees of `k·q + 1` leaves | `top_trees:` | canonical codes; leaf 0 is the terminator |
| the alphabet | `alphabet:` | ids `0 … len(alphabet) − 1` |
| — | `format:`, `left_clusters:`, `right_clusters_per_left:` | — |

The code has two alphabets.  A word belongs to a **right cluster**, which is
what the word step codes; the `k·q` right clusters are grouped `q` to a **left
cluster**, which is what the cluster step codes.  The top stage is therefore `k`
trees of `k·q` leaves, not `k·q` trees of `k·q`; `MODEL_FORMAT` keeps `q`
because the format is general, and `q = 1` ships
([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md) has the measurement).

Each top tree has one leaf more than there are right clusters: a zero-weight
**STOP** leaf, listed first.  It is never emitted — the padding is what the
decoder reads there — and it is what makes the identifier end for free.  **The
word trees have no terminator leaf.**  An identifier ends when the top stage
says so, before any word step, so a bottom tree's deepest leaf is a word like
any other.  The corpus tokeniser's stop token is not a symbol of the file at
all: its row of the adjacency matrix is the **start state**, which is what makes
the first token's distribution available, and its column does not exist because
nothing is coded after the end (see §5).

The file stores **one map**: each word's right cluster.  Its left cluster is
that label divided by `q`, so the second alphabet costs no second table — one
label per word at `⌈log₂ kq⌉` bits instead of `⌈log₂ k⌉`, and the two counts `k`
and `q`.

Symbol ids are dense from zero: the characters are ids `0 … len(alphabet) − 1`
and the words follow, so the last word is `V − 1` and
`V = len(alphabet) + len(rules)`.  There is no reserved id.

A model is a **code, not a statistic**: no counts, no unigram, no corpus
fingerprint.  Everything the decoder needs is either in the file or derivable
from it.

## 2. The schema

```yaml
format: varnames-model                 # literal, identifies the YAML
alphabet: "abcde"                      # characters, ids 0..4
left_clusters: 2                       # k: one top tree per left cluster
right_clusters_per_left: 2             # q: right clusters per left cluster
rules:                                 # word ids follow the alphabet
  - [1, 2]                             # id 5
  - [3, 4]                             # id 6
memberships: [0, 1, 2, 2, 2, 1, 3]     # V labels: symbol id -> right cluster
bottom_trees:                          # k*q trees, one per right cluster
  - [0]                                # right cluster 0: symbol 0 alone
  - [1, 1]                             # right cluster 1: symbols 1, 5
  - [1, 2, 2]                          # right cluster 2: symbols 2, 3, 4
  - [0]                                # right cluster 3: symbol 6 alone
top_trees:                             # one tree per left cluster
  - [4, 1, 2, 3, 4]                    # leaf 0 is STOP; then right clusters 0-3
  - [4, 2, 1, 3, 4]                    # after left cluster 1
```

Every sequence is a YAML sequence of integers; the file is ASCII with LF
newlines, two-space indentation, and no anchors, aliases, tags or maps other
than the top level.  A writer may add comments and blank lines; a reader must
ignore them.

The numbering is the **file's**, and only the file's is normative.  A build
working on the corpus tokeniser's alphabet will number the characters `0 … 62`,
the stop `63` and the words above it; dropping the stop shifts the words down
one.  That shift is the whole of `to_file_id` in `scripts/model_size.py`.

### The keys

* `alphabet` — the characters the model can code, as ids `0 … len(alphabet) − 1`.
  The shipped model uses the 63 ASCII characters that occur in identifiers; the
  field is carried explicitly so a reader can check the file against a corpus
  instead of assuming that set.  A toy model may use fewer.
* `left_clusters` — `k`, the number of left clusters.  It fixes the number of
  top trees, the left-hand alphabet, and the length of each `top_trees` entry
  once `q` is known (`k·q + 1`).
* `right_clusters_per_left` — `q`, the number of right clusters per left
  cluster.  It fixes the right-hand alphabet, `k·q`, and so the number of
  `bottom_trees` entries.  `q = 1` makes the two alphabets one, which is the
  plain factored model and the shipped choice.  The key is required even though
  the shipped value is 1, so that a file is never read two ways.
* `rules` — the word list as pairs of child ids.  Entry *i* defines word id
  `len(alphabet) + i`, and its children are strictly smaller ids, so the list is
  a topological order of the merge tree.  Rule *i* may not name its own id, and
  its two children must differ (no run words, `DICTIONARY_RULES.md`).
* `memberships` — one label per symbol id, `0 ≤ label < k·q`: that symbol's
  right cluster.  Labels `c·q … c·q + q − 1` are the right clusters of left
  cluster `c`, so the left cluster is that label divided by `q`.  This is the
  one assignment the model stores, and with `bottom_trees` it is table (b): the
  membership map and the unigram vector that the depths encode.
* `bottom_trees` — `k·q` depth sequences, numbered by right cluster.  A right
  cluster holds its symbols in ascending id order, one depth each, measured from
  that tree's root; a right cluster with one symbol has it at depth 0 and costs
  no bits at all.  The decoder knows which words are in the tree from
  `memberships`, so no leaf list is stored, and each tree is complete in its own
  right (a Huffman build stopped at `q` survivors).
* `top_trees` — `k` depth sequences of `k·q + 1` entries each.  Tree *i* is the
  code for the next **right cluster** given left cluster *i*; leaf 0 is the
  **STOP** leaf, which the model gives zero weight, and leaves 1 … `k·q` are the
  right clusters in ascending label order.

### Invariants a reader must check

1. `len(memberships) == V` and `V = len(alphabet) + len(rules)`.
2. `len(bottom_trees) == k·q`, every symbol id `0 … V−1` appears in exactly one
   of their leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == k`, each with `k·q + 1` entries: the STOP leaf and one per
   right cluster.
5. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + i`.
6. A left cluster has at most `q` non-empty right clusters.  Fewer is legal — a
   right cluster with one word cannot be split further — and an empty one is an
   empty depth list and never decodes.  The shipped build is `q = 1`, so every
   left cluster has exactly one non-empty right cluster.
7. In every top tree, leaf 0 (STOP) is at the **maximum** depth.  It follows
   from giving that leaf zero weight, and it is what makes the padding decode as
   the terminator (§6).  There is no corresponding rule for the bottom trees:
   they carry no terminator.

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3, in one form for both stages: **the all-zeros
codeword belongs to the first leaf at the maximum depth**, the remaining codes
are handed out in *ascending* depth order from the top of the code space (the
mirror image of the usual DEFLATE convention), and within a depth the leaves
ascend by label.  Invariant 7 is what makes the first leaf at the maximum depth
be the terminator, so neither the encoder nor the decoder needs an orientation
table.  The identifier **starts in left cluster 0** — a convention, so it is not
stored; the build picks the left cluster whose top tree codes the first-token
distribution cheapest and renumbers the labels so that one is 0.

## 3. The binary form

Measured, not estimated: `scripts/model_size.py` packs the model in this order
and reports the bytes of each section.  The figures are at `V = 8,191, k = 32,
q = 1`, the operating point, with the packed rule table.

| section | encoding | bytes |
|---|---|---:|
| magic | `NVM1` | 4 |
| `V`, `k`, `q`, `len(alphabet)` | varints | 5 |
| rules length | a varint, because the rule stream is not self-delimiting | 3 |
| `rules` | 2 × (V − 63) child indices, coded by §4 | 21,109 |
| `alphabet` | `len(alphabet)` bytes, ids 0–62 | 63 |
| `memberships` | `⌈log₂ k⌉` = 5 bits each, packed | 5,120 |
| depth width | one byte, in bits | 1 |
| `bottom_trees` | `V` depths at that width, right cluster by right cluster, ascending symbol id inside | 5,120 |
| `top_trees` | `k(k + 1)` = 1,056 depths at the same width | 660 |
| **total** | | **32,085** |

There is **no version byte**: `NVM1` is the version.  A change that would break a
reader changes the magic to `NVM2`, and a reader must reject a magic it does not
know.  There is **no checksum**: the decoder already checks the magic, every child id
against the rule's own limit, the completeness of every tree (the Kraft sum), the
leaf counts against `memberships`, and that the file ends where the tables say it
does.  A CRC-32 would add four bytes to catch nothing those checks do not.

A **varint** is a base-128, little-endian integer: each byte carries seven
payload bits and the top bit says whether another byte follows.  So `V = 8,191`
is two bytes (`0xFF 0x3F`), `k = 32` one, and a length below 128 one.  It is the
usual protobuf/LEB128 encoding, chosen because `V` and `k` are the values whose
useful range is widest and whose common values are smallest.

Bits are packed **least-significant first within a byte**: bit *i* of the stream
is bit *i* mod 8 of byte *i* // 8, and bit 0 of the code is the first bit an
encoder writes, so the padding of `ENCODING.md` §2 is the run of zeros *above*
the code.  Integers are little-endian.

The depth width is **5 bits measured, not assumed**: at the operating point the
deepest word tree is 23 and the deepest top tree 19, and 5 bits holds the whole
measured grid.  Six bits would be needed only above depth 31, which no point
reaches, and a length limit would only be needed for a build that reaches it.
The bias experiment below is the route down to 4 bits.

The rest of the file is 10,976 B, so the model is **32.1 kB** — against the
34.1 kB of `MODEL_BUDGET.md` §5.1, which adds 2 kB of library code that is not
part of the model.  The YAML of §2 is 182,509 B at the same point — 5.7 times
as large: it is the portable form, and the binary is what the budget measures.

### Experiment: a 4-bit depth field by biasing the weights

The depth field costs `V + k(k+1)` depths at 5 bits: 5,780 B at the operating
point, 1,156 B more than a 4-bit field (`V` and `k(k+1)` depths at 4 bits =
4,096 + 528 B).  Four bits are not enough for the measured range (0–23),
because a Huffman build puts a rare leaf much deeper than a common one.  The
range can be compressed by *biasing* the weights before the build:

    bias  =  max(0, (P_max − 32768 · P_min) / 32767)

added to every leaf probability, where `P_max` and `P_min` are the largest and
smallest positive leaf probabilities in that tree.  The bias lifts the smallest
weight so that `P_max / P_min` is about `2^15`, and a Huffman tree cannot spread
leaves whose weights differ by less than a factor `2^k` over more than `k`
levels.  The deepest-to-shallowest difference is then meant to be at most 15, so
the field holds `d − d_min` in 4 bits.

**Measured, the ratio alone is not enough.**  At 8192/32 it gives a bottom span
of 15 but a top span of 17 and an overall span of 17, which is still 5 bits.
The bound needs a second condition, in the same units: the shallowest leaf is
never shorter than one bit, while the deepest can run a couple of bits past
`−log₂ q_min`, so what bounds the *Huffman* span is the absolute floor

    q_min  ≥  2^-15      i.e.   bias  ≥  T / 32768 − P_min

with `T` the total weight.  Taking the larger of the two biases and then
doubling it until the built tree spans 15 or less gives the guarantee, and the
doubling stops at the first bias that works, so the fit cost stays minimal.
Measured that way: every tree on the grid spans at most 15, bottom max 12 and
top max 15 at 8192/32, so the field is 4 bits and the offsets are per tree.

The constant offset is recovered from the Kraft equality, per tree: a complete
tree has `Σ 2^(−d) = 1`, so with `d = δ + o` the decoder computes
`2^o = Σ 2^(−δ)` and takes `o = log₂` of it, which must be a whole number.  No
byte is stored for `o`, no `d_min` field is needed, and a tree with one leaf
carries no depth at all (its symbol is coded in zero bits, and the decoder knows
it is alone from `memberships`).  The Kraft check is also a decoder invariant:
a depth table whose δ's give no integer `o` is corrupt.

Zero-weight leaves are excluded from the bias: they are the terminator, they must
stay the deepest leaf, and lifting them to `bias` would put them level with real
leaves and could break invariant 7.

**What it buys, measured** (`--depth-bias`, stride 10, seed 1).  "Span" is the
worst single-tree spread of depths, and the field column is the width that spread
needs — the width of a file that stores the per-tree offsets above.  Today's file
stores raw depths, so its width is `bits(max)`, which is 5 at all three points:

| point | bias | bottom max | top max | worst span | field | bits/id | fit ≤64 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 8192/32 | off | 23 | 19 | 18 | 5 bits | 45.217 | 85.0 % |
| 8192/32 | on | 15 | 16 | **15** | **4 bits** | 45.165 | 85.0 % |
| 8192/16 | off | 23 | 12 | 18 | 5 bits | 45.676 | 84.5 % |
| 8192/16 | on | 20 | 12 | **14** | **4 bits** | 45.664 | 84.6 % |
| 4096/16 | off | 19 | 13 | 14 | 4 bits | 48.982 | 80.5 % |
| 4096/16 | on | 15 | 13 | **13** | **4 bits** | 48.965 | 80.5 % |

The fit rate does not move at any point, and the mean bits move the *right* way
in all three (by 0.01–0.05, which is noise: the bias only lengthens the rarest
leaves).  Shortening the field saves 1,156 B at the operating point, 1,058 B at
8192/16 and 546 B at 4096/16 — 3.6 % of the largest file — so the 4-bit field is
worth adopting.  What it needs is the offset convention above written into the
format, which is why the layout in §3 still says one width per file.

## 4. The rule table and how it is coded

The rules are the largest object in the file: 21,109 of 32,085 B, two thirds of
the model.  Rule *i* is a pair `(u, v)` of child ids, both below
`N = len(alphabet) + i`, and the decoder's only choices are how to turn the pair
into numbers and how to code a number known to lie in `[0, N)`.

* **plain** — `⌈log₂ N⌉` bits per child: 26,416 B at the operating point, and the
  whole file 37,392 B.  Simple, obviously correct, and the form the round-trip
  tests use.
* **packed** — the grid of §4.1, whose best is 20,925 B.

`scripts/rule_encoding.py` prices the grid on the 8,192-word list (8,128 rules,
16,256 child indices).  The first axis combines the pair into one number; the
second codes a number in `[0, N)`:

| pairing | `x` stored | range |
|---|---|---:|
| Pair | `u` and `v`, two numbers | `N²` |
| Triangle | `(u+v)(u+v−1)/2 + u` | `2N²` |
| Square | `(v−1)² + u` if `u < v`, else `u(u−1) + v` | `(N−1)²` |

| number code | bits |
|---|---|
| Fixed | `⌈log₂ N⌉` |
| Variable | `L = ⌊log₂ N⌋`, `s = N − 2^L`: `L` bits, then one more when `x ≥ 2^L − s` |
| Zipf | `b` bits of interval index, then Variable inside the interval |

The measured grid, bytes for the whole 8,128-rule list (10.30 bits per child is
the best; the arithmetic coder of old measured 21,109 B, 10.39):

| encoding | bytes | bits/child |
|---|---:|---:|
| **Zipf b=3, base 2, / Pair** | **20,925** | **10.298** |
| Zipf b=3, base √e, / Pair | 20,961 | 10.316 |
| Zipf b=2, base e, / Pair | 20,983 | 10.326 |
| Zipf b=3, base e, / Triangle | 21,162 | 10.415 |
| Zipf b=3, base e, / Square | 21,248 | 10.457 |
| Zipf b=2, base 2, / Pair | 21,416 | 10.539 |
| Pair / Variable | 22,948 | 11.293 |
| Square / Variable | 23,245 | 11.439 |
| Triangle / Variable | 24,154 | 11.887 |
| Pair / Fixed | 24,492 | 12.053 |
| Square / Fixed | 24,071 | 11.846 |
| Triangle / Fixed | 25,086 | 12.346 |

Three findings, which answer the axes:

* **Pair wins.**  Combining the pair costs more than it saves in every row that
  can be compared.  Triangle can never win: it maps `N²` pairs into `2N²` values,
  so it spends a full bit per rule before any coding starts.  Square is not
  usable at all — it is *not injective*: `(0, 1)` and `(1, 0)` both give 0, and
  both orders occur in the list.  Its rows are shown only for completeness.
* **A `b`-bit interval index of a geometric ladder beats an arithmetic coder.**
  The best static code is 184 B smaller than the Zipf-arithmetic stream the
  format used to carry, and it needs no arithmetic coder: the decoder computes
  the interval edges from `N` and `b` with integer arithmetic
  (`N(2^i − 1) // 255` at base 2, `B = 2^b` intervals) and reads a
  variable-width residual inside the interval it lands in.  Nothing is stored for
  the code, and nothing is computed at start-up beyond those divisions.
* **Use the whole field.**  The design writes `base^b` in the index formula,
  which yields only `b` intervals and wastes most of a `b`-bit field; writing
  `base^(2^b)` — the reading in the table — is 3–4 kB better at `b = 2` and does
  not need `b` to be guessed.  `b = 3` is the optimum: `b = 4` costs 22,408 B
  and `b = 5` 24,439 B, because a wider index divides the range into intervals
  too narrow to carry their own residual.

The base matters little (2, e and √e are within 0.3 % of each other at `b = 3`),
so base 2 is the one to ship: its edges are exact integers.  The design's third
exponent is stated as `s = −ln√2` with `base = exp(0.5)`, but under
`base = 2^(−1/s)` it gives `exp(2)`; the table uses the stated bases, and
`exp(2)` measures 23,610 B at `b = 3`, worse by 13 %.

## 5. What the file deliberately omits

| omitted | why |
|---|---|
| counts, unigram, block totals | a model is a code; statistics belong in the build's own files (§7) |
| the stop as a symbol | the identifier ends in the top stage; the stop's row is the start state, its column nothing |
| the right cluster → word index | derivable from `memberships` in one pass |
| the left cluster of a word | its right cluster divided by `q` |
| the starting left cluster | a convention: 0 |
| codewords | canonical from the depths (`ENCODING.md` §3) |
| leaf order within a depth | canonical from the labels |
| padding and the terminator | fixed by the encoding, not by the model (`ENCODING.md` §2) |
| a version and a checksum | the magic is the version; the invariants are the check (§3) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 6. Worked example

The file in §2 is a complete model: `V = 7`, `k = 2`, `q = 2`, so `k·q = 4`
right clusters and two top trees of 5 leaves.  The characters `a`…`e` are ids
0–4, and words 5 and 6 are `bc` and `de`.  The right clusters are `{a}`,
`{b, bc}`, `{c, d, e}` and `{de}`; left cluster 0 is the first two and left
cluster 1 the last two.

The four bottom trees give the word step: right cluster 0 is a single symbol and
costs nothing; right cluster 1 gives `b`→`0`, `bc`→`1`; right cluster 2 gives
`c`→`1`, `d`→`00`, `e`→`01`; right cluster 3 is `de` alone and costs nothing.
Note the direction of the canonical rule: the deeper leaves take the low codes,
which is why `d` and `e` start with `0`.

The top trees hold 5 depths each, leaf 0 being the zero-weight STOP and leaves
1–4 right clusters 0–3.  After left cluster 0 (`[4, 1, 2, 3, 4]`): STOP→`0000`,
right cluster 0→`1`, 1→`01`, 2→`001`, 3→`0001`.  After left cluster 1
(`[4, 2, 1, 3, 4]`): STOP→`0000`, right cluster 0→`01`, 1→`1`, 2→`001`,
3→`0001`.

An identifier is coded as (right cluster | left cluster) then (symbol | right
cluster), and its first step **starts in left cluster 0**.  For `bc`, which is
ids 1 and 2: `b` is in right cluster 1, so the cluster step is right cluster 1
after left cluster 0, `01`, and the word step inside it is `0`; then `c` is in
right cluster 2 after left cluster 0 (since `b`'s label is 1), `001`, and inside
it `1`; finally the STOP leaf — `c`'s label is 2, so left cluster 1 — `0000`,
which is never written.  Eleven bits of codeword, seven stored: the last four
are zeros and join the padding.

The word step is free exactly where a right cluster was stopped at one symbol,
which is why right clusters 0 and 3 store no depths beyond a single `0`.
`python3 scripts/model_size.py --self-test` runs this model end to end, from the
depths to the bytes and back.

## 7. Distribution, and the map

**One standard model.**  The standard ships exactly one model file, fixing `V`,
`k` and `q`, and the file carries no `name:` or family: a second standard model
would be an `NVM2` question.  The format itself is general — a library user may
write a file at any `V`, `k` and `q` — because it describes a code rather than
the standard's choice of one.

**The counts live beside the file.**  A published model may sit in a directory
that also holds the counts it was built from (word frequencies, the
right-cluster totals, the held-out measurement), so a third party can re-derive
and audit the code without rebuilding the corpus.  Those files are
non-normative: a reader must not require them, and the model file must mean the
same thing without them.

**The grouping lives in the map.**  A tree's depths say nothing about which
symbols share a tree, so a model with more than one right cluster needs one
label per symbol.  Naming a right cluster by a *position* in the tree does not
work: a position marks a boundary in the tree's leaf order, so it names a
contiguous block of leaves, and the right clusters are whatever the build was
left with when it stopped merging — the survivors, which are not a run of
leaves.  So the label is the price of an arbitrary grouping.  What that price is
worth, and why one map serves both stages, is measured in
[`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md).
