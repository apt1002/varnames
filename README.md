# varnames — a corpus of programming-language identifiers

Goal: build a training corpus of **programming-language identifiers** for research
into identifier-specific compression. Identifiers are restricted to the form

```
[A-Za-z_][A-Za-z0-9_]*      (ASCII only)
```

i.e. they start with an ASCII letter or underscore, and subsequent characters are
ASCII letters, underscores, or digits.

We deliberately favour **namespace-rich languages** (modules / classes / packages)
over languages like C that lack namespaces and therefore push authors into global
prefixing conventions (`gl_`, `SDL_`, …), which distort identifier statistics.

## The corpus

| File | Distinct identifiers | Description |
|---|---|---|
| `corpus/identifiers.multilang.txt` | **2,365,468** | **Recommended.** Union across 6 ecosystems, sorted, unique, lexically scrubbed. |
| `corpus/identifiers.multilang.max128.txt` | 2,365,179 | Same union, tokens >128 chars removed. |
| `corpus/identifiers.txt` | 710,477 | Ruby-only corpus (cleaned). |
| `corpus/identifiers.max128.txt` | 710,236 | Ruby-only, length-capped. |
| `corpus/by_language/*.txt` | — | Per-ecosystem lists: `ruby`, `rust`, `python`, `go`, `javascript`, `perl`. |

Statistics: [`docs/CORPUS_STATS_MULTILANG.md`](docs/CORPUS_STATS_MULTILANG.md)
(combined) and [`docs/CORPUS_STATS.md`](docs/CORPUS_STATS.md) (Ruby-only detail).

### Composition

| Language | Distinct IDs | Mean len | Median len | How obtained |
|---|---:|---:|---:|---|
| Ruby | 710,477 | 17.8 | 15 | RubyGems: 8,423 unpacked gems, 226,878 files |
| Rust | 1,290,194 | 18.8 | 17 | crates.io: 2,500 crates, 64,650 `.rs` files |
| Python | 363,927 | 15.5 | 14 | local CPython 3.13 stdlib + dist-packages, 13,710 files |
| Go | 154,229 | 13.5 | 11 | local Go 1.24 standard library, 7,115 files |
| JavaScript | 10,049 | 8.6 | 8 | local `/usr/share/javascript`, 2,786 files |
| Perl | 17,304 | 10.0 | 9 | local Perl 5 module tree, 752 files |
| **union** | **2,365,468** | | | 180,712 overlaps removed |

### Method

* **Lexical scrubbing first.** Before identifiers are collected, each source file is
  lexically scrubbed by `scripts/extract.py`: string literals (single/double quoted,
  triple-quoted, raw strings, backtick/template strings, Ruby `%`-literals, Perl
  `q`/`qq`/`qw` forms), regex literals (`/.../`, `m//`, `qr//`, `s///`, `tr///`, `y///`),
  comments (`#`, `//`, `/* ... */`, Ruby `=begin`/`=end`, Perl POD), heredocs
  (`<<TAG`, including markers followed by trailing code), Perl `__DATA__`/`__END__`,
  numeric literals (`0x…`/`0b…`/`0o…`, decimals, floats, exponents, digit
  separators and integer/float type suffixes), and non-ASCII runs are all replaced
  by spaces. The scrubbed buffer is then tokenised with a single regex
  (`[A-Za-z_][A-Za-z0-9_]*`), so base64 blobs, PEM certificates, hex dumps, URLs,
  the tails of hex/binary/decimal literals and English prose inside literals never
  reach the corpus. Scrubbing is per-extension, so Rust attributes are not mistaken
  for comments, Ruby percent-literals are not mistaken for modulo, and Rust
  lifetimes and char literals (`'a`, `'_`, `'static`, `b'\x41'`) are not mistaken
  for string delimiters.
* **Identifier extraction** is lexical: after scrubbing, everything matching
  `[A-Za-z_][A-Za-z0-9_]*` is kept, then sorted and de-duplicated. Files containing
  NUL bytes are skipped as binary.
