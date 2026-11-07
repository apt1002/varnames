# The model file

Status: **format version 1 specified; no codec yet.**  The model is published as
a portable, uncompressed YAML file; a binary form is derived from it, and its
size is what the budget measures.  The codec and the measurement are planned
work (H12), and the size oracle will report the inventory from it (H11).

The YAML is the normative description of a model's *meaning*; the binary form is
normative for its *bytes*, and is a deterministic function of the YAML, so a
published binary can be checked by converting it back.  Nothing in the file
depends on how the model was generated: a build that changes nothing produces a
byte-identical file.

## 1. What the file contains

It is the three published tables of [`MODEL_BUDGET.md`](MODEL_BUDGET.md) §1,
plus enough header to identify the format:

| table (MODEL_BUDGET §1) | key | derivation |
|---|---|---|
| the word list, `V` index pairs | `rules:` | — |
| the word trees, `V` leaves over `kq` trees | `bottom_trees:`, `memberships:` | right cluster → words; canonical codes |
| the cluster trees, `k` trees of `kq + 1` leaves | `top_trees:` | canonical codes; leaf 0 is the terminator |
| the alphabet (ids 1…) | `alphabet:` | symbol 0 is the stop |
| — | `format:`, `version:`, `left_clusters:`, `right_clusters_per_left:` | — |

The code has two alphabets.  A word belongs to a **right cluster**, which is
what the word step codes; the `kq` right clusters are grouped `q` to a **left
cluster**, which is what the cluster step codes.  The top stage is therefore `k`
trees of `kq` leaves, not `kq` trees of `kq` — the asymmetry is where the
quarter code's gain comes from (`CLUSTER_QUARTERS.md`).

Each top tree has one leaf more than there are right clusters: a zero-weight
**STOP** leaf, listed first.  It is never emitted — the padding is what the
decoder reads there — and it is what makes the identifier end for free.  A
bottom tree's terminator leaf is the stop itself (symbol 0), which is likewise
never read: the end of an identifier is signalled in the top stage, before any
word step.

The file still stores **one map**: each word's right cluster.  Its left cluster
is that label divided by `q`, so the second alphabet costs no second table — one
label per word at `⌈log₂ kq⌉` bits instead of `⌈log₂ k⌉`, 5 bits instead of 4 at
the operating point, and the two counts `k` and `q`.

Symbol 0 is always the stop, so the file never has to name it: the characters
begin at id 1, words follow them, and `V = len(alphabet) + 1 + len(rules)`
counts the stop among the implicit symbols.

A model is a **code, not a statistic**: no counts, no unigram, no corpus
fingerprint.  Everything the decoder needs is either in the file or derivable
from it.  The `V`-entry unigram of the arithmetic variant is deliberately absent
— the depths are what replaces it (`MODEL_BUDGET.md` §5.2).

## 2. The schema

```yaml
format: varnames-model                 # literal, identifies the file
version: 1                             # integer; see §6
alphabet: "abcde"                      # characters, ids 1..5; id 0 is the stop
left_clusters: 2                       # k: one top tree per left cluster
right_clusters_per_left: 2             # q: right clusters per left cluster
rules:                                 # word ids follow the implicit symbols
  - [0, 1]                             # id 6
  - [6, 2]                             # id 7
memberships: [3, 0, 1, 2, 2, 2, 1, 3]  # V labels: symbol id -> right cluster
bottom_trees:                          # k*q trees, one per right cluster
  - [0]                                # right cluster 0: symbol 1 alone
  - [1, 1]                             # right cluster 1: symbols 2, 6
  - [1, 2, 2]                          # right cluster 2: symbols 3, 4, 5
  - [1, 1]                             # right cluster 3: symbols 0, 7
top_trees:                             # one tree per left cluster
  - [4, 1, 2, 3, 4]                    # leaf 0 is STOP; then right clusters 0-3
  - [4, 2, 1, 3, 4]                    # after left cluster 1
```

Every sequence is a YAML sequence of integers; the file is ASCII with LF
newlines, two-space indentation, and no anchors, aliases, tags or maps other
than the top level.  A writer may add comments and blank lines; a reader must
ignore them.

The numbering is the **file's**.  A build usually numbers its characters
`0 … 62` and its stop `63`; the codec shifts the characters by one, maps the
stop to `0`, and leaves the word ids alone.  Only the file's numbering is
normative, and `rules:` children use it.

### The keys

* `alphabet` — the characters the model can code, as ids `1 … len(alphabet)`.
  The shipped model uses the 63 ASCII characters that occur in identifiers (ids
  1–63); the field is carried explicitly so a reader can check the file against a
  corpus instead of assuming that set.  A toy model may use fewer.  **Symbol 0 is
  the stop** (`\n`): it is the id the format reserves, its codeword is the
  all-zeros path and is never written (`ENCODING.md` §2), and so it needs no key
  of its own.  No character may claim id 0.
