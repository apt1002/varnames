# The name code: a proposed standard

Status: **proposal, version 0.1.**  A language-neutral definition of a
bijection between identifiers and integers, and of the two identifier sets that
follow from it: those whose code fits in 64 bits and those whose code fits in
128.  It reuses the byte layout already specified and measured in
[`MODEL_FORMAT.md`](MODEL_FORMAT.md); this document states what a conforming
implementation must *do*, in terms that do not mention any language, corpus or
build script.

## 1. Scope and domain

An identifier is a finite string over the model's alphabet.  The standard maps
identifiers to non-negative integers:

* **encode** is injective: an identifier has exactly one canonical integer.
* **decode** is total: every non-negative integer decodes to exactly one
  identifier (possibly the empty one).
* The two are inverse on the image of encode.

The empty identifier is a legal input and codes to `0` in zero bits.

A string containing a character outside the alphabet is outside the domain:
encoding it is an error, not a longer code.  A hash fallback for such strings
is *out of scope* (§10).

## 2. The model

A model is a file of five tables.  Their byte layout is normative in
`MODEL_FORMAT.md` §3; their meaning is:

| table | meaning |
|---|---|
| alphabet | the characters, ids `0 … C − 1` |
| rules | `V − C` child-id pairs; rule *i* defines word id `C + i` |
| memberships | one *right cluster* label per symbol id, `0 … k·q − 1` |
| word depths | one depth per symbol: the codeword length in its right cluster's tree |
| cluster depths | `k` trees of `k·q + 1` depths; leaf 0 of each is the terminator |

`V = C + (V − C)` is the vocabulary size, `k` the number of **left clusters**
and `q` the **number of right clusters per left cluster**.  Right clusters
`c·q … c·q + q − 1` belong to left cluster `c`; a symbol's left cluster is
therefore its right cluster divided by `q`.  The one shipped model has `V = 8,191`,
`k = 32`, `q = 1`, 63 characters and 8,128 rules.

The rules are a pair-merge dictionary: word id `C + i` is the concatenation of
its two children, which are strictly smaller ids.  Decoding a word therefore
means replaying the rule list once at load time; there is no other spelling
information in the file.

Each tree is a complete prefix code given by its depths alone.  No codeword is
stored: §4 derives them, and a decoder that does not reproduce the derivation
exactly will not interoperate.

## 3. The two stages

An identifier is coded as a sequence of steps that alternate between the
cluster level and the word level:

1. Start in **left cluster 0**.
2. Tokenise the identifier into symbols (§5).
3. For each symbol in turn, write
   (a) its **right cluster** in the current left cluster's tree, at leaf
       position `1 + cluster` (leaf 0 is the terminator), then
   (b) the **symbol itself** in that right cluster's tree, at its position in
       the cluster's ascending-id word list;
   then the current left cluster becomes the symbol's left cluster.
4. Write the **terminator**, leaf 0 of the final left cluster's tree.

The terminator is never stored.  Its codeword is all zeros, and so is the
padding above the integer (§6), which is what makes the end of an identifier
free.

## 4. Codewords

Given a tree's depths `d₀ … dₙ₋₁` in stored order, the codewords are
assigned canonically, filling the space from the deepest leaves down:

```
max  := the largest depth
next := 0
for length from max down to 0:
    block := 2^(max − length)
    begin := ceil(next / block)
    count := the number of leaves whose depth is `length`
    for the k-th such leaf p, in ascending p:
        codeword[p] := begin + k, in `length` bits
    next := (begin + count) * block
```

The first leaf at the maximum depth therefore receives the all-zeros codeword.
Two consequences are load-bearing and must not be "fixed" by a reimplementation:

* the terminator leaf (position 0 of every cluster tree) is the deepest leaf,
  because its weight is zero, so its codeword is the all-zeros one;
* word trees have no terminator leaf, and their deepest leaf is an ordinary
  word.

Codewords travel most-significant bit first.  Bits are packed into bytes
least-significant bit first: the first bit of the stream is bit 0 of byte 0
(§3 of `MODEL_FORMAT.md`).  These two orders are opposite on purpose and are the
most common source of incompatibility.

## 5. Tokenisation

The rules are applied in ascending rank order, merging every adjacent pair
whose ids match a rule, repeatedly, until no rule applies:

```
tokens := the character ids of the identifier, in order
for rank from 0 upwards:
    scan left to right, merging every adjacent pair that is rule `rank`
    (a merge of rank r never creates a pair of rank below r, so one sweep
    per rank suffices; the result equals always merging the lowest rank first)
```

