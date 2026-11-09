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

The two stages are there because a word transition is coded in two parts: the
top tree says *which group of words* comes next, the bottom tree says *which
word* within it.  Every right cluster is a leaf of every top tree, so the top
stage may pair right clusters that belong to different left clusters; a left
cluster owns `q` of them, which is why the next left cluster is the right
cluster divided by `q`.  `q` is the number of right clusters per left cluster.
It is 1 in the standard — one right cluster to a left cluster, so the two
stages read the same label — but the format carries it, and
[`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md) measures what `q > 1` buys.

The file contains exactly what that algorithm needs, and nothing else:

| what | how much |
|---|---|
| a **top tree** per left cluster, the first leaf reserved for the all-zeros case | `k` trees of `k·q + 1` leaves |
| a **bottom tree** per right cluster | `k·q` trees |
| a **rule** per word: the first `len(alphabet)` ids are single characters, every other word is a pair of earlier words | `V − len(alphabet)` rules |
| the **alphabet** the model can code | `len(alphabet)` characters, UTF-8 |
| the parameters `V`, `k`, `q` and the format's name | a header |

The trees are stored as the depth of each leaf in label order, and a membership
table says which words belong to which bottom tree.  That is all a decoder
needs: the codewords are canonical from the depths, so no code table is
stored.  The storage is §3, and its cost in bytes is
[`MODEL_BUDGET.md`](MODEL_BUDGET.md).

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

`alphabet` is a **double-quoted scalar written with JSON escapes**: a JSON
string is a valid YAML double-quoted scalar, so `json.dumps` escapes quotes,
backslashes and control characters correctly without a YAML writer in the
loop.  A non-ASCII character is therefore written `\uXXXX` and the file stays
ASCII; one that is not is refused, not guessed at.  That is a choice, not a
constraint — YAML would accept literal UTF-8 here — made because this file is
the normative statement of *meaning* (§1), and a literal character in a
checked-in file is one that an editor or a filter that renormalises text can
silently change; `\u00e9` cannot be renormalised.  The binary form is where
UTF-8 is spelled out.

The numbering is the **file's**, and only the file's is normative.  A build
working on the corpus tokeniser's alphabet will number the characters `0 … 62`,
the stop `63` and the words above it; dropping the stop shifts the words down
one.  That shift is the whole of `to_file_id` in `scripts/model_size.py`.

### The keys

* `alphabet` — the characters the model can code, as ids
  `0 … len(alphabet) − 1`.  The shipped model uses the 63 ASCII characters that
  occur in identifiers; the field is carried explicitly so a reader can check
  the file against a corpus instead of assuming that set.  A toy model may use
  fewer, and a model for a corpus that is not ASCII may use any characters:
  the binary stores the list as UTF-8 (§3).
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
  its two children must differ (no run words, `DICTIONARY_RULES.md`).  The list
  may be empty: `V = len(alphabet)` is a model that codes characters only.
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
| `rules` | 2 × (V − 63) child indices, coded by §4 | 20,926 |
| `alphabet` | `len(alphabet)` characters in UTF-8, ids 0–62; one byte each here | 63 |
| `memberships` | `⌈log₂ kq⌉` = 5 bits each, packed | 5,120 |
| `bottom_trees` | `V` depths at 4 bits each, right cluster by right cluster, ascending symbol id inside | 4,096 |
| `top_trees` | `k(k+1)` = 1,056 depths at 4 bits each | 528 |
| **total** | | **30,745** |

**The alphabet is UTF-8**, and the header counts characters, not bytes.  The
section is not length-prefixed in bytes because UTF-8 delimits itself: the
decoder reads exactly `len(alphabet)` characters and the section ends where the
last one ends.  Every character of the shipped alphabet is ASCII, so the count
and the byte length agree and the 63 bytes are the same bytes a raw-ASCII
alphabet would have written.  A non-ASCII character costs its UTF-8 length —
two bytes for accented Latin, Greek and Cyrillic, three for Han, kana and
Hangul, four for emoji — and that is the whole cost of a wider alphabet here;
the symbols themselves cost their table entries as usual.  Because a reader
that predates this rejects a non-ASCII alphabet outright, widening it needed no
new magic: every file that existed before is unchanged, and a file that uses
the widening is refused cleanly by an older reader rather than misread.

There is **no version byte**: `NVM1` is the version.  A change that would break a
reader changes the magic to `NVM2`, and a reader must reject a magic it does not
know.  There is **no checksum**: the decoder already checks the magic, every child id
against the rule's own limit, the completeness of every tree (the Kraft sum), the
leaf counts against `memberships`, and that the file ends where the tables say it
does.  A CRC-32 would add four bytes to catch nothing those checks do not.

**Every depth is exactly four bits**, and there is **no width byte**.  The field
stores `d − d_min` for its own tree, not the raw depth: `d_min` is not stored at
all.  The decoder recovers it from the Kraft equality, per tree.  A complete
tree has `Σ 2^(−d) = 1`, so with `d = δ + d_min` it computes
`2^d_min = Σ 2^(−δ)` and takes `d_min = log₂` of it, which must be a whole
number.  A tree with one leaf carries no depth at all — its symbol is coded in
zero bits, and the decoder knows it is alone from `memberships`.  A depth table
whose δ's give no integer offset is corrupt, so the equality is also a decoder
invariant.  §3.1 is why four bits are enough at every point of the grid.

A **varint** is a base-128, little-endian integer: each byte carries seven
payload bits and the top bit says whether another byte follows.  So `V = 8,191`
is two bytes (`0xFF 0x3F`), `k = 32` one, and a length below 128 one.  It is the
usual protobuf/LEB128 encoding, chosen because `V` and `k` are the values whose
useful range is widest and whose common values are smallest.

Bits are packed **least-significant first within a byte**: bit *i* of the stream
is bit *i* mod 8 of byte *i* // 8, and bit 0 of the code is the first bit an
encoder writes, so the padding of `ENCODING.md` §2 is the run of zeros *above*
the code.  Integers are little-endian.

The rest of the file is 9,819 B, so the model is **30.7 kB** — against the
32.8 kB of `MODEL_BUDGET.md` §5.1, which adds 2 kB of library code that is not
part of the model.  The YAML of §2 is 182,472 B at the same point — 5.9 times
as large: it is the portable form, and the binary is what the budget measures.

### 3.1 Why four bits are enough: the weight bias

Unbiased, a Huffman build puts a rare leaf far deeper than a common one: at
8192/32 the word trees run from 0 to 23, so a raw depth needs five bits.  The
range is compressed by adding a **bias** to every leaf weight before the merge,
which lifts the smallest probabilities and shortens the tail.  The design
proposed

    bias  =  max(0, (P_max − 32768 · P_min) / 32767)

on the hypothesis that a weight ratio of at most `2^15` bounds the depth span at
15.  It does not, and why is the difference between an *ideal* code and a
*Huffman* code.

**The formula bounds the wrong quantity.** Ideal (Shannon) depth is `−log₂ p`, so
a ratio `P_max / P_min ≤ 2^15` does bound the *ideal* gap at 15 levels.  A
Huffman tree is not the ideal code: its longest codeword obeys the **Fibonacci
bound** `L_max ≤ log_phi(T / q_min)`, which is 1.44 times the Shannon depth at
the same weight, and its shortest is floored near `−log₂ q_max`.  A
distribution can satisfy the formula and still span more than 15 — and the grid
does: at 8192/32 the stated bias leaves the top trees spanning **16** levels,
while it has already flattened the bottom trees from 18 to **12**, three more
than the field needs.  One formula, applied tree by tree, over-corrects one
stage and under-corrects the other, because the two stages have different weight
ratios, and what it costs in bits is what the search over the grid prices.

**The formula is tied to 15.** It is an inequality about `2^15`, so it says
nothing about a span of `s` for any other `s`, and cannot be scaled to a
narrower field.

#### A worked example that does *not* tickle it

The design's own `[1, 2, 4, 8, 16]`, as probabilities over 31.  Its Huffman
depths are `4, 4, 3, 2, 1`: a span of 3, which a 4-bit field holds with no bias
at all, and the formula agrees (it asks for zero).  So this example does not
exhibit the bug at 15 bits.  It does exhibit it at a **one-bit** field: the same
weights need a span of 1, the formula still asks for zero, and the least bias
that fits is `4.5` — 15 % of the total mass — costing 0.42 bits per leaf.

#### A worked example that does

Twenty weights in the Fibonacci progression `1, 1, 2, 3, 5, …, 6765` (total
17,710).  The deepest weight is `q_min = 2^-14.11`, so
`log_phi(1/q_min) = 20.3`, and the unbiased tree spans **18** levels.  The ratio
`P_max / P_min = 6765` is far below `2^15`, so the formula asks for zero bias —
and the tree still spans 18, needing five bits.  The least bias that brings it
to 15 is `0.067`, a lift of 0.0004 %, and it does so at no measurable bit cost.
Nothing in the distribution's maximum-to-minimum ratio predicts that number; the
shape of the whole tail does.  (`scripts/depth_bias.py` prints all of these
trees.)

#### The sufficient condition, and why it is too expensive

The Fibonacci bound does give a closed-form guarantee: `q_min ≥ phi^-15` forces
`L_max ≤ 15`, hence a span of at most 15.  On the Fibonacci weights it works
(span 7) but over-flattens badly, and on the real trees it is expensive: at
8192/32 it gives a span of 11 and costs **0.22 bits per identifier** against
the unbiased build.  A bound on the *longest* codeword is not a bound on the
*span*, and the difference is paid in bits.

#### So the bias is found, not computed

The Huffman shape is a property of the whole distribution, and no single ratio
describes it.  The build therefore brackets a working bias by doubling from the
design's formula, then **bisects** the bracket for the least bias whose built
tree spans 15 or less, to `2^-16` relative.  That is the least flattening the
four-bit field allows, and measured it is what keeps the field's fit cost at
nothing:

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

The field is four bits at every point of the measured grid.  Shortening the
depths from five bits to four takes the operating-point file from 31,901 B to
30,745 B — **1,156 B, 3.6 %** — and the fit rate does not move at any point.

## 4. The rule table and how it is coded

The rules are the largest object in the file: 20,926 of 30,745 B, two thirds of
the model.  Rule *i* is a pair `(u, v)` of child ids, both below
`N = len(alphabet) + i`, and the decoder knows `N` for each rule.  The file
stores each child with a **static geometric ladder**, base 2, `b = 3`:

    B    = 2^b = 8 intervals
    e_i  = N (2^i − 1) // (2^B − 1)           for i = 0 … B
    x    = the child id, in [0, N)
    i    = the interval with e_i <= x < e_{i+1}, written in b bits
    r    = x − e_i, written in [0, e_{i+1} − e_i) by the variable-width code

Nothing is stored for the code: the decoder derives the eight edges from `N`
and `b` with integer arithmetic, and at base 2 the index is exact in shifts.
The two children are coded **separately** — Pair — rather than combined into one
number.  That is the finding of the grid: the ladder exploits the frequency rank
of each child, because a low id is an old, frequent word, so a rule
`(common, rare)` gets a short code for the common child.  Any pairing sends both
children through one number, and the common child loses its short code.  The
adopted encoding is 20,925 B for the shipped list (10.298 bits per child); the
fixed field costs 24,492 B, the variable field 22,948 B, and the best
pair-combining scheme 21,162 B (Triangle) or 21,458 B (Square).

The grid that chose it — three pairings crossed with eight number codes, `b` from
2 to 5, three bases, and the narrow and wide readings of the index formula — is
[`RULE_ENCODING.md`](RULE_ENCODING.md).  Two of its conclusions are worth
repeating here because they are about *this* code.  First, the ladder is
**static**: the only thing computed at load is eight integer divisions.  Second,
it is within 5 % of the pooled entropy of the child-index stream (9.80
bits/child, 19,916 B), and a code that reached that limit would have to store
the empirical distribution, which costs more than the kilobyte it saves.  The
arithmetic coder the format used to carry measured 21,109 B; the ladder is 184 B
better and needs no arithmetic coder at all.

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
