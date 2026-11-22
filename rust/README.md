# varnames (Rust)

The engineering implementation of the name code: an identifier goes in, an
integer comes out, and the integer comes back to the same identifier bit for
bit.  The standard tables are compiled into the library, so a program needs no
data files at run time.

```rust
use varnames::standard::standard;

let codec = standard()?;
let code = codec.encode("getUserName")?;   // 124101637, 27 bits
assert_eq!(codec.decode(code)?, "getUserName");
```

`encode` returns the code as a `u128`; `encode_bits` returns the exact bit
string when the code does not fit in 128 bits.

## What is in the box

| module | contents |
|---|---|
| `Bits` | a bit string of exact length, packed least-significant-bit first |
| `Codec` | the tokeniser, the encoding loop, decoding |
| `case` | `classify`, `to_camel`, `from_camel` over the 266 cased pairs (`STANDARD.md` §11) |
| `model` | the `NVM1` reader: strict invariant checks, the typed index tables, the derived trees |
| `sha256` | forty lines of SHA-256, so identifying the tables needs no dependency |
| `standard` | the embedded standard tables and their SHA-256 |

`bitio`, `codec`, `huffman` and `ladder` are private: `Bits` and `Codec` are
reexported at the crate root, and the bit reader, the trees and the ladder are
crate-internal.

The crate has no dependencies and no build script.

## Every index has a type

A model is a set of tables indexed by small integers of several different
kinds, so `model` gives each kind its own one-field struct: `Word`, `Rule`,
`Char`, `Left`, `Right`, `LeftLeaf` and `RightLeaf`.  `Model`'s accessors take
one kind and return the next — `model.right(word)`, `model.left_of(right)`,
`model.top_tree(left)`, `model.position(word)` — so a right cluster cannot be
passed where a left cluster is meant, and no caller ever indexes a table
directly.  The tables themselves are private; the sizes are methods
(`num_words()`, `num_lefts()`, …), each docstring naming its letter in
`STANDARD.md`.

## Case conversion

The model is trained on CamelCase, so `FOO_BAR` and `foo_bar` code less well
than `fooBar`.  [`case`] rewrites the other two conventions and back:

```rust
use varnames::case::{classify, from_camel, to_camel};

assert_eq!(to_camel("FOO_BAR"), "fooBar");
assert_eq!(from_camel("fooBar", classify("FOO_BAR")), "FOO_BAR");
```

It is exact: every cased character maps to one character, so the length changes
only by the separators it swallows, and `from_camel(&to_camel(x), classify(&x))
== x`.  The cased characters are the ASCII letters and the 1:1-paired letters
of `U+00C0–U+017F` and `U+0400–U+052F` (`data/case-pairs.txt`, 266 pairs,
compiled in); everything else, Greek and every script without case included, is
inert and passed through.

## Using your own tables

```rust
use varnames::{Codec, Model};

let bytes = std::fs::read("tables/model.nvm1")?;
let codec = Codec::new(Model::from_bytes(&bytes)?);
```

The model file is the same one the Python package reads;
`standard/MODEL_FORMAT.md` is the specification.

## Testing

```sh
cargo test
```

`standard/golden.txt` holds 250 identifiers with their codes, produced by the
Python reference implementation.  Both implementations read that file, so the
two cannot drift apart silently.  The crate also checks the digest of its
embedded tables against `standard::STANDARD_SHA256`.

## Licence

MIT OR Apache-2.0.
