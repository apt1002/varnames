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
| `sha256` | forty lines of SHA-256, so identifying the tables needs no dependency |

The crate has no dependencies and no build script.

## Using your own tables

```rust
use varnames::{Codec, Model};

let bytes = std::fs::read("tables/model.nvm1")?;
let codec = Codec::new(Model::from_bytes(&bytes)?);
```

The model file is the same one the Python package reads; `docs/MODEL_FORMAT.md`
is the specification.

## Testing

```sh
cargo test
```

`tests/golden.txt` holds 250 identifiers with their codes, produced by the
Python reference implementation.  Both implementations read that file, so the
two cannot drift apart silently.  The crate also checks the digest of its
embedded tables against `standard::STANDARD_SHA256`.

## Licence

MIT OR Apache-2.0.
