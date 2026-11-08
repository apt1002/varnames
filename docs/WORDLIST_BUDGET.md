# Where the model budget goes: word list vs table

Status: **succeeded (as a budget rule).**  The word list and the block matrix
are the two things the model spends numbers on, and at matched model size the
larger word list always wins.  Buy words first, clusters last.  Measured in the
shipped file the same rule holds in bytes, and the word list turns out to be
two thirds of the file at the operating point.

## The question

The model has two size knobs that compete for the same budget:

* the **word list** — `V` entries, one dictionary rule each, which sets how
  many tokens an identifier is cut into (and so how much of the corpus the
  table has to describe);
* the **cluster table** — `k² + 2V` numbers for the co-clustered block model of
  the `V × V` adjacency matrix (see [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md)).

`store = k² + 2V` is the same either way: a word and a table cell cost one
number.  A larger `V` buys longer words (fewer tokens per identifier, less work
for the table); a larger `k` buys a finer table (less loss inside it).  Nothing
in the model size distinguishes the two, so the question is purely which mix
codes held-out identifiers best at a fixed `store`.

`scripts/wordlist_budget.py` answers it by sweeping the three grid word lists
with `k ∈ {16, 32, 64, 128, 256}` (`k = 128, 256` only at `V = 4,096`), with
`kappa = 300` and stride-40 validation.  Held-out bits are **per identifier**
(the full cycle length of the token sequence, stop included), so they are
comparable across word lists as long as the validation corpus is the same.

## Results

| `V` | full table | `k=16` | `k=32` | `k=64` | store (`k=16/32/64`) |
|---:|---:|---:|---:|---:|---|
| 4,096 | 42.20 | 51.58 | 51.36 | 50.62 | 8,448 / 9,216 / 12,288 |
| 6,144 | 40.80 | 49.39 | 49.02 | 48.69 | 12,544 / 13,312 / 16,384 |
| 8,192 | 39.93 | 47.71 | 47.48 | 47.28 | 16,640 / 17,408 / 20,480 |

All clustered figures are the two-sided `assoc` model; the full table is the
unclustered bigram model over the same word list.  At `V = 4,096` the sweep
continues to 50.00 at `k = 128` (store 24,576), 48.96 at `k = 256` (73,728),
47.42 at `k = 512` (270,336) and 45.64 at `k = 1,024` (1,056,768) — see the
`k`-scaling table in [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md).

## The same question in the shipped file's bytes

`store` counts numbers; the shipped format stores two of the same objects as
bytes, and `scripts/model_size.py` measures them (`MODEL_BUDGET.md` §7).  At the
cheapest `k` on each word list, `q = 1`, one map, stride-10 held-out:

| `V` | `k` | word list | labels | depths | header | file | bits/id | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 512 | 32 | 936 | 320 | 784 | 74 | 2,114 | 65.535 | 60.3 % | 94.5 % |
| 4,096 | 32 | 9,787 | 2,560 | 2,576 | 74 | 14,997 | 48.866 | 80.5 % | 98.4 % |
| 6,144 | 24 | 15,259 | 3,840 | 3,372 | 74 | 22,545 | 46.735 | 83.2 % | 98.7 % |
| 8,192 | 32 | 20,926 | 5,120 | 4,624 | 75 | **30,745** | **45.218** | **85.0 %** | **99.0 %** |

* **The word list is the largest object, and it grows to two thirds of the
  file.**  44 % of the file at `V = 512`, 65 % at 4,096 and 68 % at 6,144 and
  8,192 (20,926 of 30,745 B).  The rule "buy words first, clusters last" is
  therefore a statement about the biggest single term, not a tie-break.
* **At a fixed byte budget the largest `V` that fits still wins.**  The
  cheapest file measured at `V = 8,192` is 28,205 B (`k = 8`: 20,926 of rules,
  4,096 of bottom depths, 4,096 of labels), and at `V = 6,144` it is 19,951 B
  (`k = 4`).  So a 23.5 kB budget cannot hold an 8,192 file at any `k` measured,
  and the best 6,144 file there is 46.735 bits at 83.2 %; the best 4,096 file is
  48.866 at 80.5 % for 15.0 kB.
  The measured ladder is 512 → 4,096 → 6,144 → 8,192 with the bytes going
  2.1 → 15.0 → 22.5 → 30.7 kB and the bits 65.5 → 48.9 → 46.7 → 45.2: the first
  step is worth 16.7 bits for 12.9 kB, and the later ones 2.1 and 1.5 bits for
  7.5 and 8.2 kB, i.e. 3.5 and 5.4 kB per bit.
