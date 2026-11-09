# Plan — parallel lines of research

Living index of the research threads.  Each line records execution status and a
pointer to the document that owns the detail; `[ ]` = open, `[~]` = in progress,
`[x]` = done.  Design notes, derivations and results live in the reports
(`docs/*.md`), not here.  Plan identifiers are local to this file; reports and
filenames refer to experiments by name, never by these labels (see `README.md`).

## Standing background (done, load-bearing)

- [x] Corpus build + case normalisation — `docs/CORPUS.md`,
      `docs/CASE_NORMALISATION.md`.
- [x] Character-level fixed-budget compressibility — `docs/CODE_LENGTHS.md`.
- [x] Square-root (Hellinger) factorisation + unobserved-pairs counting fix —
      `docs/HELLINGER_FACTORISATION.md`.
- [x] Choosing `k` and `N` for the model size — `docs/SUCCESSOR_MODEL.md`.
- [x] Dictionary (pair-merge) model: CS identity, per-merge delta —
      `docs/TREE_WORDS.md`.
- [x] Typical run lengths of the corpus — `docs/RUN_LENGTHS.md`.
- [x] Tokeniser speed (precedence parser vs ascending-rank buckets) —
      `docs/TOKENISATION.md`.

## A. Dictionary / pair-merge theory (`docs/TREE_WORDS.md`)

- [x] **A1. Prove `Δ < 0` exactly.** *Solved* for distinct-pair merges.
      `docs/TREE_WORDS.md` §9.0.
- [x] **A2. Relax the no-threefold-repetition assumption.** *Succeeded.*
      `docs/TREE_WORDS.md` §9.1.
- [x] **A3. Greedy alternative** (largest `Δ` vs most frequent pair).
      *Succeeded.*  `docs/DICTIONARY_RULES.md`.
- [x] **A4. `(uv)` vs `(u^n)` crossover.** *Succeeded.*
      `docs/DICTIONARY_RULES.md`.
- [x] **A5. Rewrite `TREE_WORDS.md` for pedagogy.** *Done.*
      `docs/TREE_WORDS.md`.
- [x] **A6. Run-fusion theory** (mirror A1 for runs). *Solved.*
      `docs/TREE_WORDS.md` §9.1.
- [x] **A7. Boundary words (`v\n`).** *Negative — not adopted.*
      `docs/BOUNDARY_TRIGRAM.md`.
- [x] **A8. Rescan-based dictionary builder.** *Done and adopted.*
      `docs/TREE_WORDS.md` §11.
- [x] **A9. No run words.** *Succeeded.*  `docs/DICTIONARY_RULES.md`.

## B. Adjacency matrix construction

- [x] **B1. Canonical adjacency-matrix reference.** *Done.*
      `docs/ADJACENCY_MATRIX.md`.

## C. Apply the dictionary model to `merged.txt`

- [x] **C1. Word × word adjacency counts.** *Done.*
      `docs/ADJACENCY_MATRIX.md`.
- [x] **C2. Fill unobserved adjacencies with the `κ` prior.** *Done.*
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C3. Held-out compressibility.** *Succeeded.*
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C4. Break-open prior: design and feasibility.** *Closed by C5.*
      `docs/BREAK_OPEN_PRIOR.md`.
- [x] **C5. Bottom-up `M` construction (break-open prior).** *Failed.*
      `docs/BREAK_OPEN_PRIOR.md` §8.
- [x] **C6. Re-run the compression study on the run-aware dictionary.** *Done.*
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C7. Smooth the break-open shape, or drop it.** *Dropped.*
      `docs/BREAK_OPEN_PRIOR.md`.
- [x] **C8. Tokeniser speed: precedence parser vs buckets.** *Succeeded.*
      `docs/TOKENISATION.md`.
- [x] **C9. Retarget the adjacency experiments to tree words.** *Negative.*
      `docs/HELLINGER_FACTORISATION.md`.
- [x] **C10. Structural zeros of the tree-word matrix.** *Negligible.*
      `docs/STRUCTURAL_ZEROS.md`.
- [x] **C11. Retract the break-open prior on absorbed mass.** *Rejected.*
      `docs/BREAK_OPEN_PRIOR.md` §9.
- [x] **C12. Word list: overshoot then prune by `Δ_CS`.** *Unsuccessful.*
      `docs/PRUNE_WORDS.md`.
- [x] **C13. Compress the word matrix by K-means co-clustering.** *Succeeded.*
      `docs/CLUSTER_WORDS.md`.
- [x] **C14. How large an overshoot is worth it.** *Closed.*
      `docs/PRUNE_WORDS.md`.
- [x] **C15. Adopt the pruned 2040 word list.** *No.*
      `docs/PRUNE_WORDS.md`.
- [x] **C16. Why the pruned list regresses under co-clustering.** *Closed.*
      `docs/PRUNE_WORDS.md`.
