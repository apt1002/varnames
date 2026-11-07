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
| the cluster trees, `k` trees of `kq` leaves | `top_trees:` | canonical codes |
| the alphabet (ids 1…) | `alphabet:` | symbol 0 is the stop |
| — | `format:`, `version:`, `left_clusters:`, `right_clusters_per_left:` | — |

The code has two alphabets.  A word belongs to a **right cluster**, which is
what the word step codes; the `kq` right clusters are grouped `q` to a **left
cluster**, which is what the cluster step codes.  The top stage is therefore `k`
trees of `kq` leaves, not `kq` trees of `kq` — the asymmetry is where the
quarter code's gain comes from (`CLUSTER_QUARTERS.md`).

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
  - [2, 3, 3, 1]                       # after left cluster 0
  - [1, 2, 3, 3]                       # after left cluster 1
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
  once `q` is known.
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
* `top_trees` — `k` depth sequences of `k·q` entries each.  Tree *i* is the code
  for the next **right cluster** given left cluster *i*; its leaves are the right
  clusters in ascending id order.

### Invariants a reader must check

1. `len(memberships) == V` and `V = len(alphabet) + 1 + len(rules)`.
2. `len(bottom_trees) == k·q`, every symbol id `0 … V−1` appears in exactly one
   of their leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^(d_max − d) == 2^d_max` exactly, with every
   depth `≥ 0`.
4. `len(top_trees) == k`, each with `k·q` entries, one per right cluster.
5. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + 1 + i`.
6. Symbol 0 (the stop) is a leaf of exactly one bottom tree — the one for its
   right cluster.
7. Every left cluster has exactly `q` non-empty right clusters, so `q` may not
   exceed the number of words in the smallest left cluster.

The canonical codes then follow from the depths by the rule in
[`ENCODING.md`](ENCODING.md) §3: within a tree, sort leaves by `(length, label)`
and hand out integers in that order.

## 3. The binary form

Planned, in this order, all integers little-endian:

| section | encoding | bytes at `V = 8192, k = 16, q = 2` |
|---|---|---:|
| magic | `VNAM` | 4 |
| version | one byte | 1 |
| `V`, `k`, `q` | varints | 5–6 |
| `alphabet` | 63 bytes, ids 1–63 | 63 |
| `rules` | 2 × (V − 64) child indices | see below |
| `memberships` | `⌈log₂ kq⌉` bits each, packed | 5,120 |
| `bottom_trees` | a depth-width byte, then `V` depths in right-cluster order | 5,120 |
| `top_trees` | `k² q` depths at the same width, packed | 320 |
| checksum | CRC-32 of everything above | 4 |

Two encodings of the section that dominates, the rule table:

* **plain** — `⌈log₂ V⌉` bits per child, 13 at `V = 8,192`: 26,416 B.  Simple,
  obviously correct, and the form the round-trip tests use.
* **packed** — the child index is coded with the Zipf model of
  `MODEL_BUDGET.md` §4 (index `< *i*`, probability `∝ (j+1)^−0.7`): about 21 kB
  at `V = 8,192`, a saving of 19–22 %.  This is the number the budget quotes.

The rest of the file is 10.6 kB, so the model file is about **31.6 kB** at
`V = 8192, k = 16, q = 2` packed — against the 33.7 kB in `MODEL_BUDGET.md` §5.1,
which adds 2 kB of library code that is not part of the model.

The quarter code costs 1.2 kB of that: one more bit per label (5 bits instead of
4, since a right cluster is one of twice as many), and twice the top depths
(320 B instead of 160 B).  The label is not avoidable: a depth list cannot say
which symbols share a tree, and no position in the tree can stand in for it (§7).

A 5-bit depth field covers trees of depth ≤ 31.  If a build exceeds it the
writer uses 6 bits and says so; at `V = 8,192` that costs 1 kB of depths.

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

The file in §2 is a complete model: `V = 8`, `k = 2`, `q = 2`.  Symbol 0 is the
stop (`\n`), the characters `a`…`e` are ids 1–5, and words 6 and 7 are `ab` and
`abc`.  The right clusters are `{a}`, `{b, ab}`, `{c, d, e}` and `{stop, abc}`;
left cluster 0 is the first two and left cluster 1 the last two.

The four bottom trees give the word step: right cluster 0 is a single symbol and
costs nothing, right cluster 1 gives `b`→`0`, `ab`→`1`, right cluster 2 gives
`c`→`0`, `d`→`10`, `e`→`11`, and right cluster 3 gives the stop→`0`, `abc`→`1`.
The stop's `0` is the all-zeros path, which is what makes the zero padding past
the budget read as a terminator (`ENCODING.md` §2).  The top trees are
`[2, 3, 3, 1]` after left cluster 0, i.e. right cluster 3 → `0`, right cluster 0
→ `10`, right clusters 1 and 2 → `110` and `111`, and `[1, 2, 3, 3]` after left
cluster 1, i.e. right cluster 0 → `0`, 1 → `10`, 2 → `110`, 3 → `111`.

An identifier is coded as (right cluster | left cluster) then (symbol | right
cluster), and its cycle starts at the stop, so the first top tree is the one for
the stop's left cluster.  For `ab`: stop→`a` is right cluster 0 after left
cluster 1, `0`; `a`→`b` is right cluster 1 after left cluster 0 then `b` inside
it, `110 0`; `b`→stop is right cluster 3 after left cluster 0 then the stop
inside it, `0 0`.  Seven bits for three transitions, and the word step is free
exactly where the tree was stopped at a single symbol.

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
write a file at any `V`, `k` and `q`, including `q = 1` — because it describes a
code rather than the standard's choice of one.

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
