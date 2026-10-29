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
