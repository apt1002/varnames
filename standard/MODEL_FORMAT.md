# The model file

Status: **`NVM1` specified; implemented.**  The model is published as a
portable, uncompressed YAML file; a binary form is derived from it, and its size
is what the budget measures.  `scripts/model_size.py` writes the YAML, packs it,
reads it back and decodes held-out identifiers through the packed file.
Illustrative byte counts quoted here are measurements of the default model: a
working artefact.

The YAML is the normative description of a model's *meaning*; the binary form is
normative for its *bytes*, and is a deterministic function of the YAML, so a
published binary can be checked by converting it back.  Nothing in the file
depends on how the model was generated: any build that produces the same tables
produces a byte-identical file.

## 1. What the file contains

The file is a code.  Decoding an integer reads its bits starting at the least
significant one, emits characters, and may read zeros beyond the highest stored
bit — that padding is the terminator, and it costs nothing.  The algorithm is:

* **Start in left cluster 0.**
* **Read a codeword in that left cluster's top tree.**  If the codeword is the
  all-zeros leaf, the identifier has ended.
* **Otherwise the leaf names a right cluster.**  Read a codeword in that right
  cluster's bottom tree; it names a *word*.  Walk the word depth-first,
  emitting its characters.
* **Continue from the left cluster of that word**, which is its right cluster
  divided by `q`.

The top tree / bottom tree separation is the clustering optimisation: the
top tree says *which group of words* comes next, the bottom tree says *which
word* within it. Every right cluster is a leaf of every top tree. In the default
model `q = 1`, so the left clusters and right clusters coincide, but the
standard also allows `q > 1`.

The file contains exactly what that algorithm needs, and nothing else:

| what | how much |
|---|---|
| a **top tree** per left cluster, the first leaf reserved for the all-zeros case | `k` trees of `k·q + 1` leaves |
| a **bottom tree** per right cluster | `k·q` trees |
| a **rule** per word: the first `len(alphabet)` ids are single characters, every other word is a pair of earlier words | `V − len(alphabet)` rules |
| the **alphabet** the model can code | `len(alphabet)` characters, UTF-8 |
| the parameters `V`, `k`, `q` and the format's name | a header |

A model is a **code, not a statistic**: no counts, no unigram, no corpus
fingerprint.  Everything the decoder needs is either in the file or derivable
from it.

## 2. The schema

A typical model, in YAML form, look like this:

```yaml
format: varnames-model                 # literal, identifies the YAML
alphabet: "abcde"                      # characters, ids 0..4
left_clusters: 2                       # k: one top tree per left cluster
right_clusters_per_left: 2             # q: right clusters per left cluster
rules:                                 # word ids follow the alphabet
  - [1, 2]                             # id 5
  - [3, 4]                             # id 6
memberships: [0, 1, 2, 2, 2, 1, 3]     # V labels: word id -> right cluster
bottom_trees:                          # k*q trees, one per right cluster
  - [0]                                # right cluster 0: word 0 alone
  - [1, 1]                             # right cluster 1: words 1, 5
  - [1, 2, 2]                          # right cluster 2: words 2, 3, 4
  - [0]                                # right cluster 3: word 6 alone
top_trees:                             # one tree per left cluster
  - [4, 1, 2, 3, 4]                    # leaf 0 is STOP; then right clusters 0-3
  - [4, 2, 1, 3, 4]                    # after left cluster 1
```

The file is ASCII with LF newlines, two-space indentation, and no anchors,
aliases, tags or maps other than the top level. Every sequence is a YAML
sequence of integers. Strings must be double quoted with JSON escapes (which
are a subset of YAML escapes) so that everything is ASCII. A writer may add
comments and blank lines; a reader must ignore them.

Sticking to ASCII is a choice, not a constraint; YAML would accept UTF-8. We
make this design decision because this file is the normative statement of
*meaning* (§1), and a non-ASCII character is one that an editor or a filter can
silently change. The binary form, in contrast, encodes characters UTF-8.

The numbering of words, left clusters and right clusters is local to the model.
Note that it differs from the numbering used in the program that builds the
model.

### The keys

* `alphabet` — the characters the model can code. These define word ids
  `0 … len(alphabet) − 1`.  The default model uses the 63 ASCII characters that
  commonly occur in identifiers. The field is included so that a non-default
  model can use different characters.