The result is the symbol sequence of §3.  Ranks are nested — a rule's children
were created by lower ranks — and that is what makes the single sweep correct.

## 6. The integer

The code is a finite bit string `b₀ … b_{L−1}` in stream order.  The canonical
integer is

```
value = Σ b_i · 2^i        (b₀ is the least significant bit)
```

with trailing zeros removed: a code is stored with no trailing zero bit, and
the integer's bit length is `L`.  The decoder reads zeros past the end of the
integer, which is what lets the all-zeros terminator finish the identifier;
equivalently, in a fixed-width word the terminator is "the code continues as
zeros".  In 64- and 128-bit words the value is little-endian.

Consequently every bit string is a code of exactly one identifier, and every
integer is the code of exactly one identifier.  There are no reserved values.

## 7. The two sets

The sets are read off the encoder rather than tabulated:

* the **64-bit set** is the identifiers whose canonical code has `L ≤ 64`;
* the **128-bit set** is the identifiers whose canonical code has `L ≤ 128`.

Membership is a property of the identifier and the model, not of a second table.
Codes longer than 128 bits exist — the corpus contains them — and they are
outside both sets, not errors: the code is a bit string of any length, and the
two sets are the subset that fits a machine word.  The measured fit rates are in
[`BUDGET64_STUDY.md`](BUDGET64_STUDY.md).

## 8. Conformance

A conforming **encoder** must:

* tokenise and code exactly as §§3–6 say, and emit the canonical integer;
* refuse characters outside the alphabet rather than extend the alphabet;
* leave every unused high bit of a 64/128-bit word zero.

A conforming **decoder** must:

* accept every non-negative integer, including 0;
* read zeros past the top of the word, and stop at the terminator;
* ignore unused high bits in a fixed-width word, never test them;
* reproduce the canonical assignment of §4 exactly, or it will mis-decode.

A conforming **model file** must satisfy the invariants of `MODEL_FORMAT.md`
§3: the rules topological and run-free, one membership and one depth per symbol,
each cluster tree complete with leaf 0 deepest, each word tree within the Kraft
bound, `V = C + len(rules)`.  A reader that finds a violation must reject the
file rather than guess.

No floating point is needed anywhere in encoding or decoding.  A decoder that
computes probabilities is computing the wrong object: it needs only the depths
and the rule list.

## 9. Publishing the tables

* The standard publishes **one model file**, not a distribution of them.  A new
  or retrained model is a new file with a new digest; files are never edited in
  place.
* The file's identity is its **SHA-256**.  The shipped model is
  `976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79`
  (30,745 bytes).  Implementations embed or fetch the file and verify the
  digest before use.
* The human-readable form of the same model (`model.yaml`, the schema of
  `MODEL_FORMAT.md` §2) is published alongside it, so the binary can be checked
  by converting it back.  The binary is normative for bytes; the YAML is
  normative for meaning.
* The published tables are `CC0-1.0`, the code and specification
  `MIT OR Apache-2.0`.

A deployment may use a different model — another `V`, another `k`, another
corpus.  Such a file is *not* the standard model, and two programs that use
different files will not agree; the digest is how they find out.

## 10. Out of scope

* A hash fallback for identifiers outside the alphabet or outside the 128-bit
  set.  The sets are defined by exclusion; a fallback belongs to a transport,
  not to this code.
* Case normalisation, Unicode identifiers, and any rule about what an identifier
  is: the code's domain is strings over a stated alphabet.
* Table-building.  How a word list, an assignment and a set of depths are
  produced from a corpus is engineering, not interoperability.
* Compression of the model file itself.  It is 30,745 bytes, published once,
  and every scheme to shrink it has so far cost more in decoder complexity than
  it saved.

## 11. Test vectors

`rust/tests/golden.txt` holds 250 identifiers with their exact integer and bit
length.  Both implementations in this repository read that file, so it pins
them to each other; a third implementation can do the same.  The first lines:

| identifier | integer | bits |
|---|---:|---:|
| *(empty)* | 0 | 0 |
| `a` | 108 | 7 |
| `A` | 772 | 10 |
| `_` | 208 | 8 |
| `foo` | 7,043 | 13 |
| `getUserName` | 124,101,637 | 27 |
| `HTTPServer` | 43,666,456 | 26 |

A conforming implementation reproduces all 250, and decodes each integer back
to its identifier.
