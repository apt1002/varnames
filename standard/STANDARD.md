# The name code: a proposed standard

Status: **proposal, version 0.1.**  A language-neutral definition of a
bijection between identifiers and integers, and of the two identifier sets that
follow from it: those whose code fits in 64 bits and those whose code fits in
128.  It uses the byte layout specified and measured in
[`MODEL_FORMAT.md`](MODEL_FORMAT.md). This document states what a conforming
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

### The files of this standard

The standard is the directory `standard/` of this repository and nothing else:
two documents and four published files.  No other file is needed to build a
conforming implementation, and no other file may override one of these.

| file | what it is | status |
|---|---|---|
| `STANDARD.md` | this document | normative |
| `MODEL_FORMAT.md` | the byte layout, and the readable schema | §§2–4 by reference |
| `model.nvm1` | the model, `V = 8191`, `k = 32`, `q = 1`, 30,745 B | normative for the bytes (§9) |
| `model.yaml` | the same model, readable | normative for the meaning (§9) |
| `case-pairs.txt` | the 266 cased characters of §11 | normative for the mapping |
| `golden.txt` | 250 conformance vectors: name, code, bits | informative (§12) |

This repository contains two implementations of the standard. Both ship
byte-for-byte copies of the `model.nvm1` and of `case-pairs.txt`. They check the
model's digest before using it, and test that their copy of the pairs is the
published file (§9). Their unit tests test conformance with `golden.txt`. We
recommend that other implementations of the standard do the same.

## 2. The model

A model is a file of five tables:

- an alphabet of characters, of length `C`,
- a list of tokenisation rules, of length `V - C`,
- a partition of the words (characters and rules) into clusters,
- a Huffman tree that encodes a word given its cluster, and
- a Huffman tree that encodes a cluster given its predecessor.

Two equivalent standard representations are defined: a readable `.yaml` textual
format, and a compact `.nvm1` binary format. See `MODEL_FORMAT.md` for an
explanation of how they are stored. In particular, §2 defines the `.yaml` form,
and §3 defines the `.nvm1` form. These sections are normative.

## 3. The two stages

An identifier is coded as a sequence of steps that alternate between the
cluster level and the word level:

1. Tokenise the identifier into words (§5).
2. Start in **left cluster 0**.
3. For each word in turn, write
   (a) its **right cluster** in the current left cluster's tree, at leaf
       position `1 + cluster` (leaf 0 is the terminator), then
   (b) the **word itself** in that right cluster's tree, at its position in
       the cluster's ascending-id word list;
   then the word's left cluster becomes the new current left cluster.
4. Write the **terminator**, leaf 0 of the final left cluster's tree.

The terminator's codeword is all zeros. Some additional trailing bits may be
zero by chance.

## 4. Codewords

Each Huffman tree is represented as a list of the depths of its leaves, i.e.
the lengths of its codewords. Given a tree's depths `d₀ … dₙ₋₁` in stored order,
the codewords are assigned canonically, filling the space from the deepest
leaves down:

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
  because its weight is zero, so its codeword is all zeros;
* word trees have no terminator leaf, and their deepest leaf is an ordinary
  word.

The above pseudo-code generates big-endian codewords, which must therefore be
reversed to form a little-endian integer (see §6).

## 5. Tokenisation

§3 says "Tokenise the identifier into words"; this section defines how to do
that.

The model's tokenisation rules are applied to the identifier in ascending rank
order (the order they appear in the model file). Each rule is a
search-and-replace operation that merges every occurrence of a particular 2-gram
(two adjacent words) into a 1-gram (a single word).

The replacement order within one rank does not matter: two occurrences of a
2-gram cannot overlap, because the rule's two children differ.

## 6. The integer

The code is a finite bit string `b₀ … b_{L−1}` in stream order.  The canonical
integer is

```
value = Σ b_i · 2^i        (b₀ is the least significant bit)
```

I.e. the encoding is little-endian. Trailing zeros of the bit string, including
the all-zeros terminator codeword, become leading zeros of the integer. Leading
zeros are implicitly endless, and are therefore stored for free. The decoder
reads as many zeros as it needs to finish the identifier; when reading a 64-bit
or 128-bit integer, it can continue beyond the first 64 or 128 bits.

Consequently every bit string is a code of exactly one identifier, and every
integer is the code of exactly one identifier.  There are no reserved values.

## 7. The two sets

A contribution of this standard is two useful sets of identifiers. The sets are
read off the encoder rather than tabulated:

* The **64-bit set** is the identifiers whose canonical integer has no ones
beyond bit 63. This includes 85% of unique identifiers in a validation corpus.
* The **128-bit set** is the identifiers whose canonical integer has no ones
beyond bit 127. This includes 99% of unique identifiers in the corpus.

Measuring the sets as a fraction of *unique* identifiers undersells them,
because a typical word in the set is used more frequently than a typical word
outside it. As a fraction of occurrences, the 64-bit set covers about 92% of
identifiers. Words excluded by the sets tend to be long and odd in some way,
e.g. they contain an unusual number of underscores, or use unconventional
capitalisation. There is often an easy fix.

Membership is a property of the identifier and the model, not of a second
table. Codes longer than 128 bits exist, and they are outside both sets. The
code generalises to bit strings of any length, and the two sets are merely the
subset that fits a machine word.

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
§3: the rules topological and run-free, one membership and one depth per word,
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
* In this repository the two are `standard/model.nvm1` and
  `standard/model.yaml`; the same bytes are compiled into both implementations
  (`python/varnames/data/model.nvm1`, `rust/data/model.nvm1`), and each checks
  the digest above before it uses them.