* `left_clusters` — `k`, the number of left clusters. They are numbered `0 … k`.
  Left cluster `0` is the starting cluster.
* `right_clusters_per_left` — `q`, the number of right clusters per left
  cluster.  Right clusters are numbered `0 … k·q`. The default model has `q = 1`
  such that the left and right clusters correspond. A non-default model can have
  `q > 1`.
* `rules` — the word list as pairs of child ids.  Rule `i` defines word id
  `len(alphabet) + i`. Its children are strictly smaller ids, so the list is
  a topological order of the merge tree.  Rule `i` may not name its own id, and
  its two children must differ.  The list may be empty: `V = len(alphabet)`
  is a model that codes characters only.
* `memberships` — one label per word, `0 ≤ label < k·q`: that word's
  right cluster. The word's left cluster is that label divided by `q`.
* `bottom_trees` — a Huffman tree (see below) for each right cluster. Each tree
  has a leaf for each word in the right cluster (according to `memberships`):
  `V` leaves in total across all the trees. The leaves are listed in word order.
* `top_trees` — a Huffman tree (see below) for each left cluster. Each tree has
  a leaf for `STOP` and for each right cluster: `1 + k·q` leaves per tree. The
  leaves are listed with `STOP` first, then in right cluster order.

`V` is not stored in the YAML file; is is computed as
`len(alphabet) + len(rules)`. It *is* stored in the binary form of the file, as
is `len(alphabet)`.

The Huffman trees are represented by listing the depths of their leaves. Given
the list of depths, codewords are assigned to leaves in decreasing depth order.
When leaves have the same depth, they are assigned codewords in the order they
are listed. The "all zeros" codeword is therefore assigned to the earliest
deepest leaf. Depths are measured from the tree's root; if a tree has only one
leaf then the leaf has depth 0 and is assigned the empty codeword.

### Invariants a reader must check

1. `len(memberships) == V` and (binary only) `V == len(alphabet) + len(rules)`.
2. `len(bottom_trees) == k·q`, every symbol id `0 … V−1` appears in exactly one
   of their leaves, in ascending order, and the total leaf count is `V`.
3. Every tree is **complete**: `Σ 2^{−d} == 1` exactly.
4. In each tree, `max(depth) - min(depth) <= 15`.
5. `len(top_trees) == k`, each with `k·q + 1` leaves: the STOP leaf and one per
   right cluster.
6. `rules[i] = [a, b]` with `a ≠ b` and `a, b < len(alphabet) + i`, and no two
   rules the same pair.
7. A left cluster has at most `q` non-empty right clusters.  Fewer is legal — a
   right cluster with one word cannot be split further — and an empty one is an
   empty depth list and never decodes.  The default model has `q = 1`, so every
   left cluster has exactly one non-empty right cluster.
8. In every top tree, leaf 0 (STOP) is at the **maximum** depth.  It follows
   from giving that leaf zero weight, and it is what makes the padding decode as
   the terminator (§6).  There is no corresponding rule for the bottom trees:
   they carry no terminator.

## 3. The binary form

Measured, not estimated: `scripts/model_size.py` packs the model in this order
and reports the bytes of each section. Illustrative byte sizes describe the
default model, which has `V = 8,191, k = 32, q = 1`.

| section | encoding | bytes |
|---|---|---:|
| magic | `NVM1` | 4 |
| `V`, `k`, `q`, `len(alphabet)` | varints | 5 |
| rules length | a varint: the length of `rules` rounded up to a whole number of bytes | 3 |
| `rules` | 2 × (V − 63) child indices, coded by §4 | 20,926 |
| `alphabet` | `len(alphabet)` characters in UTF-8 | 63 |
| `memberships` | `⌈log₂ kq⌉` = 5 bits each, packed | 5,120 |
| `bottom_trees` | `V` depths at 4 bits each | 4,096 |
| `top_trees` | `k(kq+1)` = 1,056 depths at 4 bits each | 528 |
| **total** | | **30,745** |

There is no version byte separate from `magic`: `NVM1` is the version.  A change
that would break a reader changes the magic to `NVM2`, and a reader must reject
a magic it does not know.  There is **no checksum**: the decoder already checks
so many things that a CRC-32 would add four bytes to catch nothing.

The `rules` table is preceded by its length in bytes. This allows the table to be
skipped without decoding it. The length in bytes must be exactly the size
of the table, which must be zero-padded to a whole number of bytes. 

