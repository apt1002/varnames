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
- [x] **C28. Cluster quarters.** *Adopted at `q = 2`; rejected at `q = 4`.*
      `docs/CLUSTER_QUARTERS.md`.
- [ ] **C29. Codesign the assignment and the code.** *Planned, re-scoped to the
      model term.*  `docs/CODESIGN.md`.
- [ ] **C30. Show the clusters on the factor clouds.** *Planned.*  Colour
      `scripts/factor_cloud.py` by the shared assignment, so the co-clustering
      can be seen rather than inferred.  `docs/CLUSTER_WORDS.md`,
      `docs/HELLINGER_FACTORISATION.md`.
- [ ] **C31. A factor-cloud figure for `README.md`.** *Blocked on the final
      model.*  The two clouds of the adopted model, coloured by cluster, as
      illustration.  `README.md`.

## D. Corpus preprocessing

- [x] **D1. Case-normalisation ablation.** *Closed, positive.*
      `docs/CASE_NORMALISATION.md`.

## E. Productisation (long-term horizon)

The distant target.  **Not started** — recorded so the research lines above can
be steered toward it.  Design intent, scope and audiences:
`docs/PRODUCTISATION.md`.

- [~] **E1. Design the encoding.** *In progress — designed; which tables ship
      is still open.*  `docs/ENCODING.md`.
- [ ] **E2. Write up the best algorithm** — corpus, case normalisation, word
      list, tokenisation, adjacency matrix, clustering, encoding.
- [ ] **E3. Write up rejected alternatives** — the gathered data as
      justifications for the design decisions.
- [ ] **E4. Ablation study** (design TBD).
- [x] **E5. Study the 64-bit and 128-bit identifier sets.** *Done.*
      `docs/BUDGET64_STUDY.md`.
- [ ] **E6. Propose a standard** — a language-neutral bijection between
      identifiers and integers; define the 64-bit and 128-bit sets; decide how
      to publish the lookup tables. (Hash fallback is out of scope.)
- [ ] **E7. Reference implementation (Python)** — runnable, readable; for people
      porting the library.
- [ ] **E8. Engineering implementation (Rust)** — runnable, readable; for people
      writing compilers.
- [ ] **E9. Standard vs custom tables** — both implementations default to the
      standardised tables but accept non-standard tables. (Hash fallback still
      out of scope.)
- [ ] **E10. Publish table-building tools** — easy to use and modify; need not
      be language-neutral.
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
- [ ] **H7. Rationalise the `(V, k)` grid.** *Partly done — the grid is fixed at
      `V ∈ {4096, 6144, 8192}`; `V = 512` is testing-only.*
      `docs/MODEL_BUDGET.md`, `docs/SMALL_DICT.md`.
- [x] **H9. Restructure the documentation.** *Done.*  `README.md`.
- [x] **H10. Reconcile the codebook accounting.** *Settled.*
      `docs/CLUSTER_QUARTERS.md`, `docs/MODEL_BUDGET.md`.
- [ ] **H11. A complete review of the model-size accounting.** *Planned — the
      six-step size oracle.*  `docs/MODEL_BUDGET.md` ("The size oracle").
- [ ] **H12. Encode and decode the model file.** *Planned — the YAML format is
      specified; the YAML ⇄ binary codec and the measurement of the binary are
      the work.  Feeds the oracle (H11) and the published table-building tools
      (E10).*  `docs/MODEL_FORMAT.md`.

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
