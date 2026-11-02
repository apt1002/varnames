# Case normalisation and common substrings

The successor and adjacency models are built on a **case-normalised** copy of
the corpus, and on the set of **common substrings** of its identifiers. Both are
produced by `scripts/run_camel_pipeline.sh` (or the individual scripts) from
`corpus/identifiers.multilang.txt`.

## Case normalisation

1. **classify** — split the corpus into `lower_case` (has lower-case letters, no
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

`scripts/classify_identifiers.py` and `scripts/camelize_identifiers.py` do steps
1–2; `scripts/merge_identifiers.py` does step 3. On the current union
(2,365,468 identifiers) the merged, normalised corpus has **2,295,340**
identifiers.

The pipeline writes the case-normalisation artefacts (`lower_case.txt`,
`upper_case.txt`, `camel_case.txt`, `camel_from_lower.txt`,
`camel_from_upper.txt`, `merged.txt`) into the CamelCase directory
(`work/camel`).

## Common substrings

Every identifier is wrapped as `^identifier$`, and all substrings occurring at
least *T* times are enumerated (Apriori/BFS over length with a 64-bit rolling
hash count, in `scripts/common_substrings.py`). The empty string is common by
definition. The artefacts land in `work/common<T>`.

| T | common substrings | max length |
|---:|---:|---:|
| 100000 | 159 | 5 |
| 50000 | 316 | 5 |
| 20000 | 911 | 7 |
| 10000 | 2,102 | 9 |
| 5000 | 4,478 | 13 |
| 2000 | 11,758 | 14 |
| 1000 | 23,284 | 25 |
| 500 | 46,346 | 33 |

At the default threshold *T* = 10000 the set contains 2,102 substrings; the
longest are 9 characters (`Attribute`, `Response$`). The empty string, `^`, `$`
and all 65 single characters (`a-z`, `A-Z`, `0-9`, `_`, `^`, `$`) occur at least
10000 times.

## Running it

```sh
sh scripts/run_camel_pipeline.sh corpus/identifiers.multilang.txt work/camel
# the common substrings at a given threshold, e.g. 2000 -> work/common2000
THRESHOLD=2000 sh scripts/run_camel_pipeline.sh corpus/identifiers.multilang.txt work/camel
```

The case-normalisation artefacts always go to the CamelCase directory
(`work/camel`); the common-substring artefacts go to `work/common<THRESHOLD>`.

## Ablation: does case normalisation actually help?

Reproducing the ablation:

```sh
mkdir -p work/raw
python3 scripts/split_corpus.py corpus/identifiers.multilang.txt \
        work/raw/merged_training.txt work/raw/merged_validation.txt --every 10
python3 scripts/tree_words.py train --corpus work/raw/merged_training.txt \
        --num-pairs 2040 --sample 20 --outdir work/tw2040raw
python3 scripts/case_ablation.py work/tw2040 work/tw2040raw
```

Two corpora were built from the same raw union (`corpus/identifiers.multilang.txt`,
2,365,468 identifiers, already sorted-unique) and split 9:1 identically
(interleaved, `scripts/split_corpus.py --every 10`):

* **normalised** — `classify`/`camelize`/`merge` → `work/camel/merged.txt`, the
  existing pipeline (`merged_training` / `merged_validation`);
* **raw** — the union as-is → `work/raw/merged_training` / `merged_validation`.

The same word model is fitted to each (NUM_PAIRS = 2040, dictionary on a
stride-20 sample, adjacency on the full training corpus), and each is scored on
its own held-out set (stride 20, `kappa = 300`):

| target ids | model trained on | full table | cluster `k = 105` (`assoc`) |
|---|---|---:|---:|
| canonical (normalised split) | normalised | **45.77** | **55.35** |
| raw (raw split) | raw | 50.30 | 62.91 |

The two test sets differ, so this alone is not decisive.  The clean **paired**
test scores identifiers that normalisation leaves *unchanged* — the CamelCase
subset of the raw held-out set (3,598 of 11,828), which is the *same string* in
both corpora:

| model trained on | bits on the 3,598 CamelCase ids |
|---|---:|
| normalised | **48.01** |
| raw | 53.42 |

Training on the case-normalised corpus makes even the untouched CamelCase
identifiers **5.4 bits shorter**: normalisation consolidates the three casing
conventions (`foo_bar`, `FOO_BAR`, `fooBar`) so each word's counts — and hence the
word-bigram statistics — are estimated from more evidence.  It must be applied
consistently: a normalised-trained model scored on *raw* identifiers costs
64.62 bits (a mismatch penalty of ~14 bits), so the encoder must normalise its
input the same way the corpus was normalised.

**Caveat — reversibility costs only the class label.**  Normalisation is
**injective within a case class**: `to_camel` has an exact inverse
`from_camel(s, cls)`, and `camelize_identifiers.py --check` round-trips all
1,649,738 non-CamelCase identifiers with **0 failures** — so the original
identifier is recovered from its canonical form **plus its class**.  The two
classes (`lower`, `upper`) are the ones `to_camel` rewrites; CamelCase is the
identity.  All the "lossiness" is that the class is dropped: `merge_identifiers.py`
de-duplicates *across* the three lists, collapsing 70,128 of 2,365,468
identifiers (3.0 %).  **Every collapse is cross-class** — e.g. `_abc` (lower),
`_ABC` (upper) and `Abc` (CamelCase) all normalise to `Abc`; `_a` (lower) and
`_A` (upper) both give `A`; `_a_id` (lower) and `AId` (CamelCase) both give
`AId` — and the class label disambiguates them.  So exact recovery needs only
the class kept alongside the token stream (≈1.6 bits), not the original spelling.
If the target is the canonical form alone (the assumption throughout this
repository), even that is unnecessary.
