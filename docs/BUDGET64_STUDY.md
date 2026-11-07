# The 64-bit and 128-bit identifier sets

Status: **results (grid).**  What fraction of real identifiers the fixed budgets
cover, where the boundary lies in *character* length, what kind of identifier
fails, and what a random member of the set looks like — measured on models that
actually fit the byte budget ([`MODEL_BUDGET.md`](MODEL_BUDGET.md)), not on the
full table.

## Setup

`scripts/budget64_study.py`.  Three configurations, at the `k` that is
nearest-optimal for each vocabulary's byte budget (22.0 / 29.9 / 39.8 kB from
[`MODEL_BUDGET.md`](MODEL_BUDGET.md)), `kappa = 300`, held-out validation at
stride 10 (`n = 42,268` distinct identifiers).  The `assoc` transition is
evaluated from the stored numbers `(c, D)`; sampling needs only the `k` distinct
left-cluster rows.

## 1. Coverage

| model | size | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|
| `V = 4,096`, full table | 16.8 MB | 42.149 | 90.3 % | 99.5 % |
| `V = 4,096`, `k = 32` | 22.0 kB | 51.245 | 78.1 % | 98.1 % |
| `V = 6,144`, full table | 37.7 MB | 40.786 | 92.0 % | 99.6 % |
| `V = 6,144`, `k = 16` | 29.9 kB | 49.317 | 80.5 % | 98.5 % |
| `V = 8,192`, full table | 67.1 MB | 39.949 | 93.1 % | 99.7 % |
| `V = 8,192`, `k = 16` | 39.8 kB | 47.727 | 82.5 % | 98.8 % |

The 64-bit set is the discriminating one; 128 bits is essentially "everything
except the generated long tail".  Clustering costs far more 64-bit coverage than
it costs mean bits — 12.2 / 11.5 / 10.6 points against 9.1 / 8.5 / 7.8 bits — so
the budget question is really a 64-bit-coverage question, and the penalty
*shrinks* as the vocabulary grows.  The full-table rows are 760–1,700× the size
of the clustered model and are not a shipping option; they are the ceiling.

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
| `V = 4,096`, `k = 32` | 53 chars | 8 chars | 8,963 of 9,257 (96.8 %) |
| `V = 6,144`, `k = 16` | 53 chars | 8 chars | 7,963 of 8,242 (96.6 %) |
| `V = 8,192`, `k = 16` | 59 chars | 9 chars | 7,232 of 7,397 (97.8 %) |

Fit rate by character length (`V = 8,192`, `k = 16`):

| len | n | fit ≤64 | | len | n | fit ≤64 |
|---:|---:|---:|---|---:|---:|---:|
| 1–8 | 7,198 | 100.0 % | | 24 | 783 | 60.0 % |
| 10 | 2,354 | 98.7 % | | 28 | 531 | 43.9 % |
| 12 | 2,474 | 96.9 % | | 32 | 320 | 29.4 % |
| 14 | 2,409 | 93.9 % | | 36 | 180 | 17.2 % |
| 16 | 2,035 | 90.7 % | | 40 | 91 | 8.8 % |
| 18 | 1,648 | 85.5 % | | 44+ | ~420 | ~3.4 % |
| 20 | 1,325 | 76.9 % | | | | |

The two ends of the overlap, in full — the longest compressed sizes that fit,
and the shortest uncompressed sizes that do not (`V = 8,192`, `k = 16`):

| longest fitting | shortest failing |
|---|---|
| `operationInputTestGetObject_78` 30 ch, 64.00 b; `releasePreflightProgressMember` 30, 64.00; `PFN_vkUpdateDescriptorSets` 26, 64.00; `Hvt_amd64` 9, 64.00 | `AixBosRte` 9 ch, 65.44 b; `aaaaaaaaa` 9, 71.20; `eNOTEMPTY` 9, 71.25; `bGtCwr2zD` 9, 76.54 |

A 30-character identifier can fit while a 9-character one fails, and the short
failure misses by up to twelve bits — it is a genuinely unpredictable name, not
a rounding error at the boundary.  The vocabulary also *heals the short end*:
at `V = 8,192` **every** identifier of 8 characters or fewer fits (7,198 of
them).  It moves the top of the range much faster than the bottom — 53 → 59
characters fitting against 8 → 9 characters failing — so a bigger vocabulary
*widens* the overlap rather than sharpening the cut.

**The encoder cannot decide from the length** — it must encode and test.  A
"short names always fit" rule holds only up to 8 characters; past that an
unpredictable 9-character name fails while a predictable 30-character one
succeeds.

## 3. What fails

A caution about reading those example lists: they are sorted by *character*
length, so the "shortest failing" column selects freaks by construction — the
shortest thing the model cannot price is bound to look like an instruction
mnemonic.  The failure *mass* is not like that.  Marking each identifier
(`V = 8,192`, `k = 16`):

