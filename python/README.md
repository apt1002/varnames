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
| `codec.tokenise(name)` | the model's symbols, before coding |
| `codec.model` | the loaded `Model` |
| `varnames.Codec(varnames.Model.from_path(path))` | any `NVM1` model file instead of the standard one |
| `varnames.case.classify(name)` | `'lower'`, `'upper'` or `'camel'` |
| `varnames.case.to_camel(name)` | rewrite the two snake conventions in CamelCase |
| `varnames.case.from_camel(name, cls)` | the inverse, given the class |

`encode` returns an integer of any size; a 64-bit or 128-bit set is simply the
identifiers whose `bits` fit.  Round trips are exact: `decode(encode(n))` is
`n`, and the terminator is never stored.

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

## Command line

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

The suite includes `test_held_out_rate`, which walks the held-out corpus and
checks the measured 45.218 bits per identifier, 85.0 % within 64 bits and
99.0 % within 128 bits.  `tests/golden.txt` in the Rust crate pins the two
implementations to the same codes.

## Licence

MIT OR Apache-2.0.
