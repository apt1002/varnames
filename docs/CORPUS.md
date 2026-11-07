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
| `corpus/identifiers.multilang.txt` | **4,441,974** | **Recommended.** Union across 10 ecosystems, sorted, unique, lexically scrubbed. |
| `corpus/by_language/ruby.txt` | 710,173 | RubyGems harvest. |
| `corpus/by_language/rust.txt` | 1,290,194 | crates.io harvest. |
| `corpus/by_language/ocaml.txt` | 1,019,741 | opam harvest. |
| `corpus/by_language/haskell.txt` | 886,251 | Hackage harvest. |
| `corpus/by_language/java.txt` | 403,427 | Maven Central harvest. |
| `corpus/by_language/python.txt` | 364,165 | Local CPython 3.13 stdlib + dist-packages. |
| `corpus/by_language/go.txt` | 154,229 | Local Go 1.24 standard library. |
| `corpus/by_language/lua.txt` | 139,816 | LuaRocks harvest. |
| `corpus/by_language/perl.txt` | 17,196 | Local Perl 5 module tree. |
| `corpus/by_language/javascript.txt` | 10,049 | Local `/usr/share/javascript`. |

The union is derived from `by_language/` with `LC_ALL=C sort -m -u`, so there
are no duplicate per-language copies. The old Ruby-only `identifiers.txt` was
byte-identical with `by_language/ruby.txt` and has been removed. There is also
no length-capped (`max128`) variant; truncating long tokens is left to the
consumer.  The lists are dedicated to the public domain under CC0-1.0, to the
extent we hold rights in them — see *Licensing, provenance and authorship* in
`README.md`.

## Composition

| Language | Distinct IDs | Mean len | Median len | How obtained |
|---|---:|---:|---:|---|
| Ruby | 710,173 | 17.82 | 15 | RubyGems: 8,423 unpacked gems, 226,878 files |
| Rust | 1,290,194 | 18.77 | 17 | crates.io: 2,500 crates, 64,650 `.rs` files |
| OCaml | 1,019,741 | 15.39 | 14 | opam: sources of packages ranked by reverse dependencies |
| Haskell | 886,251 | 13.44 | 12 | Hackage: sources of packages ranked by reverse dependencies |
| Java | 403,427 | 17.17 | 16 | Maven Central: `org/apache/**` `-sources.jar` |
| Python | 364,165 | 15.46 | 14 | local CPython 3.13 stdlib + dist-packages, 13,710 files |
| Go | 154,229 | 13.53 | 11 | local Go 1.24 standard library, 7,115 files |
| Lua | 139,816 | 14.75 | 13 | LuaRocks: all packages, ranked by published versions |
| Perl | 17,196 | 10.06 | 9 | local Perl 5 module tree, 752 files |
| JavaScript | 10,049 | 8.60 | 8 | local `/usr/share/javascript`, 2,786 files |
| **union** | **4,441,974** | **16.99** | **15** | 553,267 overlaps removed (per-language sum 4,995,241) |

### The packaged harvests

The four packaged ecosystems are harvested from ecosystem indexes by
`scripts/harvest_packages.py`, which writes a `(package, URL)` plan per language
and then downloads, extracts and discards each archive:

| Ecosystem | Index | Ranking rule | Archive |
|---|---|---|---|
| Haskell | Hackage `index.tar.gz` | reverse dependencies (`build-depends`) | per-package tarball |
| OCaml | opam `index.tar.gz` | reverse dependencies (`depends:`) | per-package tarball |
| Lua | LuaRocks `manifest` | number of published versions | `.src.rock` |
| Java | Maven Central | none — all `org/apache/**` artifacts with a `-sources.jar` | sources jar |

None of those indexes publishes download counts, so the ranking is a
popularity *proxy*, not a download measure. File counts for these four are not
retained: the trees are deleted after extraction (`scripts/harvest_packages.py`
is resumable, so a re-run rebuilds them), while the six original ecosystems'
trees were kept long enough to be audited (see "Hardening").

## Union statistics

<!-- The block below is the output of
     python3 scripts/stats.py corpus/identifiers.multilang.txt --title 'multi-language union'
     with the title line removed and the headings demoted (verified current). -->

