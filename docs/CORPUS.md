# The identifier corpus

This is the training corpus for the identifier-compression research: lists of
**programming-language identifiers**, where an identifier is a token matching

```
[A-Za-z_][A-Za-z0-9_]*      (ASCII only)
```

i.e. it starts with an ASCII letter or underscore, and subsequent characters are
ASCII letters, underscores, or digits. We deliberately favour **namespace-rich
languages** (modules / classes / packages) over languages like C that lack
namespaces and therefore push authors into global prefixing conventions (`gl_`,
`SDL_`, …), which distort identifier statistics.

This document consolidates the corpus statistics and the reproduction
instructions. Narrative background lives in the top-level `README.md`.

## Files

| File | Distinct identifiers | Description |
|---|---|---|
| `corpus/identifiers.multilang.txt` | **2,365,468** | **Recommended.** Union across 6 ecosystems, sorted, unique, lexically scrubbed. |
| `corpus/by_language/ruby.txt` | 710,477 | RubyGems harvest. |
| `corpus/by_language/rust.txt` | 1,290,194 | crates.io harvest. |
| `corpus/by_language/python.txt` | 363,927 | Local CPython 3.13 stdlib + dist-packages. |
| `corpus/by_language/go.txt` | 154,229 | Local Go 1.24 standard library. |
| `corpus/by_language/javascript.txt` | 10,049 | Local `/usr/share/javascript`. |
| `corpus/by_language/perl.txt` | 17,304 | Local Perl 5 module tree. |

The union is derived from `by_language/` with `LC_ALL=C sort -m -u`, so there
are no duplicate per-language copies. The old Ruby-only `identifiers.txt` was
byte-identical with `by_language/ruby.txt` and has been removed. There is also
no length-capped (`max128`) variant; truncating long tokens is left to the
consumer.

## Composition

| Language | Distinct IDs | Mean len | Median len | How obtained |
|---|---:|---:|---:|---|
| Ruby | 710,477 | 17.8 | 15 | RubyGems: 8,423 unpacked gems, 226,878 files |
| Rust | 1,290,194 | 18.8 | 17 | crates.io: 2,500 crates, 64,650 `.rs` files |
| Python | 363,927 | 15.5 | 14 | local CPython 3.13 stdlib + dist-packages, 13,710 files |
| Go | 154,229 | 13.5 | 11 | local Go 1.24 standard library, 7,115 files |
| JavaScript | 10,049 | 8.6 | 8 | local `/usr/share/javascript`, 2,786 files |
| Perl | 17,304 | 10.0 | 9 | local Perl 5 module tree, 752 files |
| **union** | **2,365,468** | | | 180,712 overlaps removed (per-language sum 2,546,180) |

## Union statistics

<!-- The block below is the output of
     python3 scripts/stats.py corpus/identifiers.multilang.txt --title 'multi-language union'
     (verified current). -->

| Metric | Value |
|---|---|
| Distinct identifiers | 2,365,468 |
| Total characters | 42,896,750 |
| Mean length | 18.13 |
| Median length | 16 |
| Min length | 1 |
| Max length | 264 |
| Distinct characters | 63 |
| Starts with `_` | 86,482 (3.66%) |
| Contains `_` | 1,582,262 (66.89%) |
| Ends with a digit | 168,310 (7.12%) |
| Contains a digit | 298,954 (12.64%) |
| ALL_CAPS style | 365,316 (15.44%) |
| Contains inner capitals (camel/Pascal) | 1,040,061 (43.97%) |

### Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 8 |
| p25 | 11 |
| p50 | 16 |
| p75 | 23 |
| p90 | 31 |
| p95 | 37 |
| p99 | 55 |
| p99.9 | 87 |
| p99.99 | 133 |
| max | 264 |

### Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 961,255 | 40.64% |
| 17-24 | 630,969 | 26.67% |
| 25-32 | 278,140 | 11.76% |
| 33-48 | 159,148 | 6.73% |
| 49-64 | 30,078 | 1.27% |
| 65-96 | 9,005 | 0.38% |
| 97-128 | 1,251 | 0.05% |
| 129-256 | 287 | 0.01% |
| >256 | 2 | 0.00% |

### Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 3,937,382 | 9.18% |
| `_` | 3,521,774 | 8.21% |
| `t` | 2,950,150 | 6.88% |
| `r` | 2,188,632 | 5.10% |
| `a` | 2,187,341 | 5.10% |
| `i` | 2,060,074 | 4.80% |
| `s` | 2,053,976 | 4.79% |
| `o` | 1,958,982 | 4.57% |
| `n` | 1,931,051 | 4.50% |
| `l` | 1,378,410 | 3.21% |
| `c` | 1,257,573 | 2.93% |
| `d` | 1,171,307 | 2.73% |
| `p` | 1,023,667 | 2.39% |
| `u` | 926,838 | 2.16% |
| `m` | 865,363 | 2.02% |
| `E` | 844,834 | 1.97% |
| `S` | 687,075 | 1.60% |
| `T` | 680,759 | 1.59% |
| `I` | 637,926 | 1.49% |
| `A` | 624,959 | 1.46% |

### Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `t` | 170,384 | 7.20% |
| `s` | 135,101 | 5.71% |
| `c` | 111,772 | 4.73% |
| `p` | 96,356 | 4.07% |
| `S` | 91,039 | 3.85% |
| `_` | 86,482 | 3.66% |
| `r` | 83,265 | 3.52% |
| `I` | 80,892 | 3.42% |
| `D` | 73,352 | 3.10% |
| `a` | 71,960 | 3.04% |
| `C` | 70,505 | 2.98% |
| `d` | 68,673 | 2.90% |
| `i` | 67,985 | 2.87% |
| `g` | 66,589 | 2.82% |
| `P` | 59,571 | 2.52% |

### Notes

- 289 identifiers exceed 128 characters; the longest is 264 chars and is almost
  certainly an embedded blob (base64 font/source-map data) rather than a real
  identifier.
- Longest token begins: `abcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabcdefghijkabc…`

## Method

* **Lexical scrubbing first.** Before identifiers are collected, each source file
  is lexically scrubbed by `scripts/extract.py`: string literals
  (single/double quoted, triple-quoted, raw strings, backtick/template strings,
  Ruby `%`-literals, Perl `q`/`qq`/`qw` forms), regex literals (`/.../`, `m//`,
  `qr//`, `s///`, `tr///`, `y///`), comments (`#`, `//`, `/* … */`, Ruby
  `=begin`/`=end`, Perl POD), heredocs (`<<TAG`, including markers followed by
  trailing code), Perl `__DATA__`/`__END__`, numeric literals
  (`0x…`/`0b…`/`0o…`, decimals, floats, exponents, digit separators and
  integer/float type suffixes), and non-ASCII runs are all replaced by spaces.
  The scrubbed buffer is then tokenised with a single regex
  (`[A-Za-z_][A-Za-z0-9_]*`), so base64 blobs, PEM certificates, hex dumps,
  URLs, the tails of hex/binary/decimal literals and English prose inside
  literals never reach the corpus. Scrubbing is per-extension, so Rust
  attributes are not mistaken for comments, Ruby percent-literals are not
  mistaken for modulo, and Rust lifetimes and char literals (`'a`, `'_`,
  `'static`, `b'\x41'`) are not mistaken for string delimiters.
* **Identifier extraction** is lexical: after scrubbing, everything matching
  `[A-Za-z_][A-Za-z0-9_]*` is kept, then sorted and de-duplicated
  (`LC_ALL=C sort -u`). Files containing NUL bytes are skipped as binary.
* **Ruby (network).** A uniform random sample of 10,000 gems was drawn from the
  full RubyGems catalogue (`https://rubygems.org/versions`, ~219,777 gems),
  taking the latest version of each. 9,023 archives downloaded (~1.9 GB); 8,423
  unpacked and scanned (226,878 files).
