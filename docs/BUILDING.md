# Building your own tables

Status: **packaged.** One command turns a list of identifiers into a model file
that both implementations read. This note is the guide to that command, what
each stage costs, and what is deliberately left out.

## Who this is for

You want your own corpus, or your own `V` and `k`, and you do **not** want to
change the file format. The format is [`MODEL_FORMAT.md`](MODEL_FORMAT.md), the
code and the sets are [`STANDARD.md`](STANDARD.md), and a model built from
another corpus is a *custom* model by §9 of it: a different file with a
different digest, which is exactly how a deployment finds out it is not on the
standard. (Run on the corpus below it builds the standard itself, which is the
last section of this note.)

## The command

```bash
python3 scripts/build_tables.py --corpus corpus/identifiers.multilang.txt \
    --out build --V 8192 --k 32
```

It needs Python 3 and `numpy`, nothing else. Outputs, all under `--out`:

| path | what it is |
|---|---|
| `camel/` | the case-normalised corpus (three classes, camelised, merged) |
| `train.txt`, `val.txt` | the split, by line position in the sorted corpus |
| `tw8192/` | the dictionary and the cyclic bigram counts (`dict.txt`, `sym.npy`, `adj.npz`, `meta.json`) |
| `model.nvm1` | the model file — the deliverable |
| `model.yaml` | the same model, human-readable and diffable |
| `build.json` | every knob, the digest, the section sizes and the measured rate |

`--V` counts the file's symbols, characters and the stop included, so the number
of pair-merge words is `V − 1 − (characters in the corpus)`; `--words 8128` sets
the word count directly. Both are printed at the start of the build.

## The stages

