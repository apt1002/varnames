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
plus enough header to identify the format, with the word trees of the quarter
code ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)):

| table (MODEL_BUDGET §1) | key | derivation |
|---|---|---|
| the word list, `V` index pairs | `rules:` | — |
| the word trees, `V` leaves over `qN` trees | `bottom_trees:`, `memberships:` | cell → words index; canonical codes |
| the cluster Huffman trees, `N` trees of `qN` leaves | `top_trees:` | canonical codes |
| the alphabet and the stop | `alphabet:`, `stop:` | — |
| — | `format:`, `version:`, `quarters:` | — |

There is **one assignment**: each word carries one cell label, `0 ≤ label < qN`,
in a cluster of `q` cells.  The cluster of a word is its cell label divided by
`q`, so there is no second label set to store; `N` and `q` are the two counts
that recover it.  The top stage is conditioned on that coarsening rather than on
the cell, which is why it is `N` trees of `qN` leaves and not `qN` trees of
`qN` — the asymmetry is where the quarter code's gain comes from, and it is why
the file needs both counts.

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
clusters: 2                   # N: clusters, one top tree each
quarters: 2                   # q: cells per cluster; q = 1 is the plain factored model
rules:                        # word ids follow the implicit symbols, in creation order
  - [0, 1]                    # id 6
  - [6, 2]                    # id 7
memberships: [0, 1, 2, 2, 2, 3, 1, 3]   # V labels: word id -> cell
bottom_trees:                 # qN trees, one per cell, words by ascending word id
  - [0]                       # cell 0: word 0 alone, so the word step is free
  - [1, 1]                    # cell 1: words 1, 6
  - [1, 2, 2]                 # cell 2: words 2, 3, 4
  - [1, 1]                    # cell 3: words 5, 7
top_trees:                    # one tree per left cluster, leaves by ascending cell id
  - [2, 3, 3, 1]              # after cluster 0: cells 0, 1, 2, 3
  - [1, 2, 3, 3]              # after cluster 1: cells 0, 1, 2, 3
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
* `clusters` — `N`, the number of clusters.  It fixes the number of top trees
  and, with `q`, the number of cells (`N·q`) and so the leaves in each top tree.
* `quarters` — `q`, the number of cells each cluster is cut into, so a cluster's
  words share a label block `c·q … c·q + q − 1`.  `q = 1` is the plain factored
  model.  The key is required, so that a file without it is an error rather than
  a second reading (§6).
* `rules` — the word list as pairs of child ids.  Entry *i* defines word id
  `len(alphabet) + 1 + i` (64 + *i* in version 1), and its children are strictly
  smaller ids, so the list is a topological order of the merge tree.  Rule *i*
  may not name its own id, and its two children must differ (no run words,
  `DICTIONARY_RULES.md`).
* `memberships` — one label per word id, `0 ≤ label < N·q`: the *shared* cell
  assignment (`SHARED_CLUSTERS.md`), stored once and used by both sides.  The
  cluster is `label // q`.  Together with `bottom_trees` it is table (b): the
  membership map and the unigram vector that the depths encode.
* `bottom_trees` — `N·q` depth sequences, numbered by cell.  Cell *c* holds its
  words in ascending word-id order, one depth each, measured from the **cell's**
  root; a cell with one word has that word at depth 0 and costs no bits at all.
  The decoder knows which words are in the cell from `memberships`, so no leaf
  list is stored, and the cell's code is a complete tree in its own right (a
  Huffman build stopped at `q` survivors).
* `top_trees` — `N` depth sequences of `N·q` entries each.  Tree *i* is the code
  for the next **cell** given left cluster *i*; its leaves are the cells in
  ascending id order.

### Invariants a reader must check

1. `len(memberships) == V` and `V = len(alphabet) + 1 + len(rules)`.
2. `len(bottom_trees) == N·q`, every word id appears in exactly one of their
   leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == N`, each with `N·q` entries, one per cell.
5. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + 1 + i`.
6. The stop is a leaf of exactly one bottom tree — the one for its cell.
7. Every cluster has exactly `q` non-empty cells, so `q` may not exceed the
   number of words in the smallest cluster.

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3: within a tree, sort leaves by `(length, label)`
and hand out integers in that order.

## 3. The binary form

Planned, in this order, all integers little-endian:

| section | encoding | bytes at `V = 8192, N = 16, q = 2` |
|---|---|---:|
| magic | `VNAM` | 4 |
| version | one byte | 1 |
| `V`, `N`, `q` | varints | 5–6 |
| `alphabet`, `stop` | 63 bytes + one byte | 64 |
| `rules` | 2 × (V − 64) child indices | see below |
| `memberships` | `⌈log₂ qN⌉` bits each, packed | 5,120 |
| `bottom_trees` | a depth-width byte, then `V` depths in cell order | 5,120 |
| `top_trees` | `N² q` depths at the same width, packed | 320 |
| checksum | CRC-32 of everything above | 4 |

