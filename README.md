# varnames — a corpus of programming-language identifiers

**Goal.** Construct a **bijection from programming-language identifiers to the
integers**, one that can be *expressed compactly* — on the order of 20 KB
**total**, counting the code *and* its tables together. A 64-bit hash function
is usable as a bijection in practice, but its *inverse* is far too large; so
instead we are trying to build a **compression algorithm** that encodes an
identifier as an integer and can recover it.

**Status.** A *feasibility study* and an *experimental statistical exploration*:
the corpus, the models and the reports below exist to test whether a compact
bijection is reachable at all. This is research, not yet a finished codec.

## The product

The goal is to provide a library to encode identifiers into integers and decode them again. Integers are much more efficient to process than strings, and more compact, so a bijective map between them would be useful. We propose to specify a portable (cross-language) standard for the encoding, and to ship implementations of it.

The library works with CamelCase identifiers, containing only letters, digits, and underscores. We ship functions to convert identifiers between different capitalisation conventions, and using those we can also encode lower_case and UPPER_CASE identifiers efficiently too. This covers the majority of programming use cases. The original capitalisation convention is not encoded; it is the caller's responsibility. The encoding is otherwise lossless.

We target two fixed budgets: 64-bit integers and 128-bit integers. Exceptionally long or rare identifiers do not fit in the budget; it is left to the caller to decide how to handle these cases. We think it would be sensible to reject them, or to encode them using a hash function and decode them using a hash map. The 64-bit budget is a little restrictive; about 10% of identifiers in the training corpus cannot be encoded, though they tend to be pretty ugly ones. The 128-bit budget is enough for almost any identifier.

Compressing long identifiers into small integers is an exercise in information theory. The bulk of the work is statistics, not programming. What you will find in this repo are the tools we used to study the statistics and to come up with a simple, compact model that can form the basis of the standard.

## The strategy

The experimental strategy is as follows:

- Build a corpus (see *TODO*)
- Case-normalise it (see *TODO*)
- Build word lists (see *TODO*)
- Measure statistics (see *TODO*)
- Cluster words with similar statistics (see *TODO*)
- Build a cheap model of the probability distributions (see *TODO*)
- Build an encoder based on the model (see *TODO*)

It is important that the model is small and efficient, otherwise nobody will want to use it. The pertinent optimisation criterion is the fraction of identifiers in the training corpus that fit in 64 bits, measured as a function of the model size. With a large model we could do much better, but that's not the point; the question is how well we can do with a small model. See *TODO* for details on the optimisation methodology.

We tried two main strategies, and found that the second one is much better:

- Rejected: Encode each character conditionally on the word that precedes it (see *TODO*).
- Adopted: Tokenise the string into words, and define a Markov model on the words (see *TODO*).

In the above, "word" means any string that is commonly used in identifiers; many are in fact English words or abbreviations but many are not.

We explored many ways of defining "word". It turns out that the list of words is the most important part of the model, and it therefore accounts for the majority of the model size. The best idea for the rejected strategy (See *TODO*) was different from the best idea for the adopted strategy (see *TODO*). For the supporting theory see *TODO*.

In both strategies, we found that there is a huge benefit from clustering words with similar statistics. This reduces the model size a lot, but worsens compression only a little. The clustering study for the rejected strategy is *TODO*, and for the adopted strategy it is *TODO*.

Along the way, we tried a lot of things that didn't work:

- *TODO*
- *TODO*
- ...

## Layout

