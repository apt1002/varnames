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
│   ├── CORPUS_STATS_RUST.md             # Rust harvest report
│   └── COMPRESSION_ESTIMATES.md         # fixed-budget rate + low-rank adjacency
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
│   ├── run_camel_pipeline.sh            # run the four steps end to end
│   ├── winhash.py                       # 64-bit rolling-hash helpers (shared)
│   ├── successor_distributions.py       # P(next character | common substring)
│   ├── code_lengths.py                  # ideal code length + 64/62-bit fit rates
│   ├── sample_occurrences.py            # per-ecosystem identifier occurrence counts
│   ├── normalise_counts.py              # case-normalise an occurrence-count file
│   ├── pair_matrix.py                   # prefix/suffix adjacency M + low-rank SVD/NMF
│   ├── latent_probabilities.py          # negative-entry remedies, scored by KL
│   ├── sqrt_and_smooth.py               # Hellinger (sqrt) factorisation + smoothing
│   ├── rank1_marginals.py               # rank-1 SVD vs the independence model
│   ├── run_sweep.sh                     # run the analyses over all thresholds
│   ├── cluster_substrings.py            # K-means on the Hellinger embedding
│   ├── fastkern.c                       # OpenMP kernels (assignment/accumulation)
│   └── cluster_entropy.py               # successor entropy (bits) per cluster
└── data/
    └── rubygems_versions.txt            # RubyGems compact index (regenerable)
```

### Working directories (gitignored, regenerable)

```
work/camel/         # case normalisation: lower/upper/camel splits,
                    #   camel_from_lower/upper, merged.txt
work/common10000/   # common substrings (threshold 10000) + successor
                    #   distributions, clusters, entropy
work/common2000/    # the same, at threshold 2000
work/common<T>/     # ... one directory per threshold T
                    #   (500, 1000, 2000, 5000, 10000, 20000, 50000, 100000)
work/occ/           # per-ecosystem identifier occurrence counts
                    #   (<eco>.counts, all.counts, all.camel.counts)
```

`work/` also holds the corpus-build intermediates (`gems_dl/`, `*_src/`,
`clean_ids/`, `*.shards`, per-ecosystem logs).

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

The pipeline writes the case-normalisation artefacts (`lower_case.txt`,
`upper_case.txt`, `camel_case.txt`, `camel_from_lower.txt`,
`camel_from_upper.txt`, `merged.txt`) into the CamelCase directory
(`work/camel`) and the common-substring artefacts into `work/common<THRESHOLD>`;
`THRESHOLD=2000 sh scripts/run_camel_pipeline.sh` therefore produces
`work/common2000`.

## Successor clustering

`scripts/successor_distributions.py` builds, for every common substring, the
empirical distribution of the character that follows it. It uses a
**longest-suffix (variable-order) model**: at each split of a wrapped identifier
`^identifier$` (from just after the `^` to just after the identifier) the
successor is credited to the *longest common substring that is a suffix of the
prefix*, so e.g. after `^Ac` the successor is credited to `^Ac` rather than to
`Ac` or `c`. Every one of the 41,272,149 split positions is assigned to exactly
one context. The rows are the common substrings that can occur as a prefix
suffix (non-empty, not ending in `$`) and a `#global` row carries the
corpus-wide successor marginal, used as a shared Dirichlet prior for smoothing.

`scripts/cluster_substrings.py` groups the contexts by their successor
distribution, with two objectives:

* `--method kl` (default) directly minimises the occurrence-weighted
  cross-entropy `Σ_s N_s · H(p_s ‖ P_cluster(s))`, which equals `H(next |
  cluster)`; assignment is to the smallest cross-entropy and the update is the
  pooled-count mean (Lloyd's algorithm for the KL/multinomial objective). This
  optimises exactly the quantity we report.
* `--method sphere` embeds `√p` on the unit sphere (squared Euclidean distance =
  twice the squared Hellinger distance, a metric surrogate for the non-metric KL
  "compression" distance) and runs spherical K-means. Both methods are
  occurrence-weighted: each context contributes with weight `N_s`, and the
  sphere update is the re-normalised count-weighted mean `Σ N_s x_s` (the `kl`
  update is the pooled-count mean). The assignment steps are unaffected by the
  weighting, since the weight is a per-point constant factor.

`k` is fixed by the caller (`--k`); there is deliberately no automatic
selection. Every criterion tried (the elbow of the bits curve, the mean
silhouette, and in principle held-out compression) was either arbitrary or
merely relocated the arbitrariness — the best compromise depends on how much
pressure one feels to keep the model low-dimensional — so `k` is chosen by hand
and the `H(next | cluster)` vs `k` curve is produced by sweeping `--k` yourself.
The two clustering methods agree to within ~0.04 bits (over `k = 2..100` on the
current corpus the gap is at most 0.034 bits, mean 0.017; `kl` a hair better at
small `k`, the sphere method occasionally better at large `k`), so it does not
matter which one you run. `scripts/cluster_entropy.py` reports `H(next)`,
`H(next | substring)`, `H(next | cluster)` and the information retained.

On the current corpus (1,950 analysable contexts), `H(next) = 4.966` and
`H(next | substring) = 3.070` bits. With the `kl` objective:

| k | 12 | 22 | 100 |
|---|---|---|---|
| `H(next | cluster)` | 4.011 | 3.821 | 3.502 |

So **k is the dominant lever**: the cluster model approaches — but with 100
clusters still does not reach — the exact-context 3.070 bits. At `k = 22` the
clustering retains 1.145 bits (60% of the 1.896-bit achievable reduction); at
`k = 12` it retains 0.955 bits (50%). The earlier plain
"character after substring" count gave a less sharp context model (3.520 bits)
and retained ~49% at `k = 12`.

```sh
python3 scripts/successor_distributions.py work/camel/merged.txt work/common10000/common_substrings.txt
python3 scripts/cluster_substrings.py --outdir work/common10000 --k 22   # --method kl (default)
python3 scripts/cluster_entropy.py --outdir work/common10000
```

### Scaling up: more substrings, more clusters

Lowering the common-substring threshold to 2000 gives 11,758 common substrings
(max length 14) and 10,890 analysable successor distributions. (The numbers in
this subsection predate the longest-suffix model — they use the plain
"character after substring" count — and predate the count-weighting of the
clustering, so treat them as indicative only; `k` is now chosen by hand rather
than by silhouette.)

At a hand-picked `k = 17` the successor structure sharpens considerably: many
clusters are near-deterministic, each pinned to a single likely next character —
`t:0.96`, `o:0.95`, `e:0.94`, `r:0.94`, `l:0.94`, `d:0.93`, `a:0.91`, `g:0.91`,
`s:0.89`, `n:0.87`, `i:0.85` — plus a digit/underscore cluster
(`1:0.16 _:0.14 2:0.12 …`) and a large mixed "junk drawer". The measured
entropies are: `H(next) = 4.935`, `H(next | substring) = 3.159`,
`H(next | cluster) = 3.941` bits, so the clustering retains 0.993 bits (20.1% of
`H(next)`).

`scripts/fastkern.c` holds the two O(n·k·d) inner loops (K-means assignment,
cluster accumulation). It is compiled on demand with
`gcc -O3 -march=native -fopenmp` and loaded through `ctypes`, because the host's
BLAS is reference (netlib) BLAS (~0.2 GFLOP/s) which makes the NumPy fallback
far too slow at this size; if compilation fails the script falls back to pure
NumPy automatically.

```sh
python3 scripts/common_substrings.py work/camel/merged.txt \
        --outdir work/common2000 --threshold 2000
python3 scripts/successor_distributions.py work/camel/merged.txt \
        work/common2000/common_substrings.txt --outdir work/common2000
python3 scripts/cluster_substrings.py --outdir work/common2000 \
        --k 17 --restarts 10
python3 scripts/cluster_entropy.py --outdir work/common2000
```

## Fixed-budget compressibility and the low-rank adjacency model

`scripts/code_lengths.py` computes the ideal arithmetic-code length of each
identifier under the longest-suffix successor model — the natural estimate of
whether an identifier fits a 64-bit budget (with ~2 bits reserved for
capitalisation style). Success rates are reported both **static** (percentage of
`camel/merged` identifiers) and **dynamic** (percentage of real source-code
occurrences, from `work/occ/`). `scripts/pair_matrix.py` builds the `N x N`
prefix/suffix adjacency matrix `M` (longest common substring that is a suffix of
the left half against the longest common substring that is a prefix of the right
half) and approximates it with a rank-`L` factorisation — by default in the
square-root (Hellinger) domain, `M ~ (√M)_L²`, which is non-negative by
construction and minimises the metric that matches KL (`--no-sqrt` for the old
count-space SVD). All of these are scored by the **joint** KL
`KL(M/T ‖ M̂/ΣM̂)` (`pair_matrix.kl_joint`), which differs from the older
occurrence-weighted *conditional* KL only by a model-independent constant, so
no conditional `p(b|a)` is formed.
`scripts/latent_probabilities.py` measures ways of coping with the negative
entries that factorisation introduces, and `scripts/sqrt_and_smooth.py`
explores a better fix: factorise `√M` (the occurrence-weighted Hellinger
embedding — rooting the counts already builds in the weighting) and square the
reconstruction back, which is both non-negative by construction and ~30% lower
KL than any remedy; smoothing `M` towards the independence model is a trade of
KL for fewer latent negatives. See `docs/HELLINGER_FACTORISATION.md`.

`scripts/run_sweep.sh` runs the successor, code-length and factorisation
analyses over a list of thresholds.

```sh
python3 scripts/sample_occurrences.py --outdir work/occ --per-eco 1200 --seed 1
python3 scripts/normalise_counts.py work/occ/all.counts work/occ/all.camel.counts
sh scripts/run_sweep.sh            # successor + code_lengths + pair_matrix
```

Headline numbers (budget 64 bits / 62 bits reserved for capitalisation) across
thresholds 500–100000: the **static** success rate runs from **52% to 89%** and
the **dynamic** rate saturates near **92%**; the adjacency matrix is
low-rank for the frequent contexts but close to full-rank for the tail. The
full method, tables and the negative-entry remedies are in
[`docs/COMPRESSION_ESTIMATES.md`](docs/COMPRESSION_ESTIMATES.md).

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