| Metric | Value |
|---|---|
| Distinct identifiers | 4,441,974 |
| Total characters | 75,462,935 |
| Mean length | 16.99 |
| Median length | 15 |
| Min length | 1 |
| Max length | 306 |
| Distinct characters | 63 |
| Starts with `_` | 137,872 (3.10%) |
| Contains `_` | 2,423,657 (54.56%) |
| Ends with a digit | 304,691 (6.86%) |
| Contains a digit | 512,493 (11.54%) |
| ALL_CAPS style | 451,766 (10.17%) |
| Contains inner capitals (camel/Pascal) | 2,336,504 (52.60%) |

### Length distribution

| Percentile | Length (chars) |
|---|---|
| p10 | 7 |
| p25 | 10 |
| p50 | 15 |
| p75 | 21 |
| p90 | 29 |
| p95 | 35 |
| p99 | 51 |
| p99.9 | 79 |
| p99.99 | 122 |
| max | 306 |

### Length histogram

| Length | Count | % of corpus |
|---|---|---|
| 9-16 | 1,879,192 | 42.31% |
| 17-24 | 1,127,157 | 25.38% |
| 25-32 | 453,306 | 10.21% |
| 33-48 | 241,840 | 5.44% |
| 49-64 | 42,120 | 0.95% |
| 65-96 | 12,459 | 0.28% |
| 97-128 | 1,304 | 0.03% |
| 129-256 | 293 | 0.01% |
| >256 | 3 | 0.00% |

### Character frequency (top 20)

| Char | Occurrences | % of all chars |
|---|---|---|
| `e` | 7,346,422 | 9.74% |
| `t` | 5,450,400 | 7.22% |
| `_` | 5,103,535 | 6.76% |
| `a` | 4,149,495 | 5.50% |
| `r` | 4,064,163 | 5.39% |
| `i` | 3,838,499 | 5.09% |
| `s` | 3,744,404 | 4.96% |
| `o` | 3,729,425 | 4.94% |
| `n` | 3,677,773 | 4.87% |
| `l` | 2,589,144 | 3.43% |
| `c` | 2,340,742 | 3.10% |
| `d` | 2,143,061 | 2.84% |
| `p` | 1,950,515 | 2.58% |
| `u` | 1,729,833 | 2.29% |
| `m` | 1,602,519 | 2.12% |
| `g` | 1,207,117 | 1.60% |
| `E` | 1,172,232 | 1.55% |
| `S` | 1,107,817 | 1.47% |
| `T` | 1,042,059 | 1.38% |
| `f` | 988,365 | 1.31% |

### Leading character (top 15)

| Char | Identifiers | % of corpus |
|---|---|---|
| `s` | 291,670 | 6.57% |
| `t` | 272,502 | 6.13% |
| `c` | 255,528 | 5.75% |
| `p` | 204,572 | 4.61% |
| `a` | 187,593 | 4.22% |
| `r` | 175,234 | 3.94% |
| `g` | 160,381 | 3.61% |
| `i` | 150,375 | 3.39% |
| `d` | 140,812 | 3.17% |
| `_` | 137,872 | 3.10% |
| `S` | 137,046 | 3.09% |
| `m` | 132,124 | 2.97% |
| `f` | 122,470 | 2.76% |
| `C` | 115,670 | 2.60% |
| `e` | 114,180 | 2.57% |

### Notes

- 296 identifiers exceed 128 characters; the longest is 306 chars and is almost certainly an embedded blob (base64 font/source-map data) rather than a real identifier.
- Longest token begins: `GTTCTACAACGTCCAGATCGGAAGCAAGTTCGAAGGAGAGGTCTTGATAACACCAAGCACGAGGTTACCTTCACTCTCAA...`

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

Per-ecosystem provenance — what was downloaded, how much, and the popularity
proxy used to rank packages — is recorded under *Composition* above and
*Per-language harvest reports* below.

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

One second-order bug came out of *validating* the fixes rather than writing
them.  The matcher that blanks multi-line `/x` regexes was itself a new leak: it
fired on slashes *inside ordinary strings* (`:template => '/awesome'`,
`'test/test-data/valid/'`, URL paths), blanked the string's quotes, and thereby
un-stringed the text that followed — the same parity failure the pass exists to
prevent, from the opposite direction.  It is now gated three ways: the opening
slash must sit in code context (after an operator or a bracket, never after a
quote or a word), the closing slash must be followed by code punctuation rather
than a letter or a quote, and a multi-line body must look like a regex rather
than prose.  Both directions are pinned in the regression suite.

