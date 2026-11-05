# The 64-bit and 128-bit identifier sets

Status: **results.**  What fraction of real identifiers the fixed budgets cover,
where the boundary lies in *character* length, and what a random member of the
set looks like — measured on models that actually fit the byte budget
([`MODEL_BUDGET.md`](MODEL_BUDGET.md)), not on the full table.

## Setup

`scripts/budget64_study.py`.  Three vocabularies, each at the `k` that is
nearest-optimal for its byte budget (16.7 / 43.0 / 84.7 kB respectively),
`kappa = 300`, held-out validation at stride 10 (`n = 22,954` distinct
identifiers).  The `assoc` transition is evaluated from the stored numbers
`(c, D)`; sampling needs only the `k` distinct left-cluster rows.

## 1. Coverage

| model | size | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|
| `V = 2,104`, full table | 4.2 MB | 45.61 | 85.3 % | 99.2 % |
| `V = 2,104`, `k = 52` | 16.7 kB | 56.37 | 71.3 % | 97.1 % |
| `V = 2,104`, `k = 105` | 24.8 kB | 55.14 | 72.6 % | 97.4 % |
| `V = 4,478`, full table | 19.1 MB | 42.05 | 89.9 % | 99.6 % |
| `V = 4,478`, `k = 105` | 43.0 kB | 50.78 | 77.8 % | 98.3 % |
| `V = 11,758`, full table | 131.8 MB | 39.07 | 93.8 % | 99.8 % |
| `V = 11,758`, `k = 52` | 84.7 kB | 46.90 | 83.2 % | 99.0 % |

The 64-bit set is the discriminating one; 128 bits is essentially "everything
except the generated long tail".  Clustering costs far more 64-bit coverage than
it costs mean bits — 14.0 points at `V = 2,104`, 12.1 at `4,478`, 10.6 at
`11,758`, against ~1 bit of mean — so the budget question is really a
64-bit-coverage question, and the penalty *shrinks* as the vocabulary grows.

The occurrence-weighted view is not measured here (the source-code occurrence
sampler was retired, see [`CODE_LENGTHS.md`](CODE_LENGTHS.md)); that earlier
study found the 64-bit threshold covered ~92 % of identifier *occurrences* and
was insensitive to model sharpening, because occurrences are dominated by
short, predictable names.  The static rates above are the pessimistic end.

## 2. The boundary in uncompressed length

Code length is **not** monotone in character length, so there is no clean length
cut — only an overlap that *widens* with the vocabulary:

| model | longest that fits | shortest that fails | failures inside the range |
|---|---:|---:|---:|
| `V = 2,104`, `k = 52` | 42 chars | 8 chars | 6,027 of ~6,590 (91 %) |
| `V = 4,478`, `k = 105` | 50 chars | 8 chars | 4,829 of ~5,100 (95 %) |
| `V = 11,758`, `k = 52` | 57 chars | 9 chars | 3,721 of ~3,860 (96 %) |

Fit rate by character length (`V = 4,478`, `k = 105`):

| len | n | fit ≤64 | | len | n | fit ≤64 |
---:|---:|---:|---|---:|---:|---:|
| 1–7 | 2,305 | 100.0 % | | 20 | 737 | 68.7 % |
| 8 | 964 | 99.9 % | | 24 | 464 | 53.9 % |
| 10 | 1,278 | 98.3 % | | 28 | 302 | 36.1 % |
| 12 | 1,368 | 95.9 % | | 32 | 176 | 19.3 % |
| 14 | 1,376 | 92.8 % | | 36 | 112 | 7.1 % |
| 16 | 1,173 | 87.0 % | | 40 | 53 | 5.7 % |
| 18 | 888 | 80.6 % | | 44+ | ~600 | ≲2 % |

The two ends of the overlap, in full — the longest compressed sizes that fit,
and the shortest uncompressed sizes that do not:

| model | longest fitting | shortest failing |
|---|---|---|
| `V = 2,104`, `k = 105` | `viewFunctionsWithMetadataChange` 31 ch, 63.97 b; `FsrmEventType_Information` 25, 63.97; `V128Load32Lane` 14, 63.98; `DW_OP_nop` 9, 63.99 | `VfsgnjVV` 8 ch, 67.63 b; `op_UNPKU` 8, 64.49; `RADIX_u32` 9, 65.73 |
| `V = 4,478`, `k = 105` | `testNameShouldContainArgumentName` 33 ch, 63.99 b; `AuthorizePrivilegesResponse` 27, 64.00; `HalDisplayNoBios` 16, 63.99; `test_N5_Max_P2` 14, 63.99 | `VfsgnjVV` 8 ch, 64.98 b; `RADIX_u32` 9, 68.90; `jifmkJpg5` 9, 70.83; `FT_F26Dot6` 10, 66.74 |
| `V = 11,758`, `k = 52` | `IncreaseDecreaseInDueFromEmployeeCurrent` **40 ch**, 63.99 b; `SendPasswordInitializationEmailTo` 33, 63.94; `SSL_CTX_remove_session` 22, 64.00; `amazonFireTv` 12, 63.95 | `adxtCdyt0` 9 ch, 68.15 b; `rbuggyQSA` 9, 71.56; `t_NEWLINE` 9, 65.36; `_AeabiF2iz` 10, 72.71 |