* The **case pairs** of §11 are published as `standard/case-pairs.txt`: 266
  pairs, `upper lower`, one per line, 1,937 bytes, SHA-256
  `fe4f29facc43e72b8bd263a31712013d58b3a0b29acce595b05a5cf0134f972c`.  Like
  the model it is copied into `python/varnames/data/` and `rust/data/`, and a
  test in each implementation asserts that its copy is the published file.
* The **conformance vectors** of §12 are published as `standard/golden.txt`:
  250 identifiers with their exact integer and bit length, 8,935 bytes,
  SHA-256 `bf2481b8acf2c941b8413ca37b591e83e7ba9820f187d44d62b385faf178ccb9`.
  They are informative: a vector that disagrees with a conforming model means
  the model, not the vector.
* The published tables are `CC0-1.0`, the code and specification
  `MIT OR Apache-2.0`.

A deployment may use a different model — another `V`, another `k`, another
corpus.  Such a file is *not* the standard model, and two programs that use
different files will not agree; the digest is how they find out.

## 10. Out of scope

* A hash fallback for identifiers outside the alphabet or outside the 128-bit
  set.  The sets are defined by exclusion; a fallback belongs to a transport,
  not to this code.
* Case normalisation of what is encoded.  The code's domain is strings over a
  stated alphabet, and it normalises nothing: an identifier written in another
  convention is coded, just less well.  §11 specifies an optional conversion
  for callers who want the corpus's convention; encoding and decoding never
  depend on it.
* Unicode identifiers, and any rule about what an identifier *is*.  Identity,
  normalisation (NFC, NFD) and confusables belong to the host language, and
  hosts decide them differently: Python and Rust merge the two spellings of
  `café`, GCC and Perl keep them apart, Java's specification says they are
  different identifiers and C#'s requires source identifiers to be NFC already
  ([`UNICODE.md`](../docs/UNICODE.md) §11).  There is no single answer to
  adopt, so a caller that cares normalises before encoding.
* Table-building.  How a word list, an assignment and a set of depths are
  produced from a corpus is engineering, not interoperability.
* Compression of the model file itself.  It is 30,745 bytes, published once,
  and every scheme to shrink it has so far cost more in decoder complexity than
  it saved.

## 11. Case conversion

An implementation **may** convert between the three conventions `foo_bar`,
`FOO_BAR` and `fooBar`; one that does not offer the conversion conforms. Both
the implementations in this repository do provide case convention conversions.

The standard model is trained on CamelCase identifiers. Converting an identifier
to camel case therefore allows the model to encode it better, but nothing in the
encoding or decoding process depends on it. To convert an identifier back to its
original case convention, you must record the convention out-of-band, as it is
not part of the encoded data. `from_camel(to_camel(x), class(x)) = x` for every
identifier.

### Converting single characters

For the purpose of converting between case conventions, it is necessary to
define how single characters are converted to upper- and lower-case forms.
Although the standard model has an ASCII-only alphabet, non-standard models are
allowed, so the definition covers non-ASCII characters too. For interoperability
between implementations, we encourage you to use the definition given here. Note
that the unicode character properties table shipped with your programming
language might not match the definition given here, which is fixed so that a
Unicode upgrade cannot change what it does.

A character is said to be **cased** when its upper-case and lower-case forms are
different, and are inverses of each other. Every other character is **inert**,
i.e. it is unchanged by case conversions. The cased set is defined to be the
letters in `U+0041–U+005A`, `U+0061–U+007A`, `U+00C0–U+017F` and
`U+0400–U+052F`.  In those ranges exactly six letters are inert: `ß`, `İ`, `ı`,
`ŉ` and `ſ` have no 1:1 pair, and `ĸ` has no upper case at all.  The 266 cased
pairs are published in `standard/case-pairs.txt` (§9), which is normative. They
cover the majority of characters actually used in identifiers.

### Detecting the case convention

A character is **upper** when it differs from its own lower-case form, and
**lower** when it differs from its upper-case form. Inert characters are neither
upper nor lower. An identifier is `lower` if it has lower but not upper
characters, `upper` if it has upper but not lower characters, and `camel` if it
has both or neither. A name with no cased characters has nothing to convert, so
it is already in the normal form.

### Converting to camel case

To convert a `lower` or `upper` identifier to camel case:

* every cased character becomes lower case, **except** one immediately
  preceded by an underscore, which becomes upper case. The underscore is
  swallowed: `a` stays `a`, `_a` becomes `A`, and `A_B` becomes `aB`.
* an underscore that precedes an uncased character, such as a digit or another
  underscore, is not swallowed: `__3a` is therefore unchanged.

### Other alphabets

Two design choices are worth stating, because they are what stops the set of
cased characters from growing.

**Scripts without case are inert, and that is not a gap.**  The transform's only
channel for a word boundary is a capital letter; Han, kana, Hangul, Arabic,
Hebrew, Devanagari and Thai have none, so an identifier written in them is
unchanged and keeps its underscores.  There is no table that would fix this
without inventing a convention that the writing system does not have.

**Greek is the nearest miss and stays inert.**  91 of its 236 cased letters
(`ΐ`, `ΰ`, the iota-subscript forms) map to two characters, and the letter it
cannot do without, `Σ`, lower-cases to `σ` whatever follows it — so `ΟΔΟΣ` and
`οδος` still do not meet, and the conversion would buy 91 exceptions to join
nothing.  Any further script is a further version of this standard, not a
further line in it.

## 12. Test vectors

`golden.txt` (§9) holds 250 identifiers with their exact integer and bit
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

The 266 case pairs of §11 are pinned the same way, by their own round trip:
each implementation converts and inverts every pair in both classes
(`TestCaseConversion` in the Python tests, `case::tests` in Rust).