The `alphabet` is not length-prefixed; its length can only be computed by reading
exactly `len(alphabet)` UTF-8 characters.

`memberships` partitions the words into right clusters.

`bottom_trees` is the concatenation of the lists in the YAML form. The depths
are listed in right cluster order, and within each right cluster they are in
word order. Note that this is different from listing all `V` depths in word
order (wrong).

`top_trees` is similarly the concatenation of the lists in the YAML form. The
depths are listed in left cluster order, and within each left cluster the `STOP`
leaf is first then the others are in right cluster order. Every tree has the
same `1 + k q` labels.

Every depth in `bottom_trees` and `top_trees` is exactly four bits. The field
does not store the raw depth; instead it stores `d − d_min` where `d_min` is the
smallest depth in the tree. for its own tree, not the raw depth. `d_min` is
recovered it from the Kraft equality, per tree. A complete tree has
`Σ 2^(−d) = 1`, so with `d = δ + d_min` the decoder computes
`2^d_min = Σ 2^(−δ)` and takes `d_min = log₂` of it, which must be a whole
number.  A depth table whose δ's give a non-integer `d_min` is corrupt, so the
equality is also a decoder invariant. §3.1 explains why four bits are enough.

A **varint** is a base-128, little-endian integer: each byte carries seven
payload bits and the top bit says whether another byte follows.  So `V = 8,191`
is two bytes (`0xFF 0x3F`), `k = 32` one, and a length below 128 one.  It is the
usual protobuf/LEB128 encoding, chosen because `V` and `k` are the values whose
useful range is widest and whose common values are smallest.

Bits are packed **least-significant first within a byte**: bit *i* of the stream
is bit *i* mod 8 of byte *i* // 8, and bit 0 of the code is the first bit an
encoder writes, so the padding of `ENCODING.md` §2 is the run of zeros *above*
the code.  Integers are little-endian.

The default model file is **30.7 kB**. It is fair to add 2 kB for library code
that is not part of the model file. The YAML form of the same model is
182,472 B — 5.9 times as large. The YAML is the readable form, and the binary is
what the compact form.

### 3.1 Why four bits are enough: the weight bias

A Huffman build puts a rare leaf far deeper than a common one: at
8192/32 the word trees run from depth 0 to depth 23, so a raw depth needs five
bits. But the file format allows only four.

The program that builds the model file compresses the depth range by adding a
**bias** to every leaf weight before building the Huffman tree. This lifts
the smallest probabilities and shortens the tail, but is a completely negligible
addition to the largest probabilities.

No closed form gives the least bias, because the span of a Huffman tree is a
property of the whole distribution.  A leaf's *ideal* depth is `−log₂ p`, so a
bound on `P_max / P_min` does bound the *ideal* span; a Huffman tree is not the
ideal code.  Its longest codeword obeys the **Fibonacci bound**
`L_max ≤ log_phi(T / q_min)`, which is 1.44 times the Shannon depth at the same
weight, and its shortest is floored near `−log₂ q_max`.

**The sufficient condition is too expensive.** The Fibonacci bound does give a
closed-form guarantee: `q_min ≥ phi^-15` forces `L_max ≤ 15`, hence a span of
at most 15.  But a bound on the *longest* codeword is not a bound on the
*span*: at 8192/32 it gives a span of 11 and costs **0.22 bits per identifier**
against the unbiased build.

#### So the bias is found, not computed

The build brackets a working bias by doubling from a small starting guess, then
**bisects** the bracket for the least bias whose built tree spans 15 or less.
That is the least flattening the four-bit field allows. Measurements confirm it
makes no difference to the fit rate:

| point | bias | bottom max | top max | worst span | bits/id | fit ≤64 |
|---|---:|---:|---:|---:|---:|---:|
| 8192/32 | off | 23 | 19 | 18 | 45.217 | 85.0 % |
| 8192/32 | found | 20 | 17 | 15 | 45.218 | 85.0 % |
| 8192/16 | off | 23 | 12 | 18 | 45.676 | 84.5 % |
| 8192/16 | found | 21 | 12 | 15 | 45.677 | 84.5 % |
| 4096/16 | off | 19 | 13 | 14 | 48.982 | 80.5 % |
| 4096/16 | found | 19 | 13 | 14 | 48.982 | 80.5 % |