* **Rust (network).** The first 2,500 crates by download count on crates.io
  (~374 MB of `.crate` archives, ~2.4 GB unpacked).
* **Python / Go / JavaScript / Perl (offline).** Harvested from sources already
  installed on the host, so they cost no network bandwidth.

## Hardening: the literal-leak audit

The scrubber is lexical, not a parser, so the interesting question is not "is it
correct?" but "what still leaks?".  `scripts/audit_extract.py` answers it
directly: it scans a source tree **with the production scrubber** and reports any
file whose *output* still contains a token that looks like literal data (a hex
blob, a UUID fragment, a digit blob), quoting the surrounding source so the
missed construct can be identified.  Run over the Ruby tree (226,878 files) it
flagged 241 files (0.11 %) — enough to find the misses, small enough to fix all
of them by class rather than by exception.

Five classes were found and fixed (all are now regression cases in
`scripts/check_extract.py`, 15 cases):

| class | example | effect if missed |
|---|---|---|
| **regex containing an apostrophe** | `raise_error( /can't modify frozen/i )` | the `'` starts a phantom string, **flipping the quote parity for the rest of the file** — every later literal then leaks |
| **multi-line regex** (`/x`) | `/\\A (?:[0-9a-f]{8}-… )\\z/ix` over four lines | hex blobs and UUID patterns leak |
| **quoted heredoc tag that is not an identifier** | `YAML.load <<-'5032c8a5-…e16381'` | the whole YAML fixture leaks (UUIDs, hostnames) |
| **string nested in `#{…}`** | `"… #{x + "deadbeef…"} …"` | the outer string ends at the inner quote and the remainder leaks |
| **leftover merge-conflict markers** | `>>>>>>> ccf863516cd6c75a…` (a commit hash) | the hash is harvested as an identifier |

Two further changes came out of the same audit: the heredoc blank now starts at
the line *after* the marker (so `cat <<EOF > out.txt` keeps `out`), and the tag
itself is still blanked.  Scrubbers for Haskell (`--`, `{- -}`, `'c'` chars),
OCaml (`(* *)`, `"…"`, `'c'` chars but **not** `'a` type variables) and Lua
(`--`, `--[[ ]]`, `[[…]]` long strings) were added at the same time, because the
four new ecosystems (below) need them: without OCaml's `(* *)` and Haskell's
`--`, comments would have flooded those lists with English prose.

**What it costs and what it bought** *(to be filled from the re-extraction —
the point of the audit is that every leak class found is now fixed by rule, not
by a per-token exception list, so the fix remains valid on a different corpus.)*

## What is — and is not — in here

* ✅ Real identifiers from real shipped code: method/class/module/constant names,
  including long generated names (GHC-mangled Haskell symbols, verbose
  XBRL/GAAP accounting terms, protobuf/OpenAPI-generated Rust) — good material
  for compression.
* ✅ String literals, regex literals, comments, heredocs, POD and non-ASCII text
  are scrubbed *before* tokenisation. The corpus therefore contains no base64
  payloads, PEM certificates, hex dumps, URLs or English prose from literals,
  and no non-ASCII identifiers. Validation on the union reports 0 tokens
  containing `+`, `/` or `=` and 0 non-ASCII tokens.
* ⚠️ Scrubbing is *lexical, not a full parser*. Exotic syntax (unusual heredoc
  markers, interpolated regexes, generated data embedded outside any literal)
  may still leak in rare edge cases. Language keywords (`def`, `end`, `class`,
  `fn`, `impl`, …) are retained, as are genuine long generated identifiers.
* ⚠️ A residual 15 tokens (<0.001%) look like pure hex strings. Most are genuine
  fixture data embedded in string/heredoc bodies (e.g. UUID fragments in Ruby
  test fixtures, `deadbeef…` markers); the numeric-literal scrubber removed the
  former 310k-token `x…`/`b…`/`e…`/`_…` hex-suffix flood.