| feature | share of fitters | share of failers | over-represented by |
|---|---:|---:|---:|
| `_` followed by a capital (`t_NEWLINE`) | 2.5 % | **13.8 %** | **5.5×** |
| a run of ≥2 capitals (`RADIX_u32`) | 5.8 % | **19.5 %** | 3.4× |
| contains `_` | 7.8 % | **24.7 %** | 3.2× |
| contains a digit | 10.0 % | **20.9 %** | 2.1× |
| no `aeiou` vowel (`_sngl`, `bGtCwr2zD`) | 2.4 % | **0.2 %** | *under*-represented (12×) |
| none of the above | 84.3 % | **62.7 %** | — |

**The strongest single marker is unconventional capitalisation** — an underscore
followed by an all-caps word, as in `t_NEWLINE`, `DW_OP_nop`,
`SSL_CTX_remove_session` — 5.5× over-represented among failures.  These are
exactly the identifiers the corpus's case normalisation *declines* to touch:
`classify_identifiers.py` only rewrites the all-lower and all-upper classes,
leaving genuinely mixed-case names verbatim, because rewriting them would
collide across classes ([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)).
`t_NEWLINE` really would compress as `t_newline` or `tNewline` — but recovering
which of those it was needs the case class stored, which is a design change, not
a free win.

The vowel row is the mirror image and the interesting new one: a consonant-only
name is usually a short mnemonic (`bcmp`, `cls`, `getc`), so it is a *better*
than average fitter.  The feature is not a defect; it is a length proxy.

Even so, **63 % of the failures carry none of these markers**.  The bulk of the
loss is ordinary CamelCase identifiers — an unseen *combination* of ordinary
words — not a distinguishable syntactic class that could be special-cased.

## 4. A generative view

50,000 identifiers drawn from the model (a cycle from the stop token back to
it):

| model | mean len (corpus 16.25) | valid syntax | real identifier | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|---:|---:|
| `V = 4,096`, `k = 32` | 16.21 | 98.2 % | 2.19 % | 51.694 (51.245) | 72.1 % (78.1) | 94.3 % (98.1) |
| `V = 6,144`, `k = 16` | 16.24 | 96.9 % | 2.32 % | 49.936 (49.317) | 73.8 % (80.5) | 95.0 % (98.5) |
| `V = 8,192`, `k = 16` | 16.30 | 97.2 % | 2.18 % | 48.692 (47.727) | 75.0 % (82.5) | 95.6 % (98.8) |

(bracketed values are the corpus's own, for comparison.)  Examples at
`V = 8,192`: `RecTypeId`, `partitionMathFromCustomClient`, `ref`,
`rect_SLoadAes`, `ProviderTextArgsFilter`, `Nodes`, `colorCall`.  At `V = 6,144`
the samples start including empty strings and bad starts (`HttpSet`, `noData`,
`Binary`, ``, `encode`).

Three things show up consistently:

* **The model reproduces the identifier *shape* almost exactly** — the length
  distribution matches the corpus to a tenth of a character (16.2–16.3 against
  16.25).
* **Almost none of it is real.** Only ~2.2 % of samples are an actual identifier
  in the reference set, so the residual mass of the bijection lands on
  plausible-looking but unreal names.
* **The generative tail is heavier than the empirical one.**  A sample's own
  coverage is *below* the corpus's by 6–7.5 points at 64 bits and by 3–4 at 128,
  and the gap does *not* shrink with the vocabulary (6.0 → 6.7 → 7.5).  So the
  tail of the 64-bit set behaves worse than the average real identifier, and a
  bigger word list buys coverage without making the tail more realistic.  What
  the bigger list does buy is well-formedness: the 96.9–98.2 % syntax rate is
  flat, where the pre-grid study fell to 94.2 % at 11,758 words.

## What it shows

* The 64-bit set covers 78 % of distinct identifiers at 22 kB, 81 % at 30 kB and
  83 % at 40 kB; the 128-bit set 98–99 %.  Whether that is *useful* depends on
  the occurrence weighting (retired finding: ~92 % of occurrences) and on how
  much model size the standard is willing to carry — the 83 % figure needs
  40 kB, not 20 kB ([`MODEL_BUDGET.md`](MODEL_BUDGET.md)).
* Membership is not a length rule: failures are unpredictable identifiers of
  ordinary length, and a bigger vocabulary widens the length overlap while
  healing the short end.
* Sampling is a cheap check on the *decoder*: the model gets the shape right and
  the tail wrong, so the two ends of the set behave differently.
* The gap between the clustered model and the full table (10.6–12.2 points of
  64-bit coverage, 7.8–9.1 bits) is the largest single loss in the system, and
  it is a `k`-and-`V` question, not a coding question.

## Reproducing

```sh
python3 scripts/budget64_study.py --dir work/tw4096ns --ks 32 --stride 10
python3 scripts/budget64_study.py --dir work/tw6144ns --ks 16 --stride 10
python3 scripts/budget64_study.py --dir work/tw8192ns --ks 16 --stride 10
```