**What it costs and what it bought.**  The audit is cheap to run and the fix
is a net subtraction, but not a pure one: repairing a quote-parity error both
hides the text that used to leak *and* reveals the code that the same error had
swallowed, so tokens move in both directions.  Re-extracting the six ecosystems
with the hardened scrubber:

| language | files | tokens before | after | move |
|---|---:|---:|---:|---|
| Ruby | 226,878 | 710,477 | 710,173 | −304 (839 out, 535 in) |
| Rust | 64,650 | 1,290,194 | 1,290,194 | — |
| Python | 13,718 | 363,927 | 364,165 | +238 (drift in the apt tree, not the scrubber) |
| Go | 7,115 | 154,229 | 154,229 | — |
| Perl | 752 | 17,304 | 17,196 | −108 (182 prose out, 74 code in) |
| JavaScript | 2,786 | 10,049 | 10,049 | — |
| **union of those six** | | **2,365,468** | **2,365,354** | **−114** |

Perl is the clearest illustration: the tokens it loses are English (`Adding`,
`Briefly`, `It`, `For`) and the tokens it gains are identifiers the parity error
had been eating (`CancelCmd`, `ListBrowse`).  On Ruby the leak tokens themselves
are gone — the audit's hex-blob class drops from 15 distinct tokens to 8, and
every one of the constructs in the table above now scrubs clean; the eight that
remain are code (`B3360DC80C50` and friends are constants that the old scrubber
was *hiding*), not literal payloads.

The cost is one extra full pass over the trees (~40 minutes for the six
ecosystems on this host) and a ~0.005 % shift in the corpus, so the numbers in
the reports that depend on it move in the third decimal; the rebuild re-measures
them.


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
| `corpus/by_language/rust.txt` | 1,290,194 | 0 | 0 |
| `corpus/by_language/ocaml.txt` | 1,019,741 | 0 | 0 |
| `corpus/by_language/haskell.txt` | 886,251 | 0 | 0 |
| `corpus/by_language/ruby.txt` | 710,173 | 0 | 0 |
| `corpus/by_language/java.txt` | 403,427 | 0 | 0 |
| `corpus/by_language/python.txt` | 364,165 | 0 | 0 |
| `corpus/by_language/go.txt` | 154,229 | 0 | 0 |
| `corpus/by_language/lua.txt` | 139,816 | 0 | 0 |
| `corpus/by_language/perl.txt` | 17,196 | 0 | 0 |
| `corpus/by_language/javascript.txt` | 10,049 | 0 | 0 |

Union checks:

```
cat corpus/by_language/*.txt | wc -l                              # 4,995,241 (sum)
cat corpus/by_language/*.txt | LC_ALL=C sort -u | wc -l          # 4,441,974 (union)
```

The offline subset (Go + Python + JavaScript + Perl) unions to 527,454, and the
six original ecosystems (Ruby + Rust + Python + Go + JavaScript + Perl) to
2,365,354:

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
| Distinct identifiers | 710,173 |
| Total characters | 12,653,610 |
| Mean length | 17.82 |
| Median length | 15 |
| Min length | 1 |
| Max length | 264 |
| Distinct characters | 63 |
| Starts with `_` | 7,311 (1.03%) |
| Contains `_` | 477,914 (67.30%) |
| Ends with a digit | 17,237 (2.43%) |
| Contains a digit | 36,126 (5.09%) |
| ALL_CAPS style | 57,115 (8.04%) |
| Contains inner capitals (camel/Pascal) | 231,234 (32.56%) |

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

### Packaged harvests (Java, Haskell, OCaml, Lua)

Four ecosystems added for language diversity — Java for verbose CamelCase, Haskell
and OCaml for module-qualified lower-case names, Lua for short snake_case.  All
four are harvested by `scripts/harvest_packages.py` (index → plan → download →
extract); see "The packaged harvests" for the indexes and ranking rules.