- [x] **C17. `WORD_COMPRESSIBILITY` on the pruned list.** *Cancelled.*
      `docs/PRUNE_WORDS.md`.
- [x] **C18. Cluster loss vs `k`.** *Closed.*  `docs/CLUSTER_WORDS.md`.
- [x] **C19. Compress the word × word matrix directly.** *Closed, negative.*
      `docs/MATRIX_COMPRESSION.md`.
- [~] **C20. Rank-4 factor clouds (visualisation).** *Tool ready; negative.*
      `docs/HELLINGER_FACTORISATION.md`.
- [x] **C21. Where the co-clustering loss lives.** *Closed.*
      `docs/CLUSTER_LOSS.md`.
- [x] **C22. Structure of a high-loss cluster-pair block.** *Closed,
      negative.*  `docs/CLUSTER_LOSS.md`.
- [x] **C23. Word-list size vs cluster-matrix budget.** *Closed, positive.*
      `docs/WORDLIST_BUDGET.md`.
- [x] **C24. Model size in bytes, word list included.** *Closed, positive.*
      `docs/MODEL_BUDGET.md`.
- [x] **C25. Words per identifier; Huffman vs arithmetic.** *Closed.*
      `docs/CODING_OVERHEAD.md`.
- [x] **C26. One cluster assignment for both sides.** *Adopted at `k = 32`.*
      `docs/SHARED_CLUSTERS.md`.
- [x] **C27. Reserved stop clusters.** *Rejected.*
      `docs/NEWLINE_CLUSTER.md`.
- [x] **C28. Cluster quarters.** *Rejected: `q = 1` ships.*
      `docs/CLUSTER_QUARTERS.md`.
- [x] **C29. Codesign the assignment and the code.** *Parked — negative.*  The
      code term alone, at a matched `k`, loses 1.921 bits/identifier and buys no
      bytes; only the `lambda_fit` sweep is untried.  `docs/CODESIGN.md`.
- [x] **C30. Show the clusters on the factor clouds.** *Done —*
      `scripts/factor_cloud.py --model standard/model.nvm1` colours both clouds
      by the shipped assignment (or `--clusters K` for a fresh one), numbers the
      centroids, marks the stop token, and writes the cluster as a CSV column.
      `docs/CLUSTER_WORDS.md`, `docs/HELLINGER_FACTORISATION.md`.
- [x] **C31. A factor-cloud figure for `README.md`.** *Done —*
      `docs/factor-cloud.png`: the rank-4 clouds of the shipped model coloured
      by right cluster, on the default axes with `--divide-unigram` (dividing each
      coordinate by `sqrt(p)` strips the mass trend, without which the clouds are
      one dense blob).  `README.md`.
- [x] **C32. Naming right clusters by position.** *Rejected.*
      `docs/CLUSTER_QUARTERS.md` §"The structural cost".

## D. Corpus preprocessing

- [x] **D1. Case-normalisation ablation.** *Closed, positive.*
      `docs/CASE_NORMALISATION.md`.

## E. Productisation (long-term horizon)

The distant target.  **In progress** — the encoding and the plan for the
product are settled: the packed model, the standard, both implementations
and the table-building tools are done, and the algorithm, its rejected
alternatives and a priced ablation of the model's pieces are written up.
Design intent, scope and audiences: `docs/PRODUCTISATION.md`.

- [x] **E1. Design the encoding.** *Done — designed, measured and shipped: one
      model file of 30,745 bytes, one canonical assignment, the stop as padding.*
      `docs/ENCODING.md` §6.
- [x] **E2. Write up the best algorithm.** *Done — the stages in sequence,
      from corpus to integer and back, with what each stage costs.*
      `docs/ALGORITHM.md`.
- [x] **E3. Write up rejected alternatives.** *Done — every measured negative
      in one place, with the number that killed it and the note it came from.*
      `docs/ALTERNATIVES.md`.
- [x] **E4. Ablation study.** *Done — one harness, one held-out set, one table:
      every model-side piece and case normalisation, each priced in bytes, bits
      and fit points at the operating point.*
      `docs/ABLATION.md`.
- [x] **E5. Study the 64-bit and 128-bit identifier sets.** *Done.*
      `docs/BUDGET64_STUDY.md`.
- [x] **E6. Propose a standard.** *Drafted (version 0.1): the code, the two
      sets, conformance, and how the tables are published and identified.*
      `standard/STANDARD.md`.
- [x] **E7. Reference implementation (Python).** *Done — a package, not a
      script: `pip install .`, a `varnames` console script, tests, and the
      held-out rate reproduced exactly (45.218 bits, 85.0 % / 99.0 %).*
      `python/`.