* ⚠️ The per-language files are lexical extractions from file trees; they do not
  record which token came from which file or how often it occurred.

## Validation

Per-language files, checked with `grep -cE '^$'` (empty lines) and
`grep -cvE '^[A-Za-z_][A-Za-z0-9_]*$'` (violations) — all zero:

| File | Lines | Empty | Violations |
|---|---:|---:|---:|
| `corpus/by_language/ruby.txt` | 710,477 | 0 | 0 |
| `corpus/by_language/rust.txt` | 1,290,194 | 0 | 0 |
| `corpus/by_language/python.txt` | 363,927 | 0 | 0 |
| `corpus/by_language/go.txt` | 154,229 | 0 | 0 |
| `corpus/by_language/javascript.txt` | 10,049 | 0 | 0 |
| `corpus/by_language/perl.txt` | 17,304 | 0 | 0 |

Union checks:

```
cat corpus/by_language/*.txt | wc -l                              # 2,546,180 (sum)
cat corpus/by_language/*.txt | LC_ALL=C sort -u | wc -l          # 2,365,468 (union)
```

The offline subset (Go + Python + JavaScript + Perl) unions to 527,316:

```
cat corpus/by_language/go.txt corpus/by_language/python.txt \
    corpus/by_language/javascript.txt corpus/by_language/perl.txt \
  | LC_ALL=C sort -u | wc -l
```

`scripts/validate_corpus.py` additionally checks sortedness, uniqueness,
ASCII-only content and known artefacts.

## Per-language harvest reports

### Ruby (RubyGems)

| Metric | Value |
|---|---|
| Distinct identifiers | 710,477 |
| Total characters | 12,657,587 |
| Mean length | 17.82 |
| Median length | 15 |
| Min length | 1 |
| Max length | 264 |
| Distinct characters | 63 |
| Starts with `_` | 7,318 (1.03%) |
| Contains `_` | 477,991 (67.28%) |
| Ends with a digit | 17,273 (2.43%) |
| Contains a digit | 36,172 (5.09%) |
| ALL_CAPS style | 57,213 (8.05%) |
| Contains inner capitals (camel/Pascal) | 231,408 (32.57%) |

Length percentiles: p10 8, p25 11, p50 15, p75 21, p90 30, p95 37, p99 62,
p99.9 107, p99.99 148, max 264. 241 identifiers exceed 128 characters; the
longest (264 chars) is almost certainly an embedded blob (base64 font/source-map
data).

### Rust (crates.io)

| metric | value |
|---|---|
| crates listed | 2,500 |
| crates downloaded | 2,500 |
| crates unpacked | 2,500 |
| `.rs` files scanned | 64,650 |
| distinct identifiers | **1,290,194** |

* **Source list:** crates.io API `/api/v1/crates?page=N&per_page=100&sort=downloads`
  (pages 1–25), no auth, custom `User-Agent`. Up to 2,500 crates; for each we
  used `max_stable_version` (falling back to `max_version`). Saved to
  `work/rust_crates.txt` as `name version` lines.
* **Download:** `https://static.crates.io/crates/NAME/NAME-VERSION.crate`,
  fetched with `xargs -P32` and `curl --max-time 60`, into `work/rust_dl/`.
* **Unpack:** each `.crate` is a gzipped tarball with top directory
  `NAME-VERSION/`, extracted into `work/rust_src/`. Corrupt/truncated archives
  are skipped; already-unpacked directories are not re-extracted.
* **Extraction:** `python3 scripts/extract.py work/clean_ids/rust.shards
  work/rust_src --exts .rs --threshold 400000`, then
  `LC_ALL=C sort -u work/clean_ids/rust.shards > corpus/by_language/rust.txt`.

