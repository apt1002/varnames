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
| the shared Huffman trees, `V` leaves over `N` trees | `bottom_trees:`, `memberships:` | cluster → words index; canonical codes |
| the cluster Huffman trees, `N` leaves over `N` trees | `top_trees:` | canonical codes |
| the alphabet and the stop | `alphabet:`, `stop:` | — |
| — | `format:`, `version:` | — |

There is **one count**, `N` (the file's `clusters:`): `N` bottom trees, `V` leaves
between them, and `N` leaves in every top tree.  A model cannot have more
right-hand symbols than left-hand ones, because the assignment is shared by both
sides — so no separate count for the two stages, and no `q` (see §7).

A model is a **code, not a statistic**: no counts, no unigram, no corpus
fingerprint.  Everything the decoder needs is either in the file or derivable
from it.  The `V`-entry unigram of the arithmetic variant is deliberately absent
— the depths are what replaces it (`MODEL_BUDGET.md` §5.2).

## 2. The schema

```yaml
format: varnames-model        # literal, identifies the file
version: 1                    # integer; see §6
alphabet: "abcde"             # the characters, in symbol-id order (0, 1, ...)
stop: 5                       # symbol id of the stop character (here "\n")
clusters: 2                   # N: bottom trees, and leaves per top tree
rules:                        # word ids follow the implicit symbols, in creation order
  - [0, 1]                    # id 6
  - [6, 2]                    # id 7
memberships: [0, 0, 1, 1, 1, 1, 0, 1]   # V labels: word id -> cluster
bottom_trees:                 # one tree per cluster, leaves by ascending word id
  - [1, 2, 2]                 # cluster 0: words 0, 1, 6
  - [2, 2, 2, 3, 3]           # cluster 1: words 2, 3, 4, 5, 7
top_trees:                    # one tree per left cluster, leaves by ascending cluster id
  - [1, 1]
  - [1, 1]
```

Every sequence is a YAML sequence of integers; the file is ASCII with LF
newlines, two-space indentation, and no anchors, aliases, tags or maps other
than the top level.  A writer may add comments and blank lines; a reader must
ignore them.

### The keys

* `alphabet` — the characters the model can code, in id order.  The shipped
  model uses the 63 ASCII characters that occur in identifiers and the stop is
  the next id, 63; the field is carried explicitly so a reader can check the file
  against a corpus instead of assuming that set.  A toy model may use fewer.
* `stop` — the id of the character that ends an identifier (`\n`).  Its
  codeword is all zeros and is never written (`ENCODING.md` §2).
* `clusters` — `N`, the number of clusters.  It fixes three things at once: the
  number of bottom trees, the number of leaves in each top tree, and the number
  of labels in `memberships`.
* `rules` — the word list as pairs of child ids.  Entry *i* defines word id
  `len(alphabet) + 1 + i` (64 + *i* in version 1), and its children are strictly
  smaller ids, so the list is a topological order of the merge tree.  Rule *i*
  may not name its own id, and its two children must differ (no run words,
  `DICTIONARY_RULES.md`).
* `memberships` — one label per word id, `0 ≤ label < k`; the *shared* cluster
  assignment (`SHARED_CLUSTERS.md`), used by both sides.  Together with
  `bottom_trees` it is table (b): the membership map and the unigram vector that
  the depths encode.
* `bottom_trees` — `N` depth sequences.  Tree *j* holds the words of cluster *j*
  in ascending word-id order, one depth each, measured from the cluster tree's
  root.  The decoder knows which words those are from `memberships`, so no leaf
  list is stored.
* `top_trees` — `N` depth sequences of `N` entries each.  Tree *i* is the code
  for the next cluster given left cluster *i*; its leaves are the clusters in
  ascending id order.

### Invariants a reader must check

1. `len(memberships) == V` and `V = len(alphabet) + 1 + len(rules)`.
2. `len(bottom_trees) == N`, every word id appears in exactly one of their
   leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == N`, each with `N` entries, one per cluster.
5. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + 1 + i`.
6. The stop is a leaf of exactly one bottom tree — the one for its cluster.

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3: within a tree, sort leaves by `(length, label)`
and hand out integers in that order.

## 3. The binary form

Planned, in this order, all integers little-endian:

| section | encoding | bytes at `V = 8192, N = 16` |
|---|---|---:|
| magic | `VNAM` | 4 |
| version | one byte | 1 |
| `V`, `N` | varints | 4–5 |
| `alphabet`, `stop` | 63 bytes + one byte | 64 |
| `rules` | 2 × (V − 64) child indices | see below |
| `memberships` | `⌈log₂ N⌉` bits each, packed | 4,096 |
| `bottom_trees` | a depth-width byte, then `V` depths | 5,120 |
| `top_trees` | `N²` depths at the same width | 160 |
| checksum | CRC-32 of everything above | 4 |

Two encodings of the section that dominates, the rule table:

* **plain** — `⌈log₂ V⌉` bits per child, 13 at `V = 8,192`: 26,416 B.  Simple,
  obviously correct, and the form the round-trip tests use.
* **packed** — the child index is coded with the Zipf model of
  `MODEL_BUDGET.md` §4 (index `< *i*`, probability `∝ (j+1)^−0.7`): about 21 kB
  at `V = 8,192`, a saving of 19–22 %.  This is the number the budget quotes.

The rest of the file is 9.4 kB, so the model file is about **30.5 kB** at
`V = 8192, N = 16` packed — against the 32.5 kB in `MODEL_BUDGET.md` §5.1, which
adds 2 kB of library code that is not part of the model.

The quarter code has no encoding here, and that is a finding rather than an
omission: it refines only the right-hand side, which a shared label set cannot
express (§7).

A 5-bit depth field covers trees of depth ≤ 31.  If a build exceeds it the
writer uses 6 bits and says so; at `V = 8,192` that costs 1 kB of depths.

## 4. What the file deliberately omits

| omitted | why |
|---|---|
| counts, unigram, block totals | a model is a code; statistics belong in the build's own files |
| the cluster → word index | derivable from `memberships` in one pass |
| codewords | canonical from the depths (`ENCODING.md` §3) |
| leaf order within a depth | canonical from the labels |
| padding and the terminator | fixed by the encoding, not by the model (`ENCODING.md` §2) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 5. Worked example

The file in §2 is a complete model: `V = 8`, `N = 2`.  Symbol 5 is
`\n`; words 6 and 7 are `ab` and `abc`.  Cluster 0 holds `a`, `b`, `ab`;
cluster 1 holds `c`, `d`, `e`, `\n`, `abc`.  Bottom tree 0 (`[1, 2, 2]`) is
`a`→`0`, `b`→`10`, `ab`→`11`; bottom tree 1 (`[2, 2, 2, 3, 3]`) is
`c`→`00`, `d`→`01`, `e`→`10`, `\n`→`110`, `abc`→`111`; the top trees are
`0`→`0`, `1`→`1`.  An identifier is coded as (cluster | left cluster) then
(word | cluster); the first top tree is the row of the cluster holding the stop,
because the identifier's cycle starts at the stop.

## 6. Versioning

`version` is an integer and changes only when the meaning of an existing key
changes or a key is removed.  Adding an optional key does not bump it; a reader
must reject a version it does not know, and must reject unknown keys rather than
ignore them, so that a file never means two things.  There are no optional keys
in version 1.

## 7. Open questions

* One model or a family: does the standard fix `V` and `N`, or ship `V ∈
  {4096, 6144, 8192}` as separate files with a `name:`?  The file format does
  not care, but the distribution does.
* **The quarter code does not fit this structure**, and the format says so by
  not carrying `q`.  It gives the left side `k` labels and the right side `qk`
  cells, so the two label sets differ; a shared assignment requires them to be
  one set, which is why a `qk`-leaf top stage implies `qk` trees on both sides.
  The symmetric alternative is the plain factored model with `N = qk` clusters —
  expressible here as `clusters: 32` — and at `V = 8192` that costs 2,816 B over
  `N = 16` for +0.3 arithmetic fit points, where the quarter code claims 252 B
  for +0.9.  Whether the asymmetry is worth a second label set is the open
  question, and it belongs to `CLUSTER_QUARTERS.md` §"The structural cost", not
  to this file.
* Whether a second, non-normative file should carry the counts, so that a
  third party can re-derive the code and audit it without rebuilding the corpus.
