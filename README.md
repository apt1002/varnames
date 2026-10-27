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
| `corpus/identifiers.txt` | **1,424,035** | Canonical corpus: every distinct ASCII identifier, sorted, one per line. |
| `corpus/identifiers.max128.txt` | 1,422,724 | Recommended variant: same list with tokens longer than 128 chars removed (these are embedded base64 blobs, not identifiers). |

Both exceed the 1M target with headroom. See [`docs/CORPUS_STATS.md`](docs/CORPUS_STATS.md)
for the full statistical breakdown.

### Source and method

* **Ecosystem:** RubyGems (Ruby — a properly namespaced language via modules/classes).
* **Packages:** a uniform random sample of **10,000 gems** drawn from the full
  RubyGems catalogue (`https://rubygems.org/versions`, ~219,777 gems); we take the
  **latest version** of each. 9,023 archives downloaded (~1.9 GB); **8,079**
  successfully unpacked and scanned.
* **Files scanned:** 235,676 source files (`.rb`, `.rake`, `.gemspec`, `.erb`).
* **Extraction:** a single regex tokeniser (`scripts/extract.py`) applied to raw
  file bytes. Files containing NUL bytes are skipped as binary. Everything matching
  the identifier regex is kept.

### What is — and is not — in here

* ✅ Real identifiers from real shipped Ruby: method/class/module/constant names,
  including long, generated-looking names from GHC-built libraries
  (e.g. `LanguageziPythonziLexerziKWzuCase_con_e`) and verbose XBRL/GAAP accounting
  symbols — these are excellent material for identifier compression.
* ⚠️ The tokeniser is *lexical, not semantic*: it also captures tokens that occur
  inside comments and string literals (including ordinary English words), and
  language keywords (`def`, `end`, `class`, …). For a compression model this is
  usually harmless — arguably desirable — but it is a known source of noise.
* ⚠️ A tiny number (<0.1%) of very long tokens are embedded base64 payloads
  (fonts, source maps). The `max128` variant removes the worst of these.

## Layout

```
varnames/
├── corpus/
│   ├── identifiers.txt          # full corpus (1,424,035)
│   └── identifiers.max128.txt   # length-capped variant
├── docs/
│   └── CORPUS_STATS.md          # statistical report
├── scripts/
│   ├── extract.py               # streaming regex tokeniser (memory-bounded)
│   ├── fetch_gems.py            # parallel RubyGem downloader
│   ├── unpack_gems.py           # .gem → source tree
│   └── stats.py                 # corpus statistics → Markdown
└── data/
    └── rubygems_versions.txt    # RubyGems compact index (regenerated via curl)
```

## Reproducing

```bash
# 1. Full RubyGems index (list of every gem + versions)
curl -s -o data/rubygems_versions.txt https://rubygems.org/versions

# 2. Fetch a random sample of gems (latest version of each)
python3 scripts/fetch_gems.py data/rubygems_versions.txt work/gems_dl --limit 10000 --seed 42

# 3. Unpack .gem archives into a source tree
python3 scripts/unpack_gems.py work/gems_dl work/gems_src

# 4. Extract the distinct identifier set
python3 scripts/extract.py work/ids.txt work/gems_src

# 5. (optional) sort/uniq and cap length
LC_ALL=C sort -u work/ids.txt > corpus/identifiers.txt
awk 'length($0)<=128' corpus/identifiers.txt > corpus/identifiers.max128.txt
```

## Extending the corpus

The extractor is language-agnostic and already whitelists a broad set of
namespace-rich file types (`.py`, `.rb`, `.js`, `.ts`, `.java`, `.cs`, `.go`, `.rs`,
`.kt`, `.scala`, `.php`, `.pl`, `.ex`, …). To grow or diversify the corpus,
harvest other ecosystems with the same three stages (fetch → unpack → extract),
e.g. crates.io (Rust), PyPI (Python), Maven source jars (Java), Packagist (PHP).

## Licensing & provenance

The identifiers are extracted as facts from openly published package sources on
RubyGems; individual gems carry their own licenses. This repository contains only
the derived token list, not the original source code.
