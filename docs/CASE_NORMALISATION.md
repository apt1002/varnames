# Case normalisation and common substrings

The successor and adjacency models are built on a **case-normalised** copy of
the corpus, and on the set of **common substrings** of its identifiers. Both are
produced by `scripts/run_camel_pipeline.sh` (or the individual scripts) from
`corpus/identifiers.multilang.txt`.

## Case normalisation

1. **classify** — split the corpus into `lower_case` (has cased characters, none
   upper-case), `UPPER_CASE` (upper-case, no lower-case) and `CamelCase` (both).
2. **camelize** — rewrite the non-CamelCase lists in CamelCase: a cased
   character immediately preceded by an underscore is upper-cased and all other
   cased characters, including the leading letter of the identifier, are
   lower-cased, so `a`, `_a` and `__a` stay distinct (`a`, `A`, `_A`); a run of
   underscores before a cased character gives up exactly one underscore (its
   word separator) and keeps the rest, so `a_b` → `aB` but `a__b` → `a_B`
   (underscores before a digit, before an inert character, or at the end, are
   kept as-is).
3. **merge** — concatenate the CamelCase list with the two converted lists and
   de-duplicate (`LC_ALL=C sort -u`).

`scripts/classify_identifiers.py` and `scripts/camelize_identifiers.py` do steps
1–2; `scripts/merge_identifiers.py` does step 3. On the current union
(4,441,974 identifiers) the three classes are **1,976,554** lower_case,
**451,766** UPPER_CASE and **2,013,654** CamelCase, and the merged, normalised
corpus has **4,226,707** identifiers — 215,267 collapsed (4.85%) where two
classes normalise to the same string.

**Which characters are cased.**  `STANDARD.md` §11 defines the set: the ASCII
letters, and the letters of `U+00C0–U+017F` and `U+0400–U+052F` that have a 1:1
upper/lower pair — 266 pairs, published as `standard/case-pairs.txt`.  Every
other character is **inert**: copied through unchanged and never mapped, so
Greek, Han, kana and the rest pass through, and a script without case keeps its
underscores because a capital letter is the transform's only word-boundary
signal.  `python/varnames/case.py` is the one implementation; both scripts
import it, so the builder and the library cannot drift.

The shipped corpus is ASCII — 0 of 4,441,974 identifiers contain a non-ASCII
character — so the extended set changes none of the artefacts: the two
`camel_from_*` files are byte-identical either way.  What it changes is a corpus
that has accented capitals, where the old ASCII-only classifier left the
leading letter alone: `ÄRGER` used to come out `Ärger` and never meet `ärger`,
which defeats the merge this pipeline exists to perform.  It now comes out
`ärger`.

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
| 100000 | 278 | 5 |
| 50000 | 613 | 6 |
| 20000 | 1,788 | 9 |
| 10000 | 3,935 | 13 |
| 5000 | 8,038 | 14 |
| 2000 | 20,198 | 15 |
| 1000 | 40,168 | 30 |
| 500 | 80,869 | 44 |

Rows count the empty string. At the default threshold *T* = 10000 the set
contains 3,935 substrings; the longest are 13 characters (`Configuration`). The
empty string, `^`, `$` and all 65 single characters (`a-z`, `A-Z`, `0-9`, `_`,
`^`, `$`) occur at least 10000 times. Below *T* = 2000 the maximum length is set
by padding runs of generated code (`ooo…o`), not by any shared word.

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
        --num-pairs 4032 --sample 20 --stride 0 --outdir work/tw4096raw
python3 scripts/case_ablation.py work/tw4096ns work/tw4096raw
```

Two corpora were built from the same raw union (`corpus/identifiers.multilang.txt`,
4,441,974 identifiers, already sorted-unique) and split 9:1 identically
(interleaved, `scripts/split_corpus.py --every 10`: 3,997,776 training /
444,198 validation):

* **normalised** — `classify`/`camelize`/`merge` → `work/camel/merged.txt`, the
  existing pipeline (`merged_training` / `merged_validation`);
* **raw** — the union as-is → `work/raw/merged_training` / `merged_validation`.

The same word model is fitted to each (V = 4096, dictionary on a stride-20
sample, adjacency on the full training corpus), and each is scored on its own
held-out set (stride 40, `kappa = 300`):

| target ids | model trained on | full table | cluster `k = 32` (`assoc`) |
|---|---|---:|---:|
| canonical (normalised split) | normalised | **42.20** | **51.36** |
| raw (raw split) | raw | 45.36 | 57.74 |

The two test sets differ, so this alone is not decisive.  The clean **paired**
test scores identifiers that normalisation leaves *unchanged* — the CamelCase
subset of the raw held-out set (10,117 of 22,210 at stride 20), which is the
*same string* in both corpora:

| model trained on | bits on the 10,117 CamelCase ids |
|---|---:|
| normalised | **41.83** |
| raw | 45.37 |

Training on the case-normalised corpus makes even the untouched CamelCase
identifiers **3.5 bits shorter**: normalisation consolidates the three casing
conventions (`foo_bar`, `FOO_BAR`, `fooBar`) so each word's counts — and hence
the word-bigram statistics — are estimated from more evidence.  It must be applied
consistently: a normalised-trained model scored on *raw* identifiers costs
52.84 bits against the raw model's 45.12 on the same identifiers (a mismatch
penalty of 7.7 bits), so the encoder must normalise its input the same way the
corpus was normalised.

**Caveat — reversibility costs only the class label.**  Normalisation is
**injective within a case class**: `to_camel` has an exact inverse
`from_camel(s, cls)`, and `camelize_identifiers.py --check` round-trips all
2,428,320 non-CamelCase identifiers with **0 failures** — so the original
identifier is recovered from its canonical form **plus its class**.  The two
classes (`lower`, `upper`) are the ones `to_camel` rewrites; CamelCase is the
identity.  All the "lossiness" is that the class is dropped: `merge_identifiers.py`
de-duplicates *across* the three lists, collapsing 215,267 of 4,441,974
identifiers (4.85 %).  **Every collapse is cross-class** — e.g. `_abc` (lower),
`_ABC` (upper) and `Abc` (CamelCase) all normalise to `Abc`; `_a` (lower) and
`_A` (upper) both give `A`; `_a_id` (lower) and `AId` (CamelCase) both give
`AId` — and the class label disambiguates them.  So exact recovery needs only
the class kept alongside the token stream (≈1.6 bits), not the original spelling.
If the target is the canonical form alone (the assumption throughout this
repository), even that is unnecessary.
