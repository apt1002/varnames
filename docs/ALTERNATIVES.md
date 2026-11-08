# What was rejected, and why

Status: **a synthesis, not a new experiment.** Every number below is measured in
the note it cites. This file is the index of the design decisions that went the
other way, gathered so that a reader who wants to know "why not X" gets both an
answer and the place it was measured.

The adopted design is small: a pair-merge word list; a cyclic word-bigram matrix
with a prior; a co-clustered block model of that matrix; canonical Huffman codes
built from it; and a packed file that stores depths, not probabilities. Each of
those choices had a serious alternative, and each alternative lost to a
measurement rather than to taste.

## How to read a rejection

Three currencies are used, and they are not interchangeable:

* **bits per held-out identifier** — what a change does to the code length;
* **bytes** — what it does to the model file;
* **fit rate** — the share of held-out identifiers inside the 64-bit budget,
  which is the product's actual claim.

The frontier sells bits for **3–5 kB each**
([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6): at the operating point, 0.1 bit is
worth 0.3–0.5 kB. So a change that saves hundredths of a bit but costs
kilobytes is rejected on sight, and that single ratio explains most of what
follows.

Two cautions apply throughout. A win measured in an *arithmetic account*
(sums of `−log₂ P`) is not yet a shipping win, because the shipped code is a
prefix code with a zero-padded terminator, and some of those wins do not survive
the change of representation ([`ENCODING.md`](ENCODING.md) §2). And nothing
here was decided at the testing vocabulary: `V = 512` exercises scripts and
settles nothing ([`SMALL_DICT.md`](SMALL_DICT.md)).

## The corpus

**Non-ASCII identifiers.** The shipped corpus is ASCII: the extractor blanks
any run that touches a non-ASCII byte, so a name written in Cyrillic, Han,
kana or accented Latin never reaches the tokeniser, and the model's alphabet
stays at 63 characters. The model need not be ASCII — the alphabet is stored
as UTF-8 and the builder reads UTF-8, so this is a choice about the corpus we
ship, not a limit of the format — and the exclusion is cheap. Across 62,500
repositories in five languages, non-English *identifiers* appear in **0.14 %
of files in 2015 and 0.28 % in 2025**, against 11.9 % for comments; in 2.9 M
public Java repositories, **93 % of projects from Chinese-speaking users and
88 % from Spanish speakers have ASCII-only identifiers**, and only 7 % of the
first write names in Han script — the rest transliterate (pinyin, `numero`
for `número`). A token scan of 3.7 M Python identifiers found **12**
non-ASCII names, all in one Unicode-set library's examples. A wider alphabet
would be cheap for Latin-with-accents, Greek and Cyrillic and a different
model for CJK, where 20,992 Han code points make the pair-merge dictionary
degenerate; the names it would add are the rare ones, and the hash fallback
already covers them ([`UNICODE.md`](UNICODE.md), [`CORPUS.md`](CORPUS.md)).

## The word list

**Run words, `(u^k)`.** An earlier dictionary allowed a word for a run of one
repeated character, one word per observed length, with a `k`-ary node and a
run-length table to replay it. It won on synthetic run-heavy data and on raw
bigram scores; on identifiers the action is worth a handful of `ss`/`tt`/`__`
runs that a neighbour pair delivers anyway. Under the co-clustered model the
difference is **0.02–0.04 bits and ≤ 0.2 points, in both directions**, against
two model-budget items saved. Rejected; the adopted rule forbids every
self-merge ([`DICTIONARY_RULES.md`](DICTIONARY_RULES.md) §"Rejected: the run
word", [`RUN_LENGTHS.md`](RUN_LENGTHS.md)).

**Choosing the merge by `Δ` rather than frequency.** Scoring the top candidate
pairs by the change in corpus size and taking the best is the better-founded
greedy rule. On real identifiers its edge is **0.32 %, 0.14 %, 0.20 %** at 8, 16
and 24 pairs — and its sign flips between splits — for eight times the work per
step. The frequency rule is the robust, cheap proxy, and it is what ships
([`DICTIONARY_RULES.md`](DICTIONARY_RULES.md) §"The exact score").

**Overshoot, then prune by removal cost.** Building the list 1.5× too large and
deleting the least valuable words is a more thorough way to spend the last few
slots, and on the raw bigram score it works: **0.86 bits** better than plain
greedy at 512 words, 0.145 at 2,040. But it is **0.6–1.8 bits worse** once the
matrix is co-clustered — the representation that ships — because pruning
fragments the spectrum the block model lives on. Rejected
([`PRUNE_WORDS.md`](PRUNE_WORDS.md)).

## The matrix

**A character-level successor model.** Encoding each character from its
preceding context is the obvious information-theoretic design, and it does
compress. At a comparable vocabulary the word model codes identifiers **10–16 %
shorter**, and the successor model pays 16 bytes for every common substring
where the word list pays a rule per word. Rejected
([`SUCCESSOR_MODEL.md`](SUCCESSOR_MODEL.md)).

**Coding the table directly.** Storing the largest `N` observed cells verbatim
and leaving the rest to the independence prior is the natural direct code of the
largest object. The residual after any low-rank or marginal fit is not sparse,
and at the grid direct coding is behind the block model even under a counting
convention that ignores the cost of naming the coded cells. Rejected
([`MATRIX_COMPRESSION.md`](MATRIX_COMPRESSION.md)).

**Correcting the prior for structural zeros.** Some cells of the matrix are
impossible for any corpus, and they can be listed exactly. Correcting the
independence prior for them moves held-out length by at most **0.06 bits** — the
prior is itself a small correction. Rejected as negligible
([`STRUCTURAL_ZEROS.md`](STRUCTURAL_ZEROS.md)).

**Breaking open the pair.** A word is two earlier words glued together, so the
prior could recurse down the merge tree instead of treating every vocabulary
item alike. Designed in full and measured: at the canonical grid it is **10–11
bits worse** at the best `κ` and **13–14 points worse** on the 64-bit fit. The
structure is real but the estimate built from it is not better than the
unstructured one. Rejected ([`BREAK_OPEN_PRIOR.md`](BREAK_OPEN_PRIOR.md)).

**The boundary trigram `(u, v, \n)`.** The first-order model codes the last two
bigrams of an identifier independently; the trigram "is `v` final, given `u`?"
is left on the table, and a word `v\n` would capture it. The held-out gain is
**≈ 0.4–0.5 bits per identifier, about 1 %**, and that is an upper bound.
Rejected ([`BOUNDARY_TRIGRAM.md`](BOUNDARY_TRIGRAM.md)).

## Shrinking the matrix

**The rank-`L` factorisation as the model.** The square-root (Hellinger)
factorisation is the better low-rank model, and it is the space the build
clusters in. But as the *model* at equal storage it loses: at `V = 4,096`, a
`16 × 16` block model of 8,448 numbers (0.05 % of `V²`) codes **51.580 bits
against 55.623** for the factorisation at slightly *larger* storage. The margin
is **4.0 bits at 4,096 and 3.5 at both 6,144 and 8,192**. Co-clustering is the
compressor; the factorisation is the coordinate system it works in
([`CLUSTER_WORDS.md`](CLUSTER_WORDS.md),
[`HELLINGER_FACTORISATION.md`](HELLINGER_FACTORISATION.md)).

**Splitting the right side (`q > 1`).** Giving each left cluster its own set of
right clusters is cheap to implement and the format keeps the knob. In the
packed file at the operating point, `q = 2` buys **0.12 bits per identifier for
1,536 B** — 13 kB per bit against a frontier at 3–5 kB. Rejected
([`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md)).

**Separate assignments for the two sides.** Two maps instead of one is the more
general model. Measured in the packed file, the omitted second map is worth
**0.32 bits for 5,120 B** — 16 kB per bit — and over five seeds the shared model
sits **0.34 points above** the asymmetric frontier at matched bytes when
`k = 32`, exactly on it when `k = 64`. Shared ships at `q = 1`
([`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md)).

**A cluster reserved for the stop token.** The stop is the odd symbol, and
reserving clusters for it is nearly free in bits once the clustering profile is
held fixed (**0.007–0.19**), but it buys nothing: the zero-weight terminator
already removes the stop's cost. Rejected
([`NEWLINE_CLUSTER.md`](NEWLINE_CLUSTER.md), [`ENCODING.md`](ENCODING.md) §2).

**Codesigning the assignment and the code.** Choosing cells by their code cost
as well as their mass changes nothing in the format — the decoder cannot tell.
At a matched `k` an assignment chosen by the code term alone is **1.921 bits per
identifier worse**, because the code term has no opinion about which cells are
alike. Parked, negative ([`CODESIGN.md`](CODESIGN.md)).

## The code

**Arithmetic coding.** The obvious way to beat a prefix code: fractional bits
per symbol, and the arithmetic bound is the reference in
[`CODING_OVERHEAD.md`](CODING_OVERHEAD.md). It loses on the terminator. With a
prefix code the all-zeros codeword *is* the stop, so the padding is the
terminator and costs nothing; with an arithmetic code the value `0` lies in the
stop's sub-interval only for the first symbol of the first identifier, so the
stop must be encoded at `−log₂ pₙ`, typically 1–3 bits. Add the ~1 bit of
trailing zeros the integer form gives away for free against a summed code
length, and Huffman is about **a bit per identifier ahead**, lifting the 64-bit
fit rate by ~1.5 points. Rejected ([`ENCODING.md`](ENCODING.md) §§2.1–2.2,
[`CODING_OVERHEAD.md`](CODING_OVERHEAD.md)).

**A flat Huffman code at the matched `k`.** Without the factorisation the code
is better on bits: at `8,192/16` a flat code is **123,401 B, 43.333 bits and
86.9 %** against the shipped **30,745 B, 45.218 bits and 85.0 %**. It buys **1.9
points for four times the bytes** — 92 kB for 1.9 points, or 48 kB per point,
against a frontier that sells a point for 3–5 kB. At `8,192/64` the flat code
reaches 88.4 % for 420,361 B. Rejected on bytes
([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6,
[`BUDGET64_STUDY.md`](BUDGET64_STUDY.md)).

**Publishing the probabilities.** A table of conditional probabilities is the
most direct description of the model, and a `k·V` table at `V = 8,192` is 67 MB
of numbers. Publishing the *code* — depths and canonical codewords — is a few
kilobytes and needs no floating-point arithmetic in the decoder to reproduce
([`ENCODING.md`](ENCODING.md) §3, [`MODEL_FORMAT.md`](MODEL_FORMAT.md) §2).

**A hash fallback for the identifiers that do not fit.** Sensible in a
deployment, but it is not part of the bijection and it is not specified here
([`STANDARD.md`](STANDARD.md) §10).

## The file

**YAML alone.** The YAML form is readable and diffable, and it is shipped
alongside the binary as `model.yaml`. As the file itself it is **182,507 B
against 30,745 B**, and a decoder that parses YAML needs a parser in every port.
Rejected as the delivery form ([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3).

**Compressing the YAML with a general-purpose compressor.** The YAML is plain
text (182,507 B), and a compressor could carry it without anyone writing a
decoder: decompress to a string at load time and parse. It is not competitive.
On the shipped model the best of them is **bzip2 at 33,662 B**, then xz
(36,292 B; 36,420 with `-9e`), zstd (37,754 B at `--ultra -22`) and gzip
(41,742 B). The packed file is **30,745 B**, so the best general-purpose
compressor is **2.9 kB — 9.5 % — larger**, and it still has to be decompressed
and parsed. The reason is the one that runs through this file: the YAML spends
its bytes on text where the packed form spends bits — decimal digits,
indentation, repeated labels — and a compressor cannot undo a representation it
did not choose ([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3).

**Five-bit depths.** Storing the true Huffman depths costs five bits per leaf;
four suffice once a bias flattens the trees, and the bias is found by search
because no closed form bounds a Huffman span. Five bits would take the file from
**30,745 B to 31,901 B** — 1,156 B, 3.6 % — with no change in fit. The four-bit
field and its bias are what ship ([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3.1).

## What this list is not

It is not a claim that the design is optimal. Each entry is a measurement that
closed a direction, and the remaining directions are recorded as open in
[`../PLAN.md`](../PLAN.md). What the list does show is the shape of the
argument: the bits are not in the dictionary rule, not in the prior's
structure, not in a finer table, and not in the coder — they are in the size of
the table that has to be described, which is why the product spends its bytes on
words and a coarse block model and takes the rest for free.