Zero-weight leaves are excluded from the bias: they are the terminator, they
must stay the deepest leaf, and lifting them to the bias would put them level
with real leaves and could break invariant 7.

Shortening the depths from five bits to four is a small but significant saving.

## 4. The rule table and how it is coded

The rules are the largest object in the file: 20,926 of 30,745 B, two thirds of
the model.  Rule *i* is a pair `(u, v)` of child ids, both below
`N = len(alphabet) + i`, and the decoder knows `N` for each rule.

The file stores `u` and `v` separately, each using a **static geometric
ladder**, base 2, `b = 3`:

    B    = 2^b = 8 intervals
    e_i  = N (2^i − 1) // (2^B − 1)           for i = 0 … B
    x    = the child id, in [0, N)
    i    = the interval with e_i <= x < e_{i+1}, written in b bits
    r    = x − e_i, written in [0, e_{i+1} − e_i) by a variable-width code

The ladder exploits the skewed frequency distribution of the child ids.
A low id is an old, frequent word. The adopted encoding fits the rule table of
the default model into 20,925 B (10.298 bits per child): a significant saving
over a fixed-width field.

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
| the depth offset `d_min` | recovered per tree from the Kraft equality (§3) |
| a version and a checksum | the magic is the version; the invariants are the check (§3) |
| generation parameters (`κ`, sample, seed) | they do not change the code, and they would make rebuilds non-reproducible |

## 6. Worked example

The file in §2 is a complete model: `V = 7`, `k = 2`, `q = 2`, so `k·q = 4`
right clusters and two top trees of 5 leaves.  The characters `a`…`e` are ids
0–4, and words 5 and 6 are `bc` and `de`.  The right clusters are `{a}`,
`{b, bc}`, `{c, d, e}` and `{de}`; left cluster 0 is the first two and left
cluster 1 the last two.

The four bottom trees map right clusters to words. rRight cluster 0 is a single
word and costs nothing; right cluster 1 gives `b`→`0`, `bc`→`1`; right cluster 2
gives `c`→`1`, `d`→`00`, `e`→`01`; right cluster 3 is `de` alone and costs
nothing. Note the direction of the canonical rule: the deeper leaves take the
low codes, which is why `d` and `e` start with `0`.

The top trees hold 5 depths each, leaf 0 being the zero-weight STOP and leaves
1–4 right clusters 0–3.  After left cluster 0 (`[4, 1, 2, 3, 4]`): STOP→`0000`,
right cluster 0→`1`, 1→`01`, 2→`001`, 3→`0001`.  After left cluster 1
(`[4, 2, 1, 3, 4]`): STOP→`0000`, right cluster 0→`01`, 1→`1`, 2→`001`,
3→`0001`.

An identifier is coded as (right cluster | left cluster) then (word | right
cluster), and its first step **starts in left cluster 0**.  For `bc`, which is
ids 1 and 2: `b` is in right cluster 1, so the cluster step is right cluster 1
after left cluster 0, `01`, and the word step inside it is `0`; then `c` is in
right cluster 2 after left cluster 0 (since `b`'s label is 1), `001`, and inside
it `1`; finally the STOP leaf — `c`'s label is 2, so left cluster 1 — `0000`,
which is never written.  Eleven bits of codeword, seven stored: the last four
are zeros and join the padding.

The bottom tree is free for a cluster with only one word. Right clusters 0 and 3
store no depths beyond a single `0`. `python3 scripts/model_size.py --self-test`
runs this model end to end, from the depths to the bytes and back.

## 7. Distribution, and the map

**The default model.**  The standard ships exactly one model file, build over
the ASCII corpus, and fixing `V`, `k` and `q`. The format itself is general, and
does not limit these parameters. A library user may build a non-default model
over any corpus with any `V`, `k` and `q`.

**The counts live beside the file.**  A published model may sit in a directory
that also holds the counts it was built from (word frequencies, the
right-cluster totals, the held-out measurement), so a third party can re-derive
and audit the code without rebuilding the corpus.  Those files are
non-normative: a reader must not require them, and the model file must mean the
same thing without them.

**The grouping lives in the map.**  A tree's depths say nothing about which
words share a bottom tree, so a model with more than one right cluster needs one
label per word (field `memberships`). This cost appears to be unavoidable.
The word list's order is fixed by the `rules` table, and is unrelated to the
words' grouping into clusters. There is no opportunity to renumber the words
to make the clusters contiguous intervals.
