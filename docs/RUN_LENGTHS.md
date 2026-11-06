# Typical run lengths in identifiers

A **run** is a maximal block of one repeated character inside an identifier —
the `oo` of `book`, the `---` of `a---b`.  A block of length 1 is just a
character with no equal neighbour and is *not* counted.  Runs matter because
the drain on a dictionary is the doubled pair `uu`: the run-aware rule
(`TREE_WORDS.md` §9.1, `DICTIONARY_RULES.md`) spends **one word per observed
length** `(u^k)`, and its selection heuristic counts `(k−1)·#runs(k)` against
`N(u,v)`.  This note measures how big those quantities actually are.

Reproduce with

    python3 scripts/run_lengths.py                 # corpus/identifiers.multilang.txt
    python3 scripts/run_lengths.py --top 200
    python3 scripts/run_lengths.py work/camel/merged.txt

Counts are over **distinct** identifiers (the corpus carries no occurrence
weight), so they are *not* weighted by how often an identifier appears in real
source — a run inside a very common name (e.g. `__init__`) counts once.

## Summary

On the recommended union corpus (4,441,974 identifiers, 75,462,935 characters):

| quantity | value |
|---|---:|
| identifiers with ≥ 1 run | 1,314,943 (**29.6 %**) |
| maximal runs (`k ≥ 2`) | 1,602,937 (**0.361** per identifier) |
| run mass `Σ (k−1)` = adjacent `uu` pairs | 1,634,608 (**2.17 %** of all character adjacencies) |
| mean run length | **2.020** |
| runs of length exactly 2 | **99.0 %** of runs, **97.1 %** of the mass |
| distinct run words `(u,k)` | **666**, over **63** characters |

**The picture is still stark: essentially all runs are length 2.**  Runs of three
or more are 1.0 % of runs and 2.9 % of the mass, and the tail is concentrated
rather than scattered — 41 % of the `k ≥ 3` runs are underscores.  For the
dictionary this means the run-aware rule is, in practice, "merge the doubled
pair `uu`", and the length-`k` machinery only pays off for a small set of
characters.

The count of distinct run words has risen from 220 to **666** (still over the
same 63 characters) with the four new ecosystems: Haskell, OCaml and Java
generated names contain long separator and padding runs, so more distinct
`(u,k)` pairs exist.  They are almost all rare; the mass they carry is in the
`_` and `0` rows below.

## Run-length distribution

`#runs(k)` = maximal runs of length exactly `k`; mass = `(k−1)·#runs(k)`.

| `k` | `#runs` | % of runs | mass | % of mass |
|---:|---:|---:|---:|---:|
| 2 | 1,587,060 | 99.01 % | 1,587,060 | 97.09 % |
| 3 | 13,517 | 0.84 % | 27,034 | 1.65 % |
| 4 | 1,138 | 0.07 % | 3,414 | 0.21 % |
| 5 | 404 | 0.03 % | 1,616 | 0.10 % |
| 6 | 113 | 0.01 % | 565 | 0.03 % |
| 7 | 59 | 0.00 % | 354 | 0.02 % |
| 8 | 44 | 0.00 % | 308 | 0.02 % |
| 9 | 37 | 0.00 % | 296 | 0.02 % |
| 10 | 41 | 0.00 % | 369 | 0.02 % |
| 11 | 24 | 0.00 % | 240 | 0.01 % |
| 12 | 33 | 0.00 % | 363 | 0.02 % |
| 13 | 33 | 0.00 % | 396 | 0.02 % |
| 14 | 29 | 0.00 % | 377 | 0.02 % |
| 15 | 33 | 0.00 % | 462 | 0.03 % |
| 16 | 25 | 0.00 % | 375 | 0.02 % |
| 17 | 18 | 0.00 % | 288 | 0.02 % |
| 18 | 22 | 0.00 % | 374 | 0.02 % |
| 19 | 19 | 0.00 % | 342 | 0.02 % |
| 20 | 22 | 0.00 % | 418 | 0.03 % |
| 21–101 | 266 | 0.02 % | 9,957 | 0.61 % |
| **all** | **1,602,937** | 100 % | **1,634,608** | 100 % |