* `left_clusters` — `k`, the number of left clusters.  It fixes the number of
  top trees, the left-hand alphabet, and the length of each `top_trees` entry
  once `q` is known (`k·q + 1`).
* `right_clusters_per_left` — `q`, the number of right clusters per left
  cluster.  It fixes the right-hand alphabet, `k·q`, and so the number of
  `bottom_trees` entries.  `q = 1` makes the two alphabets one, which is the
  plain factored model.  The key is required, so that a file without it is an
  error rather than a second reading (§6).
* `rules` — the word list as pairs of child ids.  Entry *i* defines word id
  `len(alphabet) + 1 + i` (64 + *i* in version 1), and its children are strictly
  smaller ids, so the list is a topological order of the merge tree.  Rule *i*
  may not name its own id, and its two children must differ (no run words,
  `DICTIONARY_RULES.md`).
* `memberships` — one label per symbol id, the stop included, `0 ≤ label <
  k·q`: that symbol's right cluster.  Labels `c·q … c·q + q − 1` are the right
  clusters of left cluster `c`, so the left cluster is that label divided by
  `q`.  This is the one assignment the model stores, and with `bottom_trees` it
  is table (b): the membership map and the unigram vector that the depths
  encode.
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

1. `len(memberships) == V` and `V = len(alphabet) + 1 + len(rules)`.
2. `len(bottom_trees) == k·q`, every symbol id `0 … V−1` appears in exactly one
   of their leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == k`, each with `k·q + 1` entries: the STOP leaf and one per
   right cluster.
5. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + 1 + i`.
6. Symbol 0 (the stop) is a leaf of exactly one bottom tree — the one for its
   right cluster.
7. A left cluster has at most `q` non-empty right clusters.  Fewer is legal — a
   right cluster with one word cannot be split further — and an empty one is an
   empty depth list and never decodes.  The shipped build is `q = 1`, so every
   left cluster has exactly one non-empty right cluster.
8. In every top tree, leaf 0 (STOP) is at the **maximum** depth, and in the
   bottom tree that holds the stop, symbol 0 is at the maximum depth.  Both
   follow from giving those two leaves zero weight, and together they are what
   makes the padding decode as the terminator (§5).

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3, in one form for both stages: **the all-zeros
codeword belongs to the first leaf at the maximum depth**, the remaining codes
are handed out in *ascending* depth order from the top of the code space (the
mirror image of the usual DEFLATE convention), and within a depth the leaves
ascend by label.  Invariant 8 is what makes the first leaf at the maximum depth
be the terminator, so neither the encoder nor the decoder needs an orientation
table.

## 3. The binary form

Measured, not estimated: `scripts/model_size.py` writes the model, packs it in
this order and reports the bytes of each section.  The figures are at
`V = 8192, k = 32, q = 1`, the operating point, with the packed rule table.

| section | encoding | bytes |
|---|---|---:|
| magic | `VNAM` | 4 |
| version | one byte | 1 |
| `V`, `k`, `q`, `len(alphabet)` | varints | 5 |
| rules length | a varint, because the rule stream is not self-delimiting | 3 |
| `rules` | 2 × (V − 64) child indices, Zipf-arithmetic-coded | 21,145 |
| `alphabet` | `len(alphabet)` bytes, ids 1–63 | 63 |
| `memberships` | `⌈log₂ k⌉` = 5 bits each, packed | 5,120 |
| depth width | one byte, in bits | 1 |
| `bottom_trees` | `V` depths at that width, right cluster by right cluster, ascending symbol id inside | 5,120 |
| `top_trees` | `k(k + 1)` = 1,056 depths at the same width | 660 |
| CRC-32 | of everything above | 4 |
| **total** | | **32,126** |

Two encodings of the section that dominates, the rule table:

* **plain** — `⌈log₂ V⌉` bits per child, 13 at `V = 8,192`: 26,416 B, and the
  whole file 37,397 B.  Simple, obviously correct, and the form the round-trip
  tests use.
* **packed** — the child index is coded with the Zipf model of
  `MODEL_BUDGET.md` §4 (index `< i`, probability `∝ (j+1)^−0.7`, truncated to the
  symbols defined so far): **21,145 B**, 20 % less, and 69 % of the file.  The
  decoder derives the same frequencies from `V` alone, so the coder costs no
  table.  This is the number the budget quotes.

Bits are packed **least-significant first within a byte**: bit *i* of the stream
is bit *i* mod 8 of byte *i* // 8, and bit 0 of the code is the first bit an
encoder writes, so the padding of `ENCODING.md` §2 is the run of zeros *above*
the code.  Integers are little-endian.

The rest of the file is 10,981 B, so the model is **32.1 kB** — against the
34.2 kB of `MODEL_BUDGET.md` §5.1, which adds 2 kB of library code that is not
part of the model.  The YAML of §2 is 181,575 B at the same point — 5.7 times
as large: it is the portable form, and the binary is what the budget measures.