A 40-character identifier can fit while a 9-character one fails, and the short
failure misses by up to nine bits — it is a genuinely unpredictable name, not a
rounding error at the boundary.  The vocabulary also *heals the short end*:
`VfsgnjVV` fails at `V = 2,104` and `4,478` but at `V = 11,758` **every**
8-character identifier fits (the length-8 row is 100 %).  It moves the top of
the range much faster than the bottom — 42 → 57 characters fitting against 8 → 9
characters failing — so a bigger vocabulary *widens* the overlap rather than
sharpening the cut.

**The encoder cannot decide from the length** — it must encode and test.  A
"short names always fit" rule holds only up to 7 characters; past that an
unpredictable 9-character name fails while a predictable 40-character one
succeeds.

## 3. A generative view

50,000 identifiers drawn from the model (a cycle from the stop token back to
it):

| model | mean len (corpus 16.97) | valid syntax | real identifier | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|---:|---:|
| `V = 2,104`, `k = 52` | 17.03 | 98.9 % | 1.64 % | 56.81 (56.37) | 68.2 % (71.3) | 92.0 % (97.1) |
| `V = 4,478`, `k = 105` | 17.06 | 97.7 % | 1.81 % | 52.01 (50.78) | 72.1 % (77.8) | 94.3 % (98.3) |
| `V = 11,758`, `k = 52` | 16.99 | 94.2 % | 1.96 % | 47.72 (46.90) | 75.2 % (83.2) | 95.3 % (99.0) |

(bracketed values are the corpus's own, for comparison.)  Examples at
`V = 4,478`: `proWhere`, `setup`, `testToStart`, `puclence_with_lookup_21`,
`SetCompilingStackType`.  At `V = 11,758` the samples begin to come apart —
`ativeacontrolTestclearLegalelase`, a blank string, `Email` — which is the
94.2 % validity above made visible.

Three things show up consistently:

* **The model reproduces the identifier *shape* almost exactly** — the length
  distribution matches the corpus to a tenth of a character.
* **Almost none of it is real.** Only ~2 % of samples are an actual identifier
  in the reference set, so the residual mass of the bijection lands on
  plausible-looking but unreal names.
* **The generative tail is heavier than the empirical one, and increasingly
  so.**  A sample's own coverage is *below* the corpus's, and the gap widens
  with the vocabulary: 64-bit 68.2 → 72.1 → 75.2 % against 71.3 → 77.8 →
  83.2 %; 128-bit 92.0 → 94.3 → 95.3 % against 97.1 → 98.3 → 99.0 %.  At
  `V = 11,758` the model's samples also stop being reliably well-formed
  (94.2 % parse, down from 98.9 %) — a big vocabulary admits low-frequency
  tokens that produce empty strings and bad starts.  So the *tail* of the
  64-bit set behaves noticeably worse than the average real identifier, and a
  bigger word list buys coverage at the cost of a noisier generation.

## What it shows

* The 64-bit set covers 71 % of distinct identifiers at 17 kB, 78 % at 43 kB,
  83 % at 85 kB; the 128-bit set ~97–99 %.  Whether that is *useful* depends on
  the occurrence weighting (retired finding: ~92 % of occurrences) and on how
  much model size the standard is willing to carry — note the 83 % figure needs
  85 kB, not 50 kB ([`MODEL_BUDGET.md`](MODEL_BUDGET.md)).
* Membership is not a length rule: failures are unpredictable identifiers of
  ordinary length, and a bigger vocabulary widens the length overlap.
* Sampling is a cheap check on the *decoder*: the model gets the shape right and
  the tail wrong, so the two ends of the set behave differently.

## Reproducing

```
python3 scripts/budget64_study.py --dir work/tw2040  --ks 52,105 --stride 10
python3 scripts/budget64_study.py --dir work/tw4414  --ks 105    --stride 10
python3 scripts/budget64_study.py --dir work/tw11694 --ks 52     --stride 10
```