- [x] **E8. Engineering implementation (Rust).** *Done — a crate with no
      dependencies; the standard tables are compiled in and digest-checked; the
      CLI mirrors the Python one.*  `rust/`.
- [x] **E9. Standard vs custom tables.** *Done — `Codec(Model.from_path(p))`
      and `--model PATH` on both sides; the digest is how a deployment finds
      out it is not on the standard.*  `standard/STANDARD.md` §9.
- [x] **E10. Publish table-building tools.** *Done — one command from a corpus
      to a `model.nvm1`, priced stage by stage; run over the full corpus it
      reproduces the shipped file byte for byte, digest and all.*
      `docs/BUILDING.md`.
- [x] **E11. Licence.** *Settled — `MIT OR Apache-2.0` for the code and the
      specification, `CC0-1.0` for the derived corpus and the published tables.*
      `README.md`.

## Housekeeping / deferred regenerations

- [x] **H1. Rebuild the pair statistics and factors with `n_iter = 8`.**
      *Done — all five thresholds; log `work/afk_pairmatrix.log`.*
- [x] **H2. Corpus hardening.** *Done.*  `docs/CORPUS.md`.
- [x] **H3. Broaden the corpus.** *Done.*  `docs/CORPUS.md`.
- [x] **H4. Rebuild the corpus inputs.** *Done.*  `work/common<T>` was rebuilt
      from `work/camel/merged.txt` and reproduces the counts in
      `docs/CASE_NORMALISATION.md` (278, 613, 1,788, 3,935, 8,038, 20,198,
      40,168, 80,869 for `T` = 100k … 500).  The derived files beside them
      (`clusters.tsv`, `code_lengths.tsv`) predate the rebuild and feed nothing
      current.  The pre-change corpus is archived at commit `7228753`.
- [x] **H5. Rebuild the model artefacts.** *Done for the grid; the legacy
      artefacts are not rebuilt.  See the build key below.*
- [x] **H7. Rationalise the `(V, k)` grid.** *Done — the grid is
      `V ∈ {4096, 6144, 8192}`, `k` chosen per `V`; `V = 512` is testing-only.*
      `docs/MODEL_BUDGET.md` §7, `docs/WORDLIST_BUDGET.md`.
- [x] **H9. Restructure the documentation.** *Done.*  `README.md`.
- [x] **H10. Reconcile the codebook accounting.** *Settled.*
      `docs/CLUSTER_QUARTERS.md`, `docs/MODEL_BUDGET.md`.
- [x] **H11. A complete review of the model-size accounting.** *Done.*
      `docs/MODEL_BUDGET.md` §5–§7.
- [x] **H12. Encode and decode the model file.** *Done for the shipped
      layout; the published table-building tool is E10.*
      `standard/MODEL_FORMAT.md`.
- [x] **H13. Choose the encoding of the rule list.** *Done — a static
      base-2 geometric ladder, `b = 3`, on two child indices.*
      `docs/RULE_ENCODING.md`, `standard/MODEL_FORMAT.md` §4.
- [x] **H14. A 4-bit depth field by biasing the weights.** *Adopted — a
      searched bias, the offset recovered from Kraft.*
      `standard/MODEL_FORMAT.md` §3.1.
- [x] **H15. Retire the arithmetic *sizes*, keep the arithmetic *argument*.**
      *Done — and the distinction is the point.*  `MODEL_BUDGET.md` prices the
      Huffman file only, and the frontier there is measured.  `CODING_OVERHEAD.md`
      is **not** retired: it is where arithmetic coding is rejected, on the
      zero-padded stop putting Huffman about a bit per identifier ahead and
      lifting the 64-bit fit rate ~1.5 points, and that argument stands on its
      own numbers.  What was retired is arithmetic *sizes* being read as the
      model's size — the `assoc` sweep of `CLUSTER_WORDS.md` is a comparison of
      factorisations and is labelled as one.  `docs/MODEL_BUDGET.md` §7, step 6;
      `docs/BUDGET64_STUDY.md` §1.

## Build-directory key (`work/` is gitignored, so the key lives here)

Model artefacts are `work/tw<V><flag>/` (`dict.txt`, `sym.npy`, `adj.npz`,
`meta.json`), with `V = NUM_PAIRS + 64`.

| flag | dictionary | adjacency | note |
|---|---|---|---|
| *(none)* | `--sample 20` | all lines | legacy: pre-split corpus (2.07M lines), no new work |
| `ns` | `--sample 20` | `--stride 0` | the H5 set; "ns" = *no stride* for the adjacency |
| `s0` | `--sample 0` | `--stride 0` | never-sampled twin: proves the dictionary does not depend on the 1-in-20 sample |

`ns` is not "no sampling" — the dictionary is still built from every 20th line,
which is what makes the build affordable.  `p` = pruned word list, `raw` =
pre-case-normalisation corpus, `_ttw*` = scratch.
