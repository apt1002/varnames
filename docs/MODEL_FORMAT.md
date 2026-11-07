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
| the shared Huffman trees, `V` leaves over `k` trees | `bottom_trees:`, `memberships:` | cluster → words index; canonical codes |
| the cluster Huffman trees, `k` leaves over `k` trees | `top_trees:` | canonical codes |
| the alphabet and the stop | `alphabet:`, `stop:` | — |
| — | `format:`, `version:` | — |

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
clusters: 2                   # k
quarters: 1                   # q; 1 = the plain factored code
rules:                        # word ids follow the implicit symbols, in creation order
  - [0, 1]                    # id 6
  - [6, 2]                    # id 7
memberships: [0, 0, 1, 1, 1, 1, 0, 1]   # V labels: word id -> cluster
bottom_trees:                 # one tree per cluster, leaves by ascending word id
  - [1, 2, 2]                 # cluster 0: words 0, 1, 6
  - [2, 2, 2, 3, 3]           # cluster 1: words 2, 3, 4, 5, 7
top_trees:                    # one tree per left cluster, leaves by ascending (cluster, quarter)
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
* `clusters`, `quarters` — `k` and `q`.  `quarters: 1` is the plain factored
  code; `q > 1` is the quarter code, where each right cluster is split into `q`
  cells and the top stage has `q·k` leaves
  ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)).
* `rules` — the word list as pairs of child ids.  Entry *i* defines word id
  `len(alphabet) + 1 + i` (64 + *i* in version 1), and its children are strictly
  smaller ids, so the list is a topological order of the merge tree.  Rule *i*
  may not name its own id, and its two children must differ (no run words,
  `DICTIONARY_RULES.md`).
* `memberships` — one label per word id, `0 ≤ label < k`; the *shared* cluster
  assignment (`SHARED_CLUSTERS.md`), used by both sides.  Together with
  `bottom_trees` it is table (b): the membership map and the unigram vector that
  the depths encode.
* `bottom_trees` — `k` depth sequences.  Tree *j* holds the words of cluster *j*
  in ascending word-id order, one depth each, measured from the cluster tree's
  root.  The decoder knows which words those are from `memberships`, so no leaf
  list is stored.  The bottom stage is the same at every `q`.
* `cuts` — absent when `q = 1`.  For each cluster, the `q − 1` boundaries that
  divide the cluster tree's leaves, in canonical order, into the `q` cells of
  the quarter code: strictly increasing integers in `1 … size − 1`.  Cell *r* of
  cluster *i* is the *r*-th run of leaves, and a word's code length in it is its
  stored depth minus the depth of the cell's root.  This is enough to label every
  cell `(cluster, quarter)` for the top stage.
* `top_trees` — `k` depth sequences of `q·k` entries each.  Tree *i* is the code
  for the next cell given left cluster *i*; its leaves are the cells in
  ascending `(cluster, quarter)` order.

### Invariants a reader must check

1. `len(memberships) == V` and `V = len(alphabet) + 1 + len(rules)`.
2. Every word id appears in exactly one `bottom_trees` leaf, in ascending order,
   and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == k`, each with `q·k` entries, one per cell.
5. `cuts` is absent when `q = 1`; otherwise it has `k` entries of `q − 1`
   strictly increasing boundaries, each within its cluster's leaf count.
6. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + 1 + i`.
7. The stop is a leaf of exactly one bottom tree — the one for its cluster.

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3: within a tree, sort leaves by `(length, label)`
and hand out integers in that order.

## 3. The binary form

Planned, in this order, all integers little-endian:

| section | encoding | bytes at `V = 8192, k = 16, q = 1` |
|---|---|---:|
| magic | `VNAM` | 4 |
| version | one byte | 1 |
| `V`, `k`, `q` | varints | 4–5 |
| `alphabet`, `stop` | 63 bytes + one byte | 64 |
| `rules` | 2 × (V − 64) child indices | see below |
| `memberships` | `⌈log₂ k⌉` bits each, packed | 4,096 |
| cell cuts | `q − 1` canonical-order boundaries per cluster, `⌈log₂ V⌉` bits each; absent at `q = 1` | 0 at `q = 1`; ~50 at `q = 2` |
| `bottom_trees` | a depth-width byte, then `V` depths | 5,120 |
| `top_trees` | `k²` depths at the same width | 160 |
| checksum | CRC-32 of everything above | 4 |

Two encodings of the section that dominates, the rule table:

* **plain** — `⌈log₂ V⌉` bits per child, 13 at `V = 8,192`: 26,416 B.  Simple,
  obviously correct, and the form the round-trip tests use.
* **packed** — the child index is coded with the Zipf model of
  `MODEL_BUDGET.md` §4 (index `< *i*`, probability `∝ (j+1)^−0.7`): about 21 kB
  at `V = 8,192`, a saving of 19–22 %.  This is the number the budget quotes.

The rest of the file is 9.4 kB, so the model file is about **30.5 kB** at
`V = 8192, k = 16` packed — against the 32.5 kB in `MODEL_BUDGET.md` §5.1, which
adds 2 kB of library code that is not part of the model.

At `q = 2` the bottom trees are the same as at `q = 1` and the top stage grows
by 160 B (`k²` → `k·qk` depths); the cuts cost ~50 B.  That is the 252 B
increment `CLUSTER_QUARTERS.md` prices, and the frontier's 32.6 kB for that cell
is this plus the 2 kB of library code.

A 5-bit depth field covers trees of depth ≤ 31.  If a build exceeds it the
writer uses 6 bits and says so; at `V = 8,192` that costs 1 kB of depths.

## 4. What the file deliberately omits

| omitted | why |
|---|---|
| counts, unigram, block totals | a model is a code; statistics belong in the build's own files |
| the cluster → word index | derivable from `memberships` in one pass |
| codewords | canonical from the depths (`ENCODING.md` §3) |
| leaf order within a depth | canonical from the labels |
| which cell a word belongs to | derivable from `cuts` and the tree |
| padding and the terminator | fixed by the encoding, not by the model (`ENCODING.md` §2) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 5. Worked example

The file in §2 is a complete model: `V = 8`, `k = 2`, `q = 1`.  Symbol 5 is
`\n`; words 6 and 7 are `ab` and `abc`.  Cluster 0 holds `a`, `b`, `ab`;
cluster 1 holds `c`, `d`, `e`, `\n`, `abc`.  Bottom tree 0 (`[1, 2, 2]`) is
`a`→`0`, `b`→`10`, `ab`→`11`; bottom tree 1 (`[2, 2, 2, 3, 3]`) is
`c`→`00`, `d`→`01`, `e`→`10`, `\n`→`110`, `abc`→`111`; the top trees are
`0`→`0`, `1`→`1`.  An identifier is coded as (cell | left cluster) then
(word | cell); the first top tree is the row of the cluster holding the stop,
because the identifier's cycle starts at the stop.

## 6. Versioning

`version` is an integer and changes only when the meaning of an existing key
changes or a key is removed.  Adding an optional key does not bump it; a reader
must reject a version it does not know, and must reject unknown keys rather than
ignore them, so that a file never means two things.  Fields that carry no
information at the current settings (`cuts` when `q = 1`) are omitted rather
than written empty.

## 7. Open questions

* One model or a family: does the standard fix `V` and `k`, or ship `V ∈
  {4096, 6144, 8192}` as separate files with a `name:`?  The file format does
  not care, but the distribution does.
* Whether the shipped code is the plain factored code or CQF `q = 2` — the
  format carries both, and the frontier currently has `q = 2` ahead by 0.9
  points for 252 bytes (`MODEL_BUDGET.md` §6).
* Whether a second, non-normative file should carry the counts, so that a
  third party can re-derive the code and audit it without rebuilding the corpus.
