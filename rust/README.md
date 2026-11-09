# varnames (Rust)

The engineering implementation of the name code: an identifier goes in, an
integer comes out, and the integer comes back to the same identifier bit for
bit.  The standard tables are compiled into the library, so a program needs no
data files at run time.

```rust
use varnames::standard;

let codec = standard()?;
let code = codec.encode("getUserName")?;   // Code { value: 124101637, bits: 27 }
assert_eq!(codec.decode(code.value)?, "getUserName");
```

## What is in the box

| module | contents |
|---|---|
| `bitio` | bits packed least-significant-bit first, and a reader that reads zeros past the end |
| `ladder` | the static rule-pair ladder and the variable-width integer (`MODEL_FORMAT.md` §4) |
| `model` | the `NVM1` reader: strict invariant checks, canonical codewords, derived trees |
| `codec` | the tokeniser, the encoding loop, decoding |
| `standard` | the embedded standard tables and their SHA-256 |
| `case` | `classify`, `to_camel`, `from_camel` over the 266 cased pairs (`STANDARD.md` §11) |
| `sha256` | forty lines of SHA-256, so identifying the tables needs no dependency |

The crate has no dependencies and no build script.

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
