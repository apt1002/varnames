# varnames (Python)

The reference implementation of the name code: an identifier goes in, an
integer comes out, and the integer comes back to the same identifier.

```python
import varnames

codec = varnames.standard()
value, bits = codec.encode("getUserName")    # 124101637, 27
assert codec.decode(value) == "getUserName"
```

The standard tables are shipped with the package
(`varnames/data/model.nvm1`, 30,745 bytes), and their SHA-256 is checked the
first time they are loaded.

## The API

| call | meaning |
|---|---|
| `varnames.standard()` | the standard `StandardCodec`, loaded once and cached |
| `codec.encode(name)` | `(value, bits)`; bit *i* of `value` is the *i*-th bit of the code |
| `codec.encode_bits(name)` | the code as a list of bits, first bit first, trailing zeros cut |
| `codec.decode(value)` | the identifier; bits past the top read as zeros |
| `codec.decode(value, bits)` | the same, with a sanity bound on the integer's width |
| `codec.tokenise(name)` | the model's words, before coding |
| `codec.model` | the loaded `Model` |
| `varnames.Codec(varnames.Model.from_path(path))` | any `NVM1` model file instead of the standard one |
| `varnames.case.classify(name)` | `'lower'`, `'upper'` or `'camel'` |
| `varnames.case.to_camel(name)` | rewrite the two snake conventions in CamelCase |
| `varnames.case.from_camel(name, cls)` | the inverse, given the class |

`encode` returns an integer of any size; a 64-bit or 128-bit set is simply the
identifiers whose `bits` fit.  Round trips are exact: `decode(encode(n))` is
`n`, and the terminator is never stored.

`decode` is total: every non-negative integer decodes to an identifier, because
bits beyond the terminator read as zeros.  `decode(value, bits)` takes an
optional sanity bound and rejects a value with a set bit above `bits`, which is
what a fixed-width field needs.

The tables are private.  `codec.model` reads them through accessors named as in
the Rust crate — `num_words()`, `char_at(i)`, `right(word)`, `left(word)`,
`top_tree(left)`, `word_at(right, at)`, `info()` — so a right cluster cannot be
passed where a left cluster is meant.

## Case conversion

The model is trained on CamelCase, so `FOO_BAR` and `foo_bar` code less well
than `fooBar`.  `varnames.case` rewrites the other two conventions and back:

```python
from varnames import case

case.classify("FOO_BAR")              # 'upper'
case.to_camel("FOO_BAR")              # 'fooBar'
case.from_camel("fooBar", "upper")    # 'FOO_BAR'
```

It is exact — every cased character maps to one character, so the length
changes only by the separators it swallows, and `from_camel(to_camel(x),
classify(x)) == x`.  The cased characters are the ASCII letters and the
1:1-paired letters of `U+00C0–U+017F` and `U+0400–U+052F`
(`varnames/data/case-pairs.txt`, 266 pairs); everything else, Greek and every
script without case included, is inert and passed through.  The definition is
`STANDARD.md` §11.

## What you can rely on

* **One codec, every thread.**  `standard()` loads the tables once under a
  lock, and encoding and decoding mutate nothing, so a single `Codec` can be
  shared.  The cased-pair table is loaded once at import and never changed.
* **Throughput.**  Pure Python, no extension: about 18,000 identifiers a second
  encoded and 17,000 decoded on a 2020s laptop (27,000 a second for
  `tokenise` alone), which is four minutes for the 4.4-million-identifier
  corpus.  This is a reference implementation, not a hot path.
* **One version number.**  `varnames.__version__` is `0.1.0`; until 1.0, minor
  versions may change the API.
* **Types.**  The package is annotated and ships `py.typed`.

## Command line

`python -m varnames` works from a checkout; `varnames` is the same command once
installed.

```console
$ varnames encode getUserName foo
getUserName  124101637  27 bits
foo         7043  13 bits
$ varnames decode 124101637
getUserName  27 bits
$ varnames info
standard model 976670d7  V=8191 k=32 q=1 alphabet=63 rules=8128 kq=32
```

`--model PATH` reads another `NVM1` file.

## Installing

```sh
pip install .
```

Nothing is required beyond Python 3.9.

## Testing

```sh
python3 -m unittest discover -s tests
```

The suite takes a few seconds.  It includes `test_held_out_rate`, which walks
the held-out corpus and
checks the measured 45.218 bits per identifier, 85.0 % within 64 bits and
99.0 % within 128 bits.  `standard/golden.txt` pins the two
implementations to the same codes.

## Licence

The code is **MIT OR Apache-2.0**, at your option. The packaged standard tables
(`varnames/data/model.nvm1`, `case-pairs.txt`, and the corpus they were derived
from) are **CC0-1.0**. All three texts ship in this directory — `LICENSE-MIT`,
`LICENSE-APACHE`, `LICENSE-CC0` — and `pyproject.toml`'s `license` field names
the code's dual licence. The model is data, and CC0 is what lets a program embed
it without an attribution burden.