## Runs per identifier

| runs in identifier | identifiers | share |
|---:|---:|---:|
| 0 | 3,127,031 | 70.40 % |
| 1 | 1,078,373 | 24.28 % |
| 2 | 196,597 | 4.43 % |
| 3 | 31,421 | 0.71 % |
| 4 | 6,712 | 0.15 % |
| 5 | 1,396 | 0.03 % |
| 6 | 284 | 0.01 % |
| 7 | 64 | 0.00 % |
| 8 | 23 | 0.00 % |
| 9 | 14 | 0.00 % |
| 10 | 29 | 0.00 % |
| 11 | 6 | 0.00 % |
| 12+ | 24 | 0.001 % |

Seven in ten identifiers have no run at all; when they do, it is usually exactly
one (mean among run-bearing identifiers 1.22).

## Which characters run

The mass is dominated by the frequent letters `s l r t o p e f d n m`, each a
single doubled character for the most part.  Three characters behave
differently: `_` and the digits carry almost all of the **long** runs.

| char | `#runs` | mass `(k−1)` | `k=2` | `k=3` | `k=4` | `k=5` | `k≥6` | max `k` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `s` | 219,769 | 220,233 | 219,323 | 435 | 9 | 1 | 1 | 10 |
| `l` | 176,354 | 176,462 | 176,255 | 97 | 1 | 0 | 1 | 11 |
| `r` | 129,497 | 129,731 | 129,350 | 134 | 10 | 1 | 2 | 59 |
| `t` | 114,290 | 114,529 | 114,241 | 42 | 0 | 0 | 7 | 90 |
| `o` | 102,993 | 106,374 | 102,816 | 31 | 9 | 12 | 125 | 101 |
| `p` | 94,127 | 94,378 | 93,902 | 218 | 4 | 1 | 2 | 20 |
| `_` | 65,842 | 74,861 | 59,356 | 6,170 | 148 | 46 | 122 | 79 |
| `e` | 71,791 | 72,336 | 71,533 | 241 | 1 | 0 | 16 | 44 |
| `f` | 71,336 | 71,967 | 71,209 | 52 | 26 | 9 | 40 | 35 |
| `d` | 69,017 | 69,541 | 68,888 | 100 | 8 | 0 | 21 | 63 |
| `n` | 59,758 | 59,882 | 59,735 | 16 | 2 | 1 | 4 | 46 |
| `m` | 57,652 | 57,713 | 57,615 | 32 | 2 | 2 | 1 | 21 |

The three characters that are not ordinary letters:

| char | `#runs` | mass `(k−1)` | `k=2` | `k=3` | `k=4` | `k=5` | `k≥6` | max `k` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `_` | 65,842 | 74,861 | 59,356 | 6,170 | 148 | 46 | 122 | 79 |
| `1` | 16,576 | 17,243 | 16,038 | 481 | 40 | 9 | 8 | 47 |
| `0` | 10,080 | 13,968 | 8,182 | 1,152 | 434 | 171 | 141 | 43 |

`_` supplies **40.9 % of all `k ≥ 3` runs** (6,486 of
15,877) while being 4.1 % of all runs; `0` is the extreme — its 141 runs
of length `≥ 6` carry 1,496 of its 13,968 mass, against 8,182 for plain
doublings.  These are the doubled/underscored conventions (`foo__bar`),
separator fills (`__________`) and zero-padded constants (`0000`) of generated
or bindgen-style code.  The *longest* runs are mostly not from them either: of
the twelve longest, nine are joke identifiers of one repeated letter (`o` at
101, `t` at 90, `I` at 85, `z` at 85, `x` at 81, …) and two are separator fills
(`a` followed by 79 underscores, `T` followed by 73); only the last is mixed
plausibly-typed padding (`IIII…CCIIICBBBBB`).