```
varnames/
├── corpus/
│   ├── identifiers.multilang.txt        # union of all 10 ecosystems (4,441,974)
│   └── by_language/
│       ├── ruby.txt  rust.txt  ocaml.txt  haskell.txt  java.txt
│       ├── python.txt  go.txt  lua.txt  perl.txt  javascript.txt
├── PLAN.md                              # index of the research lines (+ long-term productisation horizon)
├── docs/
│   ├── CORPUS.md                        # corpus statistics + reproduction
│   ├── CASE_NORMALISATION.md            # case normalisation + common substrings
│   ├── CODE_LENGTHS.md                  # fixed-budget compressibility
│   ├── ADJACENCY_MATRIX.md              # how to build the adjacency matrix + the κ prior
│   ├── HELLINGER_FACTORISATION.md       # square-root factorisation of the word matrix
│   ├── MATRIX_COMPRESSION.md            # direct coding of the word matrix (residual + top-N)
│   ├── STRUCTURAL_ZEROS.md              # structural zeros of the word prior (negligible)
│   ├── CLUSTER_SIZE_STUDY.md            # choosing k and N for the model size
│   ├── TREE_WORDS.md                    # dictionary model + merge delta (§9.1 keeps the run theory)
│   ├── TOKENISATION.md                  # tokeniser speed: precedence vs bucket parser
│   ├── DICTIONARY_RULES.md              # building the dictionary: rule choice, Δ vs frequency
│   ├── BOUNDARY_TRIGRAM.md              # boundary words (v\n) are worth ~1% held-out
│   ├── BREAK_OPEN_PRIOR.md              # structured back-off prior; loses to P_mar
│   ├── PRUNE_WORDS.md                   # overshoot/prune the word list (unsuccessful: hurts the clustered model)
│   ├── CLUSTER_WORDS.md                 # co-cluster the word matrix to compress it
│   ├── CLUSTER_LOSS.md                  # where the co-clustering loss lives + block structure
│   ├── CODING_OVERHEAD.md               # words per identifier + Huffman vs arithmetic
│   ├── RUN_LENGTHS.md                   # typical run lengths (maximal repeated-character runs)
│   ├── WORD_COMPRESSIBILITY.md          # applying the word model: held-out 64/128-bit fit
│   ├── MODEL_BUDGET.md                  # model size in bytes, word list included
│   ├── BUDGET64_STUDY.md                # the 64-/128-bit identifier sets
│   ├── ENCODING.md                      # the encoding: stop token, published tables, cluster quarters
│   ├── SHARED_CLUSTERS.md               # one cluster assignment for both sides (adopted)
│   ├── NEWLINE_CLUSTER.md               # reserved clusters for the stop token (rejected)
│   ├── SMALL_DICT.md                    # the V=512 testing vocabulary: what it can and cannot show
│   └── PRODUCTISATION.md                # long-term: design intent, scope, audiences (draft)
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
│   ├── choose_kappa.py                  # choose the prior strength κ by held-out likelihood
│   ├── cluster_substrings_lib.py        # K-means helpers (library)
│   ├── cluster_substrings.py            # CLI: K-means on the Hellinger embedding
│   ├── cluster_entropy.py               # successor entropy (bits) per cluster
│   ├── cluster_size_frontier.py         # (model size, entropy) frontier + k/N
│   ├── symmetry_check.py                # left/right reversal-symmetry sanity check
│   ├── check_merge_delta.py             # regression test for the tree-words merge delta
│   ├── split_corpus.py                  # deterministic 9:1 train/validation split
│   ├── tree_words.py                    # dictionary (pair merge, no self-merges) + word x word adjacency model
│   ├── check_tree_words.py              # regression test for the dictionary + tokeniser
│   ├── tokenizer_bench.py               # tokeniser speed / equivalence benchmark
│   ├── hfactor_words.py                 # Hellinger factorisation + structural zeros of the word matrix
│   ├── prune_words.py                   # overshoot-and-prune the word list by removal cost
│   ├── cluster_words.py                 # K-means co-clustering of the word matrix
│   ├── cluster_loss_attribution.py      # attribute the assoc loss to cluster-pair cells
│   ├── block_structure.py               # rank/sparsity of a high-loss cluster-pair block
│   ├── matrix_compress.py               # direct compression of the word matrix (residual + top-N curve)
│   ├── factor_cloud.py                  # 3D cloud viz of the rank-4 sqrt factorisation
│   ├── shape_gain_test.py               # test the cloud "gain x shape" factorisation vs nulls
│   ├── wordlist_budget.py               # word-list size vs k^2 cluster-table budget
│   ├── words_per_identifier.py          # token-count histogram + Huffman penalty
│   ├── model_budget.py                  # model size in bytes (word list + tables)
│   ├── model_fit_rates.py               # held-out fit rates of the clustered model
│   ├── budget64_study.py                # 64/128-bit sets: coverage, boundary, generation
│   ├── case_ablation.py                 # case-normalisation ablation (paired CamelCase test)
│   ├── break_open_prior.py              # break-open prior vs P_mar on held-out data
│   ├── run_lengths.py                   # run-length statistics of the corpus
│   ├── dict_experiments.py              # dictionary rules: run words, Δ vs frequency
│   ├── boundary_trigram.py              # bits the identifier-boundary trigram (u,v,\n) is worth
│   ├── run_sweep.sh                     # run the analyses over all thresholds
│   └── run_break_open_prior.sh          # run the break-open-prior sweep
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
`clean_ids/`, `*.shards`, per-ecosystem logs) — tens of thousands of files and
several GB, none of it tracked.

**Search with `rg` or `git grep`, never a bare `grep -r`.** `grep -r` ignores
`.gitignore`, so it walks the downloads and the multi-million-line corpora (and
this checkout lives on slow storage): the same query that takes seconds with
`rg` — which skips everything ignored, `work/` included — can run for minutes.
`git grep` is the right tool when only tracked files matter.

## Repository conventions

Three house rules keep the plan and the reports from drifting apart.

**Keep plan identifiers out of reports and filenames.** `PLAN.md` labels each
thread with a short identifier (`A1`, `B1`, `C5`, …). Those labels are *local to
the plan* — the plan is a living document, and a thread can be renumbered or
re-scoped, so any report that cites "C5" goes stale the moment it does.
Experiment reports (`docs/*.md`), filenames and code therefore refer to an
experiment by a **descriptive name** ("the break-open prior", "the run-aware
dictionary"), never by its plan label. Plan identifiers appear only in
`PLAN.md`.

**`PLAN.md` is an index, not a report.** It records **execution status and
success/failure only** — one line per thread, plus a pointer to the report that
owns the detail. Design notes, derivations and experimental results do **not**
belong in `PLAN.md`; they live in the individual experiment reports, which
`PLAN.md` links to. This keeps the plan readable, and lets the reports evolve
without touching it.

**Nothing is decided at the testing vocabulary.** The pair-merge dictionary is
built at a fixed grid (`V = 4096, 6144, 8192`), and `V = 512` exists only to
exercise scripts: it builds in seconds and fits in memory, so a new harness can
be run end to end before the real one is paid for. It is **not** a small version
of the product. No accept/reject decision, no byte budget and no frontier price
may be taken from it — the frontier is priced in kB per point of fit, and that
price differs by an order of magnitude between 512 and the grid, so a scheme that
saves a fixed number of bytes is scored differently at each. Measurements at
`V = 512` are kept in [`docs/SMALL_DICT.md`](docs/SMALL_DICT.md), which carries
the same warning; the experiment reports quote only the grid.

## Licensing & provenance

Identifiers are extracted as facts from openly published package sources and locally installed open-source software. Individual packages carry their own licenses. This repository contains only the derived token lists, not the original source code.

The original work in this repo is offered under a well-known permissive licence that we hope will encourage its adoption: *TODO*.

## Contributing

We welcome contributions on [GitHub](https://github.com/apt1002/varnames) and you can email us at `varnames -at- minworks.co.uk`.