A model with `q > 1` pays 1.7 kB at this point: one more bit per label (6 bits
instead of 5, since a right cluster is one of twice as many), and twice the top
depths (1,300 B instead of 660 B, the STOP leaf included).  It is the label that
dominates, and it is not avoidable: a depth list cannot say which symbols share
a tree, and no position in the tree can stand in for it (§7).  Measured, the
quarters do not repay it (`CLUSTER_QUARTERS.md`).

The depth width is **5 bits measured, not assumed**: the deepest bottom tree is
21 at `V = 8192, k = 32` and the deepest top tree 19, and the same 5 bits holds
on the whole measured grid.  A build that exceeded depth 31 would have to be
length-limited or use 6 bits, which costs 1 kB; neither is needed.

## 4. What the file deliberately omits

| omitted | why |
|---|---|
| counts, unigram, block totals | a model is a code; statistics belong in the build's own files (§7) |
| the right cluster → word index | derivable from `memberships` in one pass |
| the left cluster of a word | its right cluster divided by `q` |
| codewords | canonical from the depths (`ENCODING.md` §3) |
| leaf order within a depth | canonical from the labels |
| padding and the terminator | fixed by the encoding, not by the model (`ENCODING.md` §2) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 5. Worked example

The file in §2 is a complete model: `V = 8`, `k = 2`, `q = 2`, so `k·q = 4`
right clusters and two top trees of 5 leaves.  Symbol 0 is the stop (`\n`), the
characters `a`…`e` are ids 1–5, and words 6 and 7 are `ab` and `abc`.  The right
clusters are `{a}`, `{b, ab}`, `{c, d, e}` and `{stop, abc}`; left cluster 0 is
the first two and left cluster 1 the last two.

The four bottom trees give the word step: right cluster 0 is a single symbol and
costs nothing; right cluster 1 gives `b`→`0`, `ab`→`1`; right cluster 2 gives
`c`→`1`, `d`→`00`, `e`→`01`; right cluster 3 gives the stop→`0`, `abc`→`1`.
Note the direction of the canonical rule (invariant 8): the deeper leaves take
the low codes, which is why `d` and `e` start with `0`.

The top trees hold 5 depths each, leaf 0 being the zero-weight STOP and leaves
1–4 right clusters 0–3.  After left cluster 0 (`[4, 1, 2, 3, 4]`): STOP→`0000`,
right cluster 0→`1`, 1→`01`, 2→`001`, 3→`0001`.  After left cluster 1
(`[4, 2, 1, 3, 4]`): STOP→`0000`, right cluster 0→`01`, 1→`1`, 2→`001`,
3→`0001`.

An identifier is coded as (right cluster | left cluster) then (symbol | right
cluster), and its cycle starts at the stop, so the first top tree is the one
after the stop's left cluster — the stop is in right cluster 3, so left cluster
1.  For `ab`: stop→`a` is right cluster 0 after left cluster 1, `01`, and `a`
inside right cluster 0 is free; `a`→`b` is right cluster 1 after left cluster 0,
`01`, then `b` inside it, `0`; and `b`→stop is the STOP leaf in left cluster 0,
`0000`, which is never written.  Five bits of codeword, four stored — the last
is a zero and joins the padding — and the word step is free exactly where the
tree was stopped at a single symbol.  `python3 scripts/model_size.py
--self-test` runs this file end to end, from the depths to the bytes and back.

## 6. Versioning

`version` is an integer and changes only when the meaning of an existing key
changes or a key is removed.  Adding an optional key does not bump it; a reader
must reject a version it does not know, and must reject unknown keys rather than
ignore them, so that a file never means two things.  There are no optional keys
in version 1, which is why `right_clusters_per_left: 1` is spelled out for a
plain factored model rather than left out.

## 7. Distribution, the counts, and the map

**One standard model.**  The standard ships exactly one model file, fixing `V`,
`k` and `q`, and the file carries no `name:` or family: a second standard model
would be a version-2 question.  The format itself is general — a library user may
write a file at any `V`, `k` and `q`, with `q = 1` the shipped choice — because
it describes a code rather than the standard's choice of one.

**The counts live beside the file.**  A published model may sit in a directory
that also holds the counts it was built from (word frequencies, the right-cluster
totals, the held-out measurement), so a third party can re-derive and audit the
code without rebuilding the corpus.  Those files are non-normative: a reader must
not require them, and the model file must mean the same thing without them.

**The grouping lives in the map.**  Settled, and it is what the 1,024 B buys.
A tree's depths say nothing about which symbols share a tree, so a model with
more than one right cluster needs one label per symbol.  Naming a right cluster
by a *position* in the tree does not work: a position marks a boundary in the
tree's leaf order, so it names a contiguous block of leaves, and the right
clusters are whatever the build was left with when it stopped merging — the
survivors, which are not a run of leaves.  Splitting at a boundary would be the
imposed partition that `CLUSTER_QUARTERS.md` §"The experiment", step 3, rules
out, and it would change the code rather than describe it.  So the
label is the price of an arbitrary grouping, which is the grouping the quarter
code needs.