| Metric | Java | Haskell | OCaml | Lua |
|---|---:|---:|---:|---:|
| Distinct identifiers | 403,427 | 886,251 | 1,019,741 | 139,816 |
| Total characters | 6,926,709 | 11,914,728 | 15,693,605 | 2,062,853 |
| Mean length | 17.17 | 13.44 | 15.39 | 14.75 |
| Median length | 16 | 12 | 14 | 13 |
| Max length | 119 | 306 | 223 | 99 |
| Starts with `_` | 1.11% | 2.23% | 2.85% | 2.58% |
| Contains `_` | 17.32% | 21.22% | 62.68% | 45.11% |
| Ends with a digit | 3.62% | 10.04% | 5.09% | 3.12% |
| ALL_CAPS style | 11.51% | 3.17% | 2.79% | 7.02% |
| Contains inner capitals | 92.62% | 80.28% | 29.52% | 48.03% |

The shape of each ecosystem shows through: Java is 93% CamelCase with almost no
underscores; Haskell's 10% digit-final rate and its 306-character longest token
are GHC-mangled names; OCaml is two-thirds underscore-separated; Lua is short and
mixed.  That spread is the point: 85% of the six-ecosystem union was Rust and
Ruby, both long (18.8 and 17.8 mean length) and underscore-heavy (67%), whereas
the four packaged lists are shorter (13.4–17.2 mean length), much less
underscore-heavy (17–63% of identifiers) and far more CamelCase-dense (30–93%).

### Local offline harvest (Go, Python, JavaScript, Perl)

| Language | Source roots | Files scanned | Distinct identifiers | Violations |
|---|---|---:|---:|---:|
| Go | `/usr/share/go-1.24/src` | 7,115 | 154,229 | 0 |
| Python | `/usr/lib/python3.13`, `/usr/lib/python3/dist-packages` | 13,710 | 364,165 | 0 |
| JavaScript | `/usr/share/javascript` | 2,786 | 10,049 | 0 |
| Perl | `/usr/share/perl5`, `/usr/lib/aarch64-linux-gnu/perl5` | 752 | 17,196 | 0 |

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

### Packaged ecosystems (network)

```bash
# rank by the ecosystem's own proxy, then fetch and unpack (resumable)
python3 scripts/harvest_packages.py plan  haskell --limit 2000
python3 scripts/harvest_packages.py fetch haskell --limit 2000 --jobs 8
python3 scripts/harvest_packages.py plan  ocaml   --limit 2000
python3 scripts/harvest_packages.py fetch ocaml   --limit 2000 --jobs 8
python3 scripts/harvest_packages.py plan  lua     --limit 2000
python3 scripts/harvest_packages.py fetch lua     --limit 2000 --jobs 8
python3 scripts/harvest_packages.py plan  java    --limit 2000
python3 scripts/harvest_packages.py fetch java    --limit 2000 --jobs 8

python3 scripts/extract.py work/clean_ids/haskell.shards work/haskell_src --exts .hs,.lhs --threshold 400000
python3 scripts/extract.py work/clean_ids/ocaml.shards   work/ocaml_src   --exts .ml,.mli --threshold 400000
python3 scripts/extract.py work/clean_ids/lua.shards     work/lua_src     --exts .lua      --threshold 400000
python3 scripts/extract.py work/clean_ids/java.shards    work/java_src    --exts .java     --threshold 400000
for f in work/clean_ids/*.shards; do
    LC_ALL=C sort -u "$f" > "corpus/by_language/$(basename "$f" .shards).txt"
done
```

`plan` writes `work/plans/<lang>.tsv`, so the exact package set behind a corpus
version is recoverable from that file.

## Extending the corpus

`scripts/extract.py` is language-agnostic and whitelists a broad set of
namespace-rich file types. Good next targets: npm and TypeScript, Packagist
(PHP), PyPI wheels for packages not installed locally, and NuGet. Add a language
by running the three stages (fetch → unpack → extract) and dropping the result in
`corpus/by_language/`; an index-driven ecosystem additionally needs a planner in
`scripts/harvest_packages.py` (one function returning `(package, URL)` rows).

## Licensing & provenance

Identifiers are extracted as facts from openly published package sources and
locally installed open-source software. Individual packages carry their own
licences. This repository contains only the derived token lists, not the
original source code. The lists themselves are dedicated to the public domain
under CC0-1.0, to the extent we hold rights in them; the terms for the rest of
the repository are in *Licensing, provenance and authorship* in `README.md`.
