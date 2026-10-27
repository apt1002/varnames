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
| `corpus/identifiers.multilang.txt` | **3,732,017** | **Recommended.** Union across 6 ecosystems, sorted, unique. |
| `corpus/identifiers.multilang.max128.txt` | 3,729,192 | Same union, tokens >128 chars removed (embedded blobs). |
| `corpus/identifiers.txt` | 1,424,035 | Original Ruby-only corpus. |
| `corpus/identifiers.max128.txt` | 1,422,724 | Ruby-only, length-capped. |
| `corpus/by_language/*.txt` | — | Per-ecosystem lists: `ruby`, `rust`, `python`, `go`, `javascript`, `perl`. |

Statistics: [`docs/CORPUS_STATS_MULTILANG.md`](docs/CORPUS_STATS_MULTILANG.md)
(combined) and [`docs/CORPUS_STATS.md`](docs/CORPUS_STATS.md) (Ruby-only detail).

### Composition

| Language | Distinct IDs | Mean len | Median len | How obtained |
|---|---:|---:|---:|---|
| Ruby | 1,424,035 | 16.6 | 13 | RubyGems: 8,079 unpacked gems, 235,676 files |
| Rust | 1,854,408 | 17.5 | 15 | crates.io: 2,500 crates, 64,650 `.rs` files |
| Python | 561,160 | 13.7 | 12 | local CPython 3.13 stdlib + 286 dist-packages, 13,710 files |
| Go | 272,584 | 12.0 | 9 | local Go 1.24 standard library, 7,115 files |
| JavaScript | 67,283 | 7.0 | 6 | local `/usr/share/javascript`, 2,786 files |
| Perl | 42,306 | 8.6 | 8 | local Perl 5 module tree, 752 files |
| **union** | **3,732,017** | | | 489,759 overlaps removed |

### Method

* **Identifier extraction** is lexical: a single regex tokeniser (`scripts/extract.py`)
  is applied to raw file bytes. Files containing NUL bytes are skipped as binary.
  Everything matching `[A-Za-z_][A-Za-z0-9_]*` is kept, then sorted and de-duplicated.
* **Ruby** came from a uniform random sample of 10,000 gems drawn from the full
  RubyGems catalogue (`https://rubygems.org/versions`, ~219,777 gems), taking the
  latest version of each. 9,023 archives downloaded (~1.9 GB); 8,079 unpacked and scanned.
* **Rust** came from the first 2,500 crates by download count on crates.io (~374 MB
  of `.crate` archives, ~2.4 GB unpacked).
* **Python / Go / JavaScript / Perl** were harvested offline from sources already
  installed on the host, so they cost no network bandwidth.

### What is — and is not — in here

* ✅ Real identifiers from real shipped code: method/class/module/constant names,
  including long generated names (GHC-mangled Haskell symbols, verbose XBRL/GAAP
  accounting terms, protobuf/OpenAPI-generated Rust) — good material for compression.
* ⚠️ The tokeniser is *lexical, not semantic*: it also captures tokens that occur
  inside comments and string literals (including ordinary English words) and
  language keywords (`def`, `end`, `class`, `fn`, `impl`, …). For a compression
  model this is usually harmless — arguably desirable — but it is a known source of noise.
* ⚠️ A tiny number (<0.1%) of very long tokens are embedded base64 payloads
  (fonts, source maps). The `.max128` variants remove the worst of these.
* ⚠️ The per-language files are raw lexical extractions from file trees; they do not
  record which token came from which file or how often it occurred.

## Layout

```
varnames/
├── corpus/
│   ├── identifiers.multilang.txt        # union of all 6 ecosystems (3,732,017)
│   ├── identifiers.multilang.max128.txt # union, length-capped
│   ├── identifiers.txt                  # Ruby-only (1,424,035)
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
│   └── stats.py                         # corpus statistics → Markdown
└── data/
    └── rubygems_versions.txt            # RubyGems compact index (regenerable)
```

## Reproducing

### Ruby (network)

```bash
curl -s -o data/rubygems_versions.txt https://rubygems.org/versions
python3 scripts/fetch_gems.py data/rubygems_versions.txt work/gems_dl --limit 10000 --seed 42
python3 scripts/unpack_gems.py work/gems_dl work/gems_src
python3 scripts/extract.py work/ids.txt work/gems_src
LC_ALL=C sort -u work/ids.txt > corpus/identifiers.txt
awk 'length($0)<=128' corpus/identifiers.txt > corpus/identifiers.max128.txt
```

### Rust (network)

```bash
# collect up to 2,500 crate name/version pairs from the crates.io API, then
# download https://static.crates.io/crates/NAME/NAME-VERSION.crate and unpack.
# See docs/CORPUS_STATS_RUST.md for the exact figures used here.
python3 scripts/extract.py work/rust_ids.shards work/rust_src --exts .rs --threshold 400000
LC_ALL=C sort -u work/rust_ids.shards > corpus/by_language/rust.txt
```

### Local ecosystems (offline)

```bash
python3 scripts/extract.py work/local_ids/go.shards     /usr/share/go-1.24/src              --exts .go        --threshold 400000
python3 scripts/extract.py work/local_ids/python.shards /usr/lib/python3.13 /usr/lib/python3/dist-packages --exts .py,.pyi,.pyx --threshold 400000
python3 scripts/extract.py work/local_ids/js.shards     /usr/share/javascript               --exts .js,.mjs,.jsx --threshold 400000
python3 scripts/extract.py work/local_ids/perl.shards   /usr/share/perl5 /usr/lib/aarch64-linux-gnu/perl5 --exts .pl,.pm --threshold 400000
for f in work/local_ids/*.shards; do LC_ALL=C sort -u "$f" > "corpus/by_language/$(basename "$f" .shards).txt"; done
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