* **Ruby** came from a uniform random sample of 10,000 gems drawn from the full
  RubyGems catalogue (`https://rubygems.org/versions`, ~219,777 gems), taking the
  latest version of each. 9,023 archives downloaded (~1.9 GB); 8,423 unpacked and scanned.
* **Rust** came from the first 2,500 crates by download count on crates.io (~374 MB
  of `.crate` archives, ~2.4 GB unpacked).
* **Python / Go / JavaScript / Perl** were harvested offline from sources already
  installed on the host, so they cost no network bandwidth.

### What is — and is not — in here

* ✅ Real identifiers from real shipped code: method/class/module/constant names,
  including long generated names (GHC-mangled Haskell symbols, verbose XBRL/GAAP
  accounting terms, protobuf/OpenAPI-generated Rust) — good material for compression.
* ✅ String literals, regex literals, comments, heredocs, POD and non-ASCII text are
  scrubbed *before* tokenisation. The corpus therefore contains no base64 payloads,
  PEM certificates, hex dumps, URLs or English prose from literals, and no non-ASCII
  identifiers. Validation on the union reports 0 tokens containing `+`, `/` or `=` and
  0 non-ASCII tokens.
* ⚠️ Scrubbing is *lexical, not a full parser*. Exotic syntax (unusual heredoc
  markers, interpolated regexes, generated data embedded outside any literal) may
  still leak in rare edge cases. Language keywords (`def`, `end`, `class`, `fn`,
  `impl`, …) are retained, as are genuine long generated identifiers.
* ⚠️ A residual 15 tokens (<0.001%) look like pure hex strings. Most are genuine
  fixture data embedded in string/heredoc bodies (e.g. UUID fragments in Ruby test
  fixtures, `deadbeef…` markers); the numeric-literal scrubber removed the former
  310k-token `x…`/`b…`/`e…`/`_…` hex-suffix flood. The `.max128` variants remove
  tokens longer than 128 characters.
* ⚠️ The per-language files are lexical extractions from file trees; they do not
  record which token came from which file or how often it occurred.

## Layout

```
varnames/
├── corpus/
│   ├── identifiers.multilang.txt        # union of all 6 ecosystems (2,365,468)
│   ├── identifiers.multilang.max128.txt # union, length-capped
│   ├── identifiers.txt                  # Ruby-only (710,477)
│   ├── identifiers.max128.txt           # Ruby-only, length-capped
│   └── by_language/
│       ├── ruby.txt  rust.txt  python.txt  go.txt  javascript.txt  perl.txt
├── docs/
│   ├── CORPUS_STATS_MULTILANG.md        # combined statistics
│   ├── CORPUS_STATS.md                  # Ruby-only statistics
│   ├── CORPUS_STATS_LOCAL.md            # Python/Go/JS/Perl harvest report
│   └── CORPUS_STATS_RUST.md             # Rust harvest report
├── scripts/
│   ├── extract.py                       # streaming regex tokeniser (memory-bounded)
│   ├── fetch_gems.py                    # parallel RubyGem downloader
│   ├── unpack_gems.py                   # .gem → source tree
│   ├── stats.py                         # corpus statistics → Markdown
│   ├── validate_corpus.py               # sorted/unique/ASCII + artefact check
│   ├── classify_identifiers.py          # lower_case / UPPER_CASE / CamelCase split
│   ├── camelize_identifiers.py          # snake_case → CamelCase conversion
│   ├── merge_identifiers.py             # merge the three lists, de-duplicate
│   ├── common_substrings.py             # ^id$ substrings occurring ≥ N times
│   └── run_camel_pipeline.sh            # run the four steps end to end
└── data/
    └── rubygems_versions.txt            # RubyGems compact index (regenerable)
```

## CamelCase normalisation and common substrings

`scripts/run_camel_pipeline.sh` (or the four scripts individually) derives a
normalised corpus and its frequent substrings from `corpus/identifiers.multilang.txt`:

1. **classify** — split into `lower_case` (has lower-case letters, no
   upper-case), `UPPER_CASE` (upper-case, no lower-case) and `CamelCase` (both).