Failures/skips: the parallel download batch initially missed one crate
(`v8-152.2.0`), re-fetched explicitly and succeeded (2,500/2,500). All archives
unpacked with a top-level `Cargo.toml`. `find` located 64,651 `.rs` files; the
tokeniser scanned 64,650 (1 skipped for containing NUL bytes).

### Local offline harvest (Go, Python, JavaScript, Perl)

| Language | Source roots | Files scanned | Distinct identifiers | Violations |
|---|---|---:|---:|---:|
| Go | `/usr/share/go-1.24/src` | 7,115 | 154,229 | 0 |
| Python | `/usr/lib/python3.13`, `/usr/lib/python3/dist-packages` | 13,710 | 363,927 | 0 |
| JavaScript | `/usr/share/javascript` | 2,786 | 10,049 | 0 |
| Perl | `/usr/share/perl5`, `/usr/lib/aarch64-linux-gnu/perl5` | 752 | 17,304 | 0 |

Per-language extension sets: Go `.go`; Python `.py,.pyi,.pyx`; JavaScript
`.js,.mjs,.jsx`; Perl `.pl,.pm`. All requested roots existed and were scanned;
individual files may have been skipped for being binary (NUL bytes), for having
an extension outside the set, or for permission errors.

## Reproducing

### Ruby (network)

```bash
curl -s -o data/rubygems_versions.txt https://rubygems.org/versions
python3 scripts/fetch_gems.py data/rubygems_versions.txt work/gems_dl --limit 10000 --seed 42
python3 scripts/unpack_gems.py work/gems_dl work/gems_src
python3 scripts/extract.py work/clean_ids/ruby.shards work/gems_src \
    --exts .rb,.rake,.gemspec,.erb --threshold 400000
LC_ALL=C sort -u work/clean_ids/ruby.shards > corpus/by_language/ruby.txt
```

### Rust (network)

```bash
# collect up to 2,500 crate name/version pairs from the crates.io API, then
# download https://static.crates.io/crates/NAME/NAME-VERSION.crate and unpack.
python3 scripts/extract.py work/clean_ids/rust.shards work/rust_src \
    --exts .rs --threshold 400000
LC_ALL=C sort -u work/clean_ids/rust.shards > corpus/by_language/rust.txt
```

### Local ecosystems (offline)

```bash
python3 scripts/extract.py work/clean_ids/go.shards         /usr/share/go-1.24/src                        --exts .go        --threshold 400000
python3 scripts/extract.py work/clean_ids/python.shards     /usr/lib/python3.13 /usr/lib/python3/dist-packages --exts .py,.pyi,.pyx --threshold 400000
python3 scripts/extract.py work/clean_ids/javascript.shards /usr/share/javascript                       --exts .js,.mjs,.jsx --threshold 400000
python3 scripts/extract.py work/clean_ids/perl.shards       /usr/share/perl5 /usr/lib/aarch64-linux-gnu/perl5 --exts .pl,.pm --threshold 400000
for f in work/clean_ids/*.shards; do
    LC_ALL=C sort -u "$f" > "corpus/by_language/$(basename "$f" .shards).txt"
done
```

### Rebuild the union

```bash
LC_ALL=C sort -m -u corpus/by_language/*.txt > corpus/identifiers.multilang.txt
# corpus statistics (the "Union statistics" block above):
python3 scripts/stats.py corpus/identifiers.multilang.txt --title 'multi-language union'
```

## Extending the corpus

`scripts/extract.py` is language-agnostic and whitelists a broad set of
namespace-rich file types. Good next targets: npm/Packagist (JS/PHP), Maven
source jars (Java), PyPI wheels for packages not installed locally, and more
Rust/Java generated-code ecosystems. Add a language by running the three stages
(fetch → unpack → extract) and dropping the result in `corpus/by_language/`.

## Licensing & provenance

Identifiers are extracted as facts from openly published package sources and
locally installed open-source software. Individual packages carry their own
licenses. This repository contains only the derived token lists, not the
original source code.