* **The leftover still goes to `k`, but it has stopped paying much.**  Within
  `V = 8,192`, `k` from 8 to 32 buys 0.80 bits and 0.8 fit points for 2,540 B;
  from 32 to 64 a further 0.27 bits and 0.3 points for 2,576 B (`MODEL_BUDGET` §7).
  At the smaller word lists the curve is flatter rather than overturned: at
  4,096 the next step (`k = 64`) buys 0.34 bits for 2,064 B, 6.2 kB per bit, and
  at 6,144 `k = 64` buys 0.37 bits for 2,320 B, 6.3 — both above the 2–6 kB/bit
  the grid charges elsewhere, which is why the knees above are 32, 24 and 32.
  So the order of the two knobs is unchanged by the byte accounting: words
  first, then the `k` the remaining bytes can justify.

## What it shows

* **The word list is the dominant lever.**  Merely moving from `V = 4,096` to
  `V = 8,192` drops the *full* table from 42.20 to 39.93 bits/identifier
  (−2.27), and the clustered model at fixed `k = 16` from 51.58 to 47.71
  (−3.87).  This dwarfs anything `k` buys at a fixed word list.
* **At matched store, pick the largest word list that fits.**  The per-list
  floor is `2V`, so the frontier is "the biggest `V` whose floor fits, then
  spend the rest on `k`": at store ≈ 17 k the best point is `V = 8,192, k = 16`
  (47.71, store 16,640), which beats `V = 6,144, k = 64` (48.69, store 16,384)
  by 1.0 bit and `V = 4,096, k = 64` (50.62, store 12,288) by 2.9 bits — for
  1.02× and 1.35× the storage respectively.
* **The clustering penalty shrinks with `V`.**  At `k = 16` the
  `assoc − full` gap falls from 9.38 (`V = 4,096`) to 8.59 (`V = 6,144`) to
  7.78 (`V = 8,192`).  It is still ≥ 7 bits everywhere, so the block model
  remains the weak part even with a big word list — but a bigger word list
  makes the weak part *smaller*, which is the same conclusion from the other
  side.
* **Charging for the dictionary does not change the ordering.**  `store = k² +
  2V` prices a word at the same one number as a table cell and ignores the
  dictionary's own rules (~`2(V − 64)` integers, charged as bytes in
  [`MODEL_BUDGET.md`](MODEL_BUDGET.md)).  Adding it (`k² + 4V`) moves every
  point right, but the frontier still picks the largest `V` at every budget.
  Measured, the packed dictionary at `V = 8,192` is 21,109 B rather than the
  16,256 B the "one byte per stored number" estimate gives (2 × 8,128 integers)
  — the rule indices are the one place the model pays more than a byte per
  number — and the ordering survives that too (measured section above).

## The removable-word refinement

A pair word `(uv)` whose left cluster equals `v`'s and whose right cluster
equals `u`'s has labels implied by its operands', so it could in principle be
dropped and its label re-derived.  The `drop` column of the sweep counts them:
at `k = 16` that is **470 of 4,032** pair words at `V = 4,096` (11.7 %), 817 of
6,080 at `V = 6,144` (13.4 %) and 741 of 8,128 at `V = 8,192` (9.1 %); at
`k = 64` it falls to 194 / 348 / 407 (4.8 % / 5.7 % / 5.0 %).  That is much more
than the 2 of 2,012 seen at `k = 52` on the pre-expansion `tw2040` list: a small
`k` makes pair words share their operands' cells far more often.

Even so the saving is 5–13 % of the *pair* words (0.5 % of `V` at `k = 16`),
and re-coding them would make their labels implicit rather than free — the
decoder would pay a rule lookup on the operands' labels.  The refinement was
not pursued.

## Reproduce

```sh
python3 scripts/wordlist_budget.py --dirs work/tw4096ns,work/tw6144ns,work/tw8192ns \
        --ks 16,32,64 --validation work/camel/merged_validation.txt --stride 40

# the measured ladder: one run per (V, k) point
for spec in "tw512ns 8" "tw512ns 32" "tw4096ns 16" "tw4096ns 32" \
            "tw6144ns 16" "tw6144ns 24" "tw8192ns 32"; do
  set -- $spec
  python3 scripts/model_size.py --dir work/$1 --k $2 --stride 10
done
```

The `work/tw*ns` directories are the pair-merge dictionaries built from a 5 %
sample with adjacency over all lines (see the build-directory key in
[`../PLAN.md`](../PLAN.md)).

## Conclusion

At matched model size, the largest `V` that fits beats a finer `k` by 1–3 bits
across the range tested.  The word list is where the budget should go, and the
table's residual 7–9 bit loss is the part that remains to attack (the
loss-attribution and block-structure experiments in
[`CLUSTER_LOSS.md`](CLUSTER_LOSS.md)) or to accept.
