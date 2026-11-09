# The 64-bit and 128-bit identifier sets

Status: **results at the shipped model.**  What fraction of real identifiers
the two budgets cover, where the boundary lies in *character* length, what kind
of identifier fails, and what a random integer of the set decodes to — all
measured by encoding and decoding with the packed standard file
([`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md) §3), not with an arithmetic
transition standing in for it.

## Setup

`scripts/budget64_sets.py`.  Every held-out identifier (stride 10,
`n = 42,268`) is tokenised, encoded and decoded by the standard model —
30,745 bytes at `V = 8,191`, `k = 32`, `q = 1` — and its code length is the
number of bits the file actually spends.  The 64-bit set is "code length ≤ 64"
and the 128-bit set "≤ 128"; nothing here is estimated, sampled or rounded.

The comparison row is the **flat yardstick** of [`MODEL_BUDGET.md`](MODEL_BUDGET.md)
§5.2: one tree per left cluster over all `V` words, the same convention with
the factorisation removed.  It is a ceiling on what a Huffman code can do at
this vocabulary, and it is not shippable.

## 1. Coverage

| code | file | mean bits | fit ≤64 |
|---|---:|---:|---:|
| the shipped model, `(8,191, 32)` | 30,745 B | 45.218 | **85.0 %** |
| factored, `(8,191, 16)` | 29,329 B | 45.677 | 84.5 % |
| flat, `(8,191, 16)` | 123,401 B | 43.333 | 86.9 % |
| flat, `(8,191, 64)` | 420,361 B | 42.134 | 88.4 % |

The 128-bit set covers 99.0 % of the corpus; it is essentially "everything
except the generated long tail", so every question below is a 64-bit question.

**The earlier study overstated the price of the factorisation.**  It compared
the clustered model with an arithmetic *full table* and reported a cost of
10.6–12.2 points of 64-bit coverage.  That ceiling is not a code anyone can
decode: it is `k·V` numbers, 67 MB at `V = 8,192`, and its depths would not fit
the four-bit field ([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §5.2).  Against the
flat *Huffman* code at the same `k` (`8,192/16`: 123,401 B, 43.333 bits,
86.9 %), the factorisation costs **2.4 points and 2.3 bits**, and the shipped
`k = 32` model is 1.9 points and 1.9 bits behind that flat code — the extra
`k` buys back half a point.

The flat code is still not the buy.  Recovering 1.9 points on the frontier —
`8192/32` → `8192/64` — costs 2.6 kB for 0.3 points, about 8.5 kB a point, so
the whole 1.9 would cost roughly 16 kB; the flat file costs 94 kB more than the
factored one at the same `k`.  Factorisation remains domination, but it is a
small loss, not the dominant one it once looked.

## 2. The boundary in uncompressed length

Code length is **not** monotone in character length, so there is no clean length
cut — only an overlap:

* the longest identifier that fits is **59 characters** (60 bits);
* the shortest that fails is **9 characters** (71 bits);
* of the 34,919 identifiers between 9 and 59 characters, **6,207 (17.8 %)** fail.

Fit by character length (every second length from ten upwards):

| len | n | fit ≤64 | | len | n | fit ≤64 |
|---:|---:|---:|---|---:|---:|---:|
| 1–8 | 7,198 | **100.0 %** | | 24 | 783 | 66.4 % |
| 9 | 2,131 | 99.8 % | | 26 | 636 | 60.2 % |
| 10 | 2,354 | 99.8 % | | 28 | 531 | 50.1 % |
| 12 | 2,474 | 98.1 % | | 30 | 358 | 37.7 % |
| 14 | 2,409 | 95.8 % | | 32 | 320 | 34.7 % |
| 16 | 2,035 | 94.1 % | | 34 | 249 | 24.1 % |
| 18 | 1,648 | 88.7 % | | 36 | 180 | 22.8 % |
| 20 | 1,325 | 81.7 % | | 40 | 91 | 12.1 % |
| 22 | 1,045 | 71.8 % | | 44+ | 693 | 3.8 % |

Every identifier of eight characters or fewer fits (7,198 of them) — the short
end is *healed* by the vocabulary, as it was before.  The two ends of the
overlap, in full:

| longest fitting | shortest failing |
|---|---|
| `GoogleAdsSearchads360V23ServicesCustomerClientLinkOperation` 59 ch, 60 b; `PutBucketNotificationConfigurationResponseDeserializer` 54, 57; `updateApplicationDeployment_argsStandardSchemeFactory` 53, 63 | `aaaaaaaaa` 9 ch, 71 b; `bGtCwr2zD` 9, 70; `sbbqMiSxl` 9, 68; `vqtbl1qP8` 9, 67 |

A 59-character identifier fits while a 9-character one misses by seven bits.
**The encoder cannot decide from the length**: it must encode and test.  A
"short names always fit" rule holds only up to eight characters.

## 3. What fails

The example lists above are sorted by *character* length, so the "shortest
failing" column selects freaks by construction.  The failure *mass* is not like
that.  Marking each identifier:

| feature | share of fitters | share of failers | over-represented by |
|---|---:|---:|---:|
| `_` followed by a capital (`t_NEWLINE`) | 2.7 % | **14.6 %** | **5.4×** |
| a run of ≥2 capitals (`RADIX_u32`) | 6.0 % | **20.4 %** | 3.4× |
| contains `_` | 8.1 % | **26.0 %** | 3.2× |
| contains a digit | 10.1 % | **21.8 %** | 2.2× |
| no `aeiou` vowel (`_sngl`, `bGtCwr2zD`) | 2.3 % | 0.2 % | *under*-represented (13×) |
| none of the above | 80.0 % | **53.7 %** | — |

**The strongest single marker is still unconventional capitalisation** — an
underscore followed by an all-caps word, as in `t_NEWLINE`, `DW_OP_nop`,
`SSL_CTX_remove_session` — 5.4× over-represented among failures.  These are
exactly the identifiers the corpus's case normalisation declines to touch:
`classify_identifiers.py` rewrites only the all-lower and all-upper classes,
leaving genuinely mixed-case names verbatim, because rewriting them would
collide across classes ([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)).
`t_NEWLINE` really would compress as `t_newline` or `tNewline` — recovering
which of those it was needs the case class stored, which is a design change, not
a free win.

The vowel row is the mirror image: a consonant-only name is usually a short
mnemonic (`bcmp`, `cls`, `getc`), so it is a *better* than average fitter.  The
feature is not a defect; it is a length proxy.

Even so, **54 % of the failures carry none of these markers**.  The bulk of the
loss is ordinary CamelCase identifiers — an unseen *combination* of ordinary
words — not a distinguishable syntactic class that could be special-cased.

## 4. What a random integer of the set decodes to

Fifty thousand uniform draws from `[0, 2^64)`:

| mean length | pass the lexical rule | are a held-out identifier |
|---:|---:|---:|
| 24.88 characters (corpus 16.25) | 99.1 % | 0.00 % |

Examples: `GlNvIBplainSemantic`, `readPathakeFilePathInclusiveCases`,
`VsizeWeightedSolveWorkload`, `icountmixEicSeconds`,
`patEntityFunctionndWriteLocations`, `namedrowTickConma__pro`.

Two readings, both useful for the standard:

* **The set is the whole decodable space, not a name list.**  Every one of the
  2⁶⁴ integers decodes; none of 50,000 lands on a real identifier, and the mean
  draw is nine characters longer than life.  Membership in the 64-bit set says
  nothing about whether a string is a name a programmer would write — that
  judgement lives in the language model, not in the code.
* **The decode is total and cheap.**  A tenth of a percent of draws fail only
  the *lexical* rule (a leading digit, say); the rest are well-formed strings.
  The bijection has no holes to guard against, which is what makes the decoder
  a table walk with no error path.

## What it shows

* At 30,745 bytes the shipped model covers **85.0 %** of distinct held-out
  identifiers within 64 bits and **99.0 %** within 128.
* The factorisation costs 1.9 points against the flat code, and the flat code
  charges 94 kB for the 2.4 points it wins at a matched `k` where the frontier
  charges about 20 kB.
* Membership is not a length rule: failures are unpredictable identifiers of
  ordinary length, and the vocabulary heals the short end while widening the
  overlap at the long end.
* The 64-bit space is overwhelmingly fabricated names.  A standard should say
  so, because it means the set is defined by the code, not by the corpus.

## Reproducing

```sh
python3 scripts/budget64_sets.py
```

The old arithmetic version of this study is at `scripts/budget64_study.py`; it
is kept for the record, and its sizes are not the model's.