| stage | script | design note |
|---|---|---|
| case normalisation | `classify_identifiers.py`, `camelize_identifiers.py`, `merge_identifiers.py` | [`CASE_NORMALISATION.md`](CASE_NORMALISATION.md) |
| split | in `build_tables.py` | — |
| dictionary and adjacency | `tree_words.py train` | [`TREE_WORDS.md`](TREE_WORDS.md), [`DICTIONARY_RULES.md`](DICTIONARY_RULES.md) |
| model | `model_size.build_model` | [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md), [`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md) |
| check | the decoder in `model_size` | [`BUDGET64_STUDY.md`](BUDGET64_STUDY.md) |

**Case normalisation** is not optional for a mixed-case corpus. Two thirds of a
name's characters are usually its case convention, and camelising the
all-lower and all-upper classes is what lets one dictionary serve all three
(§"What it costs" of `CASE_NORMALISATION.md`). `--skip-normalise` is for a
corpus that is already in the target form.

**The split** holds out every `--holdout-stride`-th line (default 10) so that
the rate printed at the end is measured on identifiers the dictionary never
saw. It is a report, not a build input: the adjacency always counts the training
lines.

**The dictionary** comes from every `--sample`-th training line (default 20)
because the pair-merge is the expensive part; **the adjacency** always counts
the whole training set, because the model needs the counts even where the word
list did not look. That asymmetry is deliberate and is why the build is
affordable at `V = 8,192`.

**The model** co-clusters the matrix, builds the Huffman trees with the depth
bias, derives the canonical codewords and packs the file. It is the same code
path the shipped model took, so a custom file and the standard cannot disagree
about the format.

**The check** reads `model.nvm1` back with the decoder, round-trips a sample of
the held-out identifiers and prints mean bits, the 64- and 128-bit fit rates
and the longest code. The sample is spread over the whole file rather than taken
from its start, because the corpus is sorted and the first few thousand lines
would all begin with the same letter. If a round trip fails it stops rather than
writing `build.json`.

## What it costs

Measured on this four-core box, from the 4.4 million-identifier corpus:

| stage | V = 1,024, 200k lines | V = 8,192, 4.4M lines |
|---|---:|---:|
| normalise + split | 1 s | 35 s |
| dictionary | 1 s | 31 s |
| adjacency | 3 s | 45 s |
| model | 1 s | 50 s |
| check (20k held out) | 1 s | 1 s |
| **total** | **7 s** | **under 3 min** |

Memory peaks in the model stage, which holds the prior-added matrix densely:
`V²` doubles, 0.5 GB at the standard `V`. Nothing else is large.

## The knobs, and what each buys

* `--V` — the frontier is measured in [`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6:
  4,096 / 6,144 / 8,192 buy 80.5 % / 83.2 % / 85.0 % of identifiers within 64
  bits for 13.5 / 22.5 / 30.7 kB. The standard is 8,192; a smaller file is a
  real trade, not a defect.
* `--k` — left clusters, `--q` — right clusters per left cluster. `q = 1` shares
  one assignment between the two sides; `q > 1` separates them and pays `kq`
  bottom trees instead of `k` ([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)).
* `--kappa` — the prior mass per row, in counts. 300 is the reference used
  everywhere ([`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md)).
* `--sample`, `--holdout-stride` — cost and honesty, as above.

Two things that look like knobs and are not: the **word list order** (creation
order, and it cannot be permuted — the tokeniser replays the rules in rank
order, [`MODEL_BUDGET.md`](MODEL_BUDGET.md) §5.4) and the **stop token** (it is
the padding, not a symbol, [`ENCODING.md`](ENCODING.md) §3).

## What is not packaged

* **Getting the corpus.** Harvesting identifiers from ten ecosystems is
  research code by nature — downloads, package formats, lexical scrubbing — and
  it stays in `scripts/` as such ([`CORPUS.md`](CORPUS.md) §"Reproducing").
  `build_tables.py` takes any file with one identifier per line, so a corpus of
  your own needs nothing from that section.
* **Changing the format.** The file is the standard; adding a section or a
  symbol is a new version of it, not a build option
  ([`STANDARD.md`](STANDARD.md) §9).
* **Non-ASCII identifiers.** The tool reads UTF-8 and takes its alphabet from
  every character in the corpus, so a corpus of your own may contain accented
  Latin, Cyrillic, Greek, Han or anything else; the alphabet is stored as UTF-8
  and those names get ids and codewords like any others. The standard corpus
  has none — the extractor blanks any run that touches a non-ASCII byte — so
  the shipped model's alphabet is the 63 ASCII characters. Case normalisation
  covers accented Latin and Cyrillic as well as ASCII, and treats every other
  character as inert (`STANDARD.md` §11), so a non-ASCII corpus is normalised
  consistently rather than half-way. How rare those names are, and what a wider
  alphabet costs, is [`UNICODE.md`](UNICODE.md).

## Using the result

```console
$ python3 -m varnames.cli --model build/model.nvm1 encode getUserName
getUserName      124101637  27 bits
$ cargo run --release -- --model build/model.nvm1 encode getUserName
getUserName            124101637  27 bits
```

Both read any file the builder writes, and both verify nothing but the file's
own self-consistency when it is not the standard: `--model PATH` is the whole of
the custom-table support.

## Reproducing the shipped standard model

Run the command from the top of this note over the whole corpus and it
reproduces the shipped file exactly:

```bash
python3 scripts/build_tables.py --corpus corpus/identifiers.multilang.txt \
    --out build --V 8192 --k 32
```

Under three minutes later `build/model.nvm1` is 30,745 bytes with SHA-256
`976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79`, the file in
`standard/`, table for table and bit for bit. The check stage reads it back and
scores 45.051 bits and 85.4 % within 64 bits on its 20,000-identifier sample.

The standard was originally built the shorter way, from dictionaries that had
already been built:

```bash
bash scripts/h5_build.sh ns          # work/tw4096ns … work/tw8192ns
python3 scripts/build_standard_model.py --dir work/tw8192ns --k 32 --out standard
```

`build_standard_model.py` writes the same two files from an existing dictionary
directory, prints the digest, and asserts the packed bytes read back. The two
routes meet at the same digest, which is the sense in which the tool is the code
that made the standard.

`--skip-normalise` is the same pipeline with the corpus taken as already
camelised. Run against the training half of the corpus it makes a second file
from that half alone, and so shows what the split is worth:

```bash
python3 scripts/build_tables.py --corpus work/camel/merged_training.txt \
    --out build --V 8192 --k 32 --skip-normalise
```

It builds from the training half of the corpus and then holds out a tenth of
that, so its dictionary is trained on 3.42 million identifiers where the
standard's had 3.80 million. The file is 30,733 bytes, twelve fewer than the
standard, and on the standard's held-out file — `merged_validation.txt`, stride
10, all 42,268 identifiers, none of which is in the corpus either dictionary was
built from — it reads 45.255 bits and 84.8 % within 64 bits against the
standard's 45.218 and 85.0 %. On its own split it reads 44.817 bits and 85.9 %.