2. **camelize** — rewrite the non-CamelCase lists in CamelCase: the first
   letter after a run of underscores is upper-cased and all other letters,
   including the leading letter of the identifier, are lower-cased, so `a`, `_a`
   and `__a` stay distinct (`a`, `A`, `_A`); a run of underscores before a
   letter gives up exactly one underscore (its word separator) and keeps the
   rest, so `a_b` → `aB` but `a__b` → `a_B` (underscores before a digit, or at
   the end, are kept as-is).
3. **merge** — concatenate the CamelCase list with the two converted lists and
   de-duplicate (`LC_ALL=C sort -u`).
4. **common substrings** — wrap every identifier as `^identifier$`, then
   enumerate all substrings occurring at least 10000 times (Apriori/BFS over
   length with a 64-bit rolling-hash count). The empty string is common by
   definition.

On the current union (2,365,468 identifiers → 2,295,340 after normalisation and
de-duplication) this yields 2,102 common substrings, the longest being 9
characters (`Attribute`, `Response$`). The empty string, `^`, `$` and all 65
single characters (`a-z`, `A-Z`, `0-9`, `_`, `^`, `$`) occur at least 10000
times.

```sh
sh scripts/run_camel_pipeline.sh corpus/identifiers.multilang.txt work/camel
```

## Reproducing

### Ruby (network)

```bash
curl -s -o data/rubygems_versions.txt https://rubygems.org/versions
python3 scripts/fetch_gems.py data/rubygems_versions.txt work/gems_dl --limit 10000 --seed 42
python3 scripts/unpack_gems.py work/gems_dl work/gems_src
python3 scripts/extract.py work/clean_ids/ruby.shards work/gems_src \
    --exts .rb,.rake,.gemspec,.erb --threshold 400000
LC_ALL=C sort -u work/clean_ids/ruby.shards > corpus/identifiers.txt
awk 'length($0)>=1 && length($0)<=128' corpus/identifiers.txt > corpus/identifiers.max128.txt
```

### Rust (network)

```bash
# collect up to 2,500 crate name/version pairs from the crates.io API, then
# download https://static.crates.io/crates/NAME/NAME-VERSION.crate and unpack.
# See docs/CORPUS_STATS_RUST.md for the exact figures used here.
python3 scripts/extract.py work/clean_ids/rust.shards work/rust_src --exts .rs --threshold 400000
LC_ALL=C sort -u work/clean_ids/rust.shards > corpus/by_language/rust.txt
```

### Local ecosystems (offline)

```bash
python3 scripts/extract.py work/clean_ids/go.shards     /usr/share/go-1.24/src              --exts .go        --threshold 400000
python3 scripts/extract.py work/clean_ids/python.shards /usr/lib/python3.13 /usr/lib/python3/dist-packages --exts .py,.pyi,.pyx --threshold 400000
python3 scripts/extract.py work/clean_ids/javascript.shards /usr/share/javascript             --exts .js,.mjs,.jsx --threshold 400000
python3 scripts/extract.py work/clean_ids/perl.shards   /usr/share/perl5 /usr/lib/aarch64-linux-gnu/perl5 --exts .pl,.pm --threshold 400000
for f in work/clean_ids/*.shards; do LC_ALL=C sort -u "$f" > "corpus/by_language/$(basename "$f" .shards).txt"; done
```

### Rebuild the union

```bash
LC_ALL=C sort -m -u corpus/by_language/*.txt > corpus/identifiers.multilang.txt
awk 'length($0)<=128' corpus/identifiers.multilang.txt > corpus/identifiers.multilang.max128.txt
python3 scripts/stats.py corpus/identifiers.multilang.txt > docs/CORPUS_STATS_MULTILANG.md
```

## Extending the corpus

`scripts/extract.py` is language-agnostic and whitelists a broad set of
namespace-rich file types. Good next targets: npm/Packagist (JS/PHP), Maven source
jars (Java), PyPI wheels for packages not installed locally, and more Rust/Java
generated-code ecosystems. Add a language by running the three stages
(fetch → unpack → extract) and dropping the result in `corpus/by_language/`.

## Licensing & provenance

Identifiers are extracted as facts from openly published package sources and
locally installed open-source software. Individual packages carry their own
licenses. This repository contains only the derived token lists, not the original
source code.