## Longest runs (examples)

| `k` | identifier |
|---:|---|
| 101 | `looooo…oong` (one `o` run of 101) |
| 90 | `tttt…tttt` (one `t` run of 90) |
| 87 | `looooo…oong` (a second joke name, 87 `o`) |
| 85 | `IIII…IIII` (85 `I`), `zzzz…zzzz` (85 `z`) |
| 81 | `xxxx…xxxx` (81 `x`) |
| 79 | `a` + 79 `_` |
| 76 | `IIII…CCIIICBBBBB` (mixed padding, 76 `I`) |
| 74 | `Foooo…oooo` (74 `o`) |
| 73 | `Ccccc…cccc` (73 `c`), `T` + 73 `_`, `xxxx…xxx` (73 `x`) |
| 47 | `a_long_function_name_11111111111111111111111111111111111111111111111` |
| 19 | `U10000000000000000000` |
| 18 | `N1000000000000000000` |
| 14 | `KEYS_000000000000001B_REFLECTED` |
| 10 | `__________` (commonest in the case-normalised corpus: 78 identifiers) |

## Word-level runs (repeated *words*, not characters)

The run-aware rule collapses runs of any token, so the natural follow-up:
do adjacent equal **multi-character words** ever appear?  Yes, but rarely.
`scripts/word_runs.py` tokenises a held-out corpus with a dictionary and counts
maximal blocks of one repeated *word*.

    python3 scripts/word_runs.py work/tw4096ns work/camel/merged_validation.txt

On the current held-out set (`merged_validation.txt`, 422,671 identifiers,
V = 4096, no-run rule; the same text has 151,188 raw character runs):

| repeated word kind | word-level runs | mass `(k−1)` | run-length histogram |
|---|---:|---:|---|
| pair word | **853** | **963** | `2:798, 3:32, 4:12, 5:6, 8:2, 9:2, 12:1` |

That is **0.56 % of the character runs** — one repeated multi-character word
per 495 identifiers — and it is almost always just a doubled pair word, so the
same handful of generated names supply nearly all of it:

    AliasAliasAppearsInFromClauseSameTable     AwsS3BucketBucketLifecycleConfiguration…
    AppsPeopleOz…EmailCertificateCertificateStatus   AuthProviderFactoryFactory
    AwsBackupBackupPlanLifecycleDetails        BigQueryQueryHelper

The `20` in `BT2020NonConstantLuminance` is the one non-word example: tokenising
across the digit boundary produces the same token twice (`2`,`0`,`2`,`0` →
`20`,`20`).

The current dictionaries contain **no run words at all**: every rule in
`work/tw4096ns/dict.txt` is a `P` (pair-merge) rule over two stored symbols, so
the `(u^k)` machinery of the run-aware rule is absent and a doubled token is
always coded as two pair words.  The measurement above says that is close to
free — the loss is bounded by 853 merge opportunities in 422,671 identifiers —
which is consistent with the run-aware rule having been dropped in favour of the
no-run rule (`DICTIONARY_RULES.md`).

*(Historical record: 434 (`tw96`), 973 (`tw512`) and 409 (`tw2040`) word-level
runs on the pre-expansion held-out set of 229,534 identifiers, for the run-aware
dictionaries of the time.  Those dictionaries predate the split and the current
loader rejects them; the numbers are kept only to show what the run rule was
buying then.  The rebuild at the canonical grid has no run words to measure.)*

So a repeated multi-character word occurs about once per 500 identifiers on the
current corpus (0.20 % of identifiers; the pre-expansion dictionaries gave once
per 500–2 000) — one to two orders of magnitude rarer than a character run — and
almost always as a repeated *pair* word.  The old run-word artefacts were
greedy longest-match decompositions of a very long character run, not real word
repeats: the 47-long `1` run in `a_long_function_name_111…111` decomposed as
fifteen copies of `(1^3)` plus one `(1^2)`, and ten underscores as
`(_^4)(_^4)(_^2)`.
