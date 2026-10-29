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
| `corpus/by_language/*.txt` | — | Per-ecosystem lists: `ruby`, `rust`, `python`, `go`, `javascript`, `perl`. |

Statistics and full reproduction instructions: [`docs/CORPUS.md`](docs/CORPUS.md).
(The old Ruby-only `corpus/identifiers.txt` was byte-identical with
`by_language/ruby.txt`, and the length-capped `*.max128.*` variants were never
used; all three have been removed.)

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

How each ecosystem was harvested, the lexing rules, and what the corpus
does and does not contain are documented in [`docs/CORPUS.md`](docs/CORPUS.md).

## Layout

```
varnames/
├── corpus/
│   ├── identifiers.multilang.txt        # union of all 6 ecosystems (2,365,468)
│   └── by_language/
│       ├── ruby.txt  rust.txt  python.txt  go.txt  javascript.txt  perl.txt
├── docs/
│   ├── CORPUS.md                        # corpus statistics + reproduction
│   ├── CASE_NORMALISATION.md            # case normalisation + common substrings
│   ├── CODE_LENGTHS.md                  # fixed-budget compressibility
│   ├── ADJACENCY_MODEL.md               # low-rank prefix/suffix adjacency model
│   ├── HELLINGER_FACTORISATION.md       # square-root factorisation + unobserved-pairs prior
│   └── CLUSTER_SIZE_STUDY.md            # choosing k and N for the model size
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
│   ├── winhash.py                       # 64-bit rolling-hash helpers (library)
│   ├── successor_distributions.py       # P(next character | common substring)
│   ├── code_lengths.py                  # ideal code length + 64/128-bit fit rates
│   ├── pair_matrix_lib.py               # adjacency M + SVD/NMF helpers (library)
│   ├── pair_matrix.py                   # CLI: build adjacency M + low-rank factors
│   ├── latent_probabilities.py          # negative-entry remedies, scored by KL
│   ├── sqrt_and_smooth.py               # Hellinger (sqrt) factorisation + unobserved-pairs prior
│   ├── choose_c.py                      # choose the prior strength c by held-out likelihood
│   ├── rank1_marginals.py               # rank-1 SVD vs the independence model
│   ├── cluster_substrings_lib.py        # K-means helpers (library)
│   ├── cluster_substrings.py            # CLI: K-means on the Hellinger embedding
│   ├── cluster_entropy.py               # successor entropy (bits) per cluster
│   ├── cluster_size_frontier.py         # (model size, entropy) frontier + k/N
│   ├── symmetry_check.py                # left/right reversal-symmetry sanity check
│   └── run_sweep.sh                     # run the analyses over all thresholds
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
```

`work/` also holds the corpus-build intermediates (`gems_dl/`, `*_src/`,
`clean_ids/`, `*.shards`, per-ecosystem logs).

## CamelCase normalisation and common substrings

The successor and adjacency models are built on a **case-normalised** copy of
the corpus and on its **common substrings**. `scripts/run_camel_pipeline.sh`
derives both from `corpus/identifiers.multilang.txt` in four steps — classify,
camelize, merge, and enumerate the substrings occurring at least *T* times.
On the current union (2,365,468 identifiers → 2,295,340 after normalisation and
de-duplication) the common-substring set grows quickly as the threshold falls:

| threshold T | common substrings | max length |
|---:|---:|---:|
| 100000 | 159 | 5 |
| 10000 | 2,102 | 9 |
| 2000 | 11,758 | 14 |
| 500 | 46,346 | 33 |

The empty string, `^`, `$` and all 65 single characters (`a-z`, `A-Z`, `0-9`,
`_`, `^`, `$`) are common at every threshold. Full details, the exact
CamelCase rules and the complete threshold table are in
[`docs/CASE_NORMALISATION.md`](docs/CASE_NORMALISATION.md).

```sh
sh scripts/run_camel_pipeline.sh corpus/identifiers.multilang.txt work/camel
# a non-default threshold: THRESHOLD=2000 produces work/common2000
```

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
current corpus the gap is at most 0.035 bits, mean 0.015; `kl` is a hair better
at small `k` (up to ~30), the sphere method a hair better at large `k`), so it
does not matter which one you run. At threshold 2000 (10,890 contexts, `k`
sampled on a coarse grid) the gap is at most 0.052 bits, mean 0.019.
`scripts/cluster_entropy.py` reports `H(next)`,
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
(max length 14) and 10,890 analysable successor distributions. (`k` is chosen by
hand rather than by silhouette.)

