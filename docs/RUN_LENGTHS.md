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

On the recommended union corpus (2,365,468 identifiers, 42,896,750 characters):

| quantity | value |
|---|---:|
| identifiers with ≥ 1 run | 733,300 (**31.0 %**) |
| maximal runs (`k ≥ 2`) | 902,316 (**0.381** per identifier) |
| run mass `Σ (k−1)` = adjacent `uu` pairs | 913,504 (**2.13 %** of all character adjacencies) |
| mean run length | **2.012** |
| runs of length exactly 2 | **99.0 %** of runs, **97.8 %** of the mass |
| distinct run words `(u,k)` | **220**, over **63** characters |

**The picture is stark: essentially all runs are length 2.**  Runs of three or
more are ~1.0 % of runs and ~2.2 % of the mass; runs of six or more are a
handful of generated-code curiosities.  For the dictionary this means the
run-aware rule is, in practice, "merge the doubled pair `uu`", and the
length-`k` machinery only pays off for a small set of characters.

## Run-length distribution

`#runs(k)` = maximal runs of length exactly `k`; mass = `(k−1)·#runs(k)`.

| `k` | `#runs` | % of runs | mass | % of mass |
|---:|---:|---:|---:|---:|
| 2 | 893,420 | 99.03 % | 893,420 | 97.80 % |
| 3 | 7,934 | 0.88 % | 15,868 | 1.74 % |
| 4 | 622 | 0.07 % | 1,866 | 0.20 % |
| 5 | 192 | 0.02 % | 768 | 0.08 % |
| 6 | 39 | — | 195 | 0.02 % |
| 7 | 22 | — | 132 | 0.01 % |
| 8 | 9 | — | 63 | — |
| 9 | 10 | — | 80 | — |
| 10 | 4 | — | 36 | — |
| 11 | 6 | — | 60 | — |
| 12 | 4 | — | 44 | — |
| 13 | 8 | — | 96 | — |
| 14 | 6 | — | 78 | — |
| 15 | 5 | — | 70 | — |
| 16 | 6 | — | 90 | — |
| 17 | 5 | — | 80 | — |
| 18 | 5 | — | 85 | — |
| 19 | 4 | — | 72 | — |
| 20–47 | 15 | — | 401 | 0.04 % |
| **all** | **902,316** | 100 % | **913,504** | 100 % |

The `20–47` band is 15 runs in total (lengths 20, 22, 23, 24, 25×2, 30, 31, 32,
34, 43, 47), all from generated constants such as `…0000`.

## Runs per identifier

| runs in identifier | identifiers | share |
|---:|---:|---:|
| 0 | 1,632,168 | 69.0 % |
| 1 | 593,900 | 25.1 % |
| 2 | 115,709 | 4.9 % |
| 3 | 19,324 | 0.82 % |
| 4 | 3,406 | 0.14 % |
| 5 | 709 | 0.03 % |
| 6 | 153 | — |
| 7 | 30 | — |
| 8 | 17 | — |
| 9 | 13 | — |
| 10 | 16 | — |
| 11 | 6 | — |

Almost two thirds of identifiers have no run at all; when they do, it is
usually exactly one (mean among run-bearing identifiers 1.23).

## Which characters run

The mass is dominated by the frequent letters `s l r t o p f e d m`, each a
single doubled character for the most part.  Two characters behave differently:
`_` and the digits `0`/`1` carry almost all of the **long** runs.

| char | `#runs` | mass `(k−1)` | `k=2` | `k=3` | `k=4` | `k=5` | `k≥6` | max `k` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `s` | 116,802 | 117,177 | 116,434 | 361 | 7 | 0 | 0 | 4 |
| `l` | 96,893 | 96,956 | 96,830 | 63 | 0 | 0 | 0 | 3 |
| `r` | 75,860 | 76,018 | 75,730 | 121 | 7 | 1 | 1 | 22 |
| `t` | 61,547 | 61,560 | 61,534 | 13 | 0 | 0 | 0 | 3 |
| `o` | 60,064 | 60,105 | 60,049 | 11 | 0 | 1 | 3 | 20 |
| `p` | 43,957 | 44,152 | 43,764 | 191 | 2 | 0 | 0 | 4 |
| `f` | 40,751 | 40,906 | 40,714 | 21 | 6 | 0 | 10 | 30 |
| `e` | 39,450 | 39,607 | 39,296 | 153 | 0 | 0 | 1 | 6 |
| `d` | 35,605 | 35,703 | 35,524 | 73 | 5 | 0 | 3 | 7 |
| `m` | 31,984 | 32,000 | 31,973 | 8 | 1 | 2 | 0 | 5 |
| `n` | 31,363 | 31,376 | 31,353 | 8 | 1 | 1 | 0 | 5 |
| `_` | 27,352 | **30,870** | 23,975 | 3,302 | 33 | 31 | 11 | 10 |
| `1` | 12,314 | 12,680 | 12,027 | 261 | 19 | 4 | 3 | **47** |
| `0` | 6,968 | 9,937 | 5,505 | 868 | 355 | 146 | 94 | 43 |

`_` alone supplies ~38 % of all `k ≥ 3` runs (3,377 of 8,896) despite being
only 3 % of the runs; `0` is the extreme -- its 94 runs of length `≥ 6` carry
1,047 of its 9,937 mass, against 5,505 for plain doublings -- and the digits
hold the single longest runs.  These are the doubled/underscored
conventions (`foo__bar`), separator fills (`__________`) and zero-padded
constants (`0000`) of generated or bindgen-style code.

## Longest runs (examples)

| `k` | identifier |
|---:|---|
| 47 | `a_long_function_name_11111111111111111111111111111111111111111111111` |
| 19 | `U10000000000000000000` |
| 18 | `N1000000000000000000` |
| 17 | `N100000000000000000` |
| 14 | `KEYS_000000000000001B_REFLECTED` |
| 10 | `__________` (case-normalised corpus) |

## What it means for the dictionary

* **The run-aware rule is effectively the doubled-pair rule.**  With 99.0 % of
  runs at `k = 2`, `(k−1)·#runs(k)` is dominated by the `k = 2` term for every
  character, so the crossover against the boundary word `(uv)` almost always
  reduces to `N(u,u)` vs `N(u,v)`.  Long-run words matter only for the few
  characters in the tables above.
* **The run-word budget is small and cheap.**  All 220 distinct `(u,k)` run
  words exist over the full 63-character alphabet, but the long ones are rare:
  a word list that keeps `k = 2` for the frequent letters and adds the `_` and
  digit runs captures almost the whole 913,504-pair mass.
* **Runs are a minor share of the corpus.**  Doubled adjacencies are 2.13 % of
  all character adjacencies, so run handling is a second-order effect; the
  word model's win over the character model does not rest on it.
* **Occurrence weighting could raise the long-run share.**  These counts treat
  every distinct identifier once.  A frequency-weighted view would likely
  promote the `_` runs further (`__init__`, `foo__bar`), so the true cost of
  long runs in real token streams is probably somewhat larger than 2 %.

### Robustness: the case-normalised corpus

`work/camel/merged.txt` (2,295,340 identifiers after case normalisation, the
input the word model actually uses) gives the same shape: 30.5 % of identifiers
with ≥ 1 run, 0.374 runs per identifier, run mass 865,984, mean run length
2.011, `k = 2` at 99.4 % of runs.  The only structural change is that case
folding merges some runs into `_` (e.g. an all-underscore separator becomes a
single 10-long run).