Two encodings of the section that dominates, the rule table:

* **plain** — `⌈log₂ V⌉` bits per child, 13 at `V = 8,192`: 26,416 B.  Simple,
  obviously correct, and the form the round-trip tests use.
* **packed** — the child index is coded with the Zipf model of
  `MODEL_BUDGET.md` §4 (index `< *i*`, probability `∝ (j+1)^−0.7`): about 21 kB
  at `V = 8,192`, a saving of 19–22 %.  This is the number the budget quotes.

The rest of the file is 10.6 kB, so the model file is about **31.6 kB** at
`V = 8192, N = 16, q = 2` packed — against the 33.7 kB in `MODEL_BUDGET.md` §5.1,
which adds 2 kB of library code that is not part of the model.

The quarter code costs 1.2 kB of that: one more bit per cluster label (5 bits
instead of 4, since there are twice as many cells as clusters) and twice the top
depths (320 B instead of 160 B).  The alternative — deriving the cells from a cut
in the word tree, at about 26 B — was rejected because the cells of the quarter
build are subtrees of the *Huffman* tree, and this file stores only depths, from
which the reader derives the *canonical* tree; those two trees have the same
shape and different leaves, so a cut in the canonical tree is not the cell
([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md) §"The structural cost").

A 5-bit depth field covers trees of depth ≤ 31.  If a build exceeds it the
writer uses 6 bits and says so; at `V = 8,192` that costs 1 kB of depths.

## 4. What the file deliberately omits

| omitted | why |
|---|---|
| counts, unigram, block totals | a model is a code; statistics belong in the build's own files |
| the cluster → word index | derivable from `memberships` in one pass (`label // q`) |
| the cell → word index | one pass over `memberships` |
| codewords | canonical from the depths (`ENCODING.md` §3) |
| leaf order within a depth | canonical from the labels |
| padding and the terminator | fixed by the encoding, not by the model (`ENCODING.md` §2) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 5. Worked example

The file in §2 is a complete model: `V = 8`, `N = 2`, `q = 2`.  Symbol 5 is
`\n`; words 6 and 7 are `ab` and `abc`.  The cells are `{a}`, `{b, ab}`,
`{c, d, e}` and `{\n, abc}`, so cluster 0 is `{a, b, ab}` with cells 0 and 1,
and cluster 1 is `{c, d, e, \n, abc}` with cells 2 and 3.

The cell codes are the four bottom trees: cell 0 is a single word and costs
nothing, cell 1 gives `b`→`0`, `ab`→`1`, cell 2 gives `c`→`0`, `d`→`10`,
`e`→`11`, and cell 3 gives `\n`→`0`, `abc`→`1`.  The top trees are `[2, 3, 3, 1]`
after cluster 0, i.e. cell 3 → `0`, cell 0 → `10`, cells 1 and 2 → `110` and
`111`, and `[1, 2, 3, 3]` after cluster 1, i.e. cell 0 → `0`, cell 1 → `10`,
cell 2 → `110`, cell 3 → `111`.

An identifier is coded as (cell | left cluster) then (word | cell), and its cycle
starts at the stop, so the first top tree is the one for the stop's cluster.  For
`ab`: `\n`→`a` is cell 0 after cluster 1, `0`; `a`→`b` is cell 1 after cluster 0
then `b` inside it, `110 0`; `b`→`\n` is cell 3 after cluster 0 then `\n` inside
it, `0 0`.  Seven bits for three transitions, and the word step is free exactly
where the cluster was split down to a single word.

## 6. Versioning

`version` is an integer and changes only when the meaning of an existing key
changes or a key is removed.  Adding an optional key does not bump it; a reader
must reject a version it does not know, and must reject unknown keys rather than
ignore them, so that a file never means two things.  There are no optional keys
in version 1, which is why `quarters: 1` is spelled out for a plain factored
model rather than left out.

## 7. Open questions

* One model or a family: does the standard fix `V` and `N`, or ship `V ∈
  {4096, 6144, 8192}` as separate files with a `name:`?  The file format does
  not care, but the distribution does.
* **Cells that are subtrees of the stored tree.**  The label map costs 1.0 kB at
  the operating point and a cut in the word tree would cost 26 B.  It becomes
  available if a build splits the canonical tree — cutting at `q − 1` positions
  in its leaf order and re-coding each cell — instead of stopping the Huffman
  build early.  The code would be a little different (each cell rebuilt), so the
  saving needs its own measurement before it is claimed.
* Whether a second, non-normative file should carry the counts, so that a
  third party can re-derive the code and audit it without rebuilding the corpus.