At a hand-picked `k = 17` the successor structure sharpens considerably: many
clusters are near-deterministic, each pinned to a single likely next character,
plus a digit/underscore cluster and a large mixed "junk drawer". The measured
entropies are: `H(next) = 4.966`, `H(next | substring) = 2.611`,
`H(next | cluster) = 3.547` bits, so the clustering retains 1.419 bits
(28.6% of `H(next)`).

The clustering runs on plain NumPy matmuls; with a tuned BLAS (e.g. OpenBLAS:
`apt install libopenblas0-pthread`, which registers the `libblas.so.3` /
`liblapack.so.3` alternatives) these are fast at this size, so no compiled
kernel is needed. (An earlier OpenMP kernel, `fastkern.c`, was removed once
OpenBLAS became a standing requirement; it remains in the git history.)

```sh
python3 scripts/common_substrings.py work/camel/merged.txt \
        --outdir work/common2000 --threshold 2000
python3 scripts/successor_distributions.py work/camel/merged.txt \
        work/common2000/common_substrings.txt --outdir work/common2000
python3 scripts/cluster_substrings.py --outdir work/common2000 \
        --k 17 --restarts 10
python3 scripts/cluster_entropy.py --outdir work/common2000
```

## Fixed-budget compressibility

`scripts/code_lengths.py` computes the ideal arithmetic-code length of each
identifier under the longest-suffix successor model. It is the natural estimate
of whether an identifier fits a fixed budget (64 or 128 bits; no separate
capitalisation allowance is charged here). Scoring is on the `camel/merged`
identifiers — a **static** success rate. The method, the full threshold table,
and the finding that **the 64-bit threshold accounted for about 92% of
identifier occurrences in real source code, a proportion relatively insensitive
to improvements in compression**, are in
[`docs/CODE_LENGTHS.md`](docs/CODE_LENGTHS.md). The occurrence-weighted study
that produced that 92% figure has been retired (it is easy to reproduce if the
exact curve is ever wanted), but the qualitative result stands.

Headline: the static 64-bit success rate runs from **52% to 89%** across
thresholds 500–100000 (and 93%–99% at 128 bits).

## The low-rank prefix/suffix adjacency model

`scripts/pair_matrix.py` builds the `N x N` prefix/suffix adjacency matrix `M`
(longest common substring that is a suffix of the left half against the longest
common substring that is a prefix of the right half) and approximates it with a
rank-`L` factorisation — by default in the square-root (Hellinger) domain,
`M ~ (√M)_L²`, which is non-negative by construction and minimises the metric
that matches KL (`--no-sqrt` for the old count-space SVD). All of these are
scored by the **joint** KL `KL(M/T ‖ M̂/ΣM̂)` (`pair_matrix_lib.kl_joint`), which
differs from the older occurrence-weighted *conditional* KL only by a
model-independent constant, so no conditional `p(b|a)` is formed.
`scripts/latent_probabilities.py` measures ways of coping with the negative
entries that factorisation introduces, and `scripts/sqrt_and_smooth.py`
explores a better fix: factorise `√M` (the occurrence-weighted Hellinger
embedding — rooting the counts already builds in the weighting) and square the
reconstruction back, which is both non-negative by construction and ~30% lower
KL than any remedy. It also studies a *counting* fix for unobserved pairs — an
independence-shaped prior of fixed mass (`M + c·N²·P_mar`) added to the
reference matrix — in `docs/HELLINGER_FACTORISATION.md`.

The adjacency matrix is low-rank for the frequent contexts but close to
full-rank for the tail. The model, the rank-1 comparison, the reversal-symmetry
check and the negative-entry remedies are in
[`docs/ADJACENCY_MODEL.md`](docs/ADJACENCY_MODEL.md); the square-root
factorisation and the unobserved-pairs prior are in
[`docs/HELLINGER_FACTORISATION.md`](docs/HELLINGER_FACTORISATION.md).

`scripts/run_sweep.sh` runs the successor, code-length and factorisation
analyses over a list of thresholds:

```sh
sh scripts/run_sweep.sh            # successor + code_lengths + pair_matrix
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
