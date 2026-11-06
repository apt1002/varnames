# Plan — parallel lines of research

Living index of the open threads. Each line gets a one-line status and a
pointer to the document that owns it. `[ ]` = open, `[~]` = in progress,
`[x]` = done.

This file records **execution status and success/failure only** — the design
notes and the results live in the experiment reports (`docs/*.md`), which the
lines below point to. Plan identifiers (`A1`, `B1`, `C5`, …) are local to this
document: reports and filenames refer to experiments by *name*, never by these
labels (see `README.md`).

## Standing background (done, load-bearing)

- [x] Corpus build + case normalisation — `docs/CORPUS.md`,
      `docs/CASE_NORMALISATION.md`.
- [x] Character-level fixed-budget compressibility — `docs/CODE_LENGTHS.md`.
- [x] Square-root (Hellinger) factorisation + unobserved-pairs counting fix —
      `docs/HELLINGER_FACTORISATION.md`.
- [x] Choosing `k` and `N` for the model size — `docs/CLUSTER_SIZE_STUDY.md`.
- [x] Dictionary (pair-merge) model: CS identity, per-merge delta —
      `docs/TREE_WORDS.md`, `scripts/check_merge_delta.py`.
- [x] Typical run lengths of the corpus — `docs/RUN_LENGTHS.md`,
      `scripts/run_lengths.py`.
- [x] Tokeniser speed (precedence parser vs ascending-rank buckets) —
      `docs/TOKENISATION.md`, `scripts/tokenizer_bench.py`.

## A. Dictionary / pair-merge theory (`docs/TREE_WORDS.md`)

- [x] **A1. Prove `Δ < 0` exactly.** *Solved* for a distinct-pair merge; the
      doubled word stays outside the proof (the run-aware rule never does it).
      `docs/TREE_WORDS.md` §9.0, `scripts/check_merge_delta.py`.
- [x] **A2. Relax "no threefold repetition"** (run-aware rule). *Succeeded* —
      sign-safe; `docs/TREE_WORDS.md` §9.1.
- [x] **A3. Greedy alternative** (largest `Δ` vs most frequent pair).
      *Succeeded: the frequency rule is the robust proxy.*
      `docs/DICTIONARY_RULES.md`.
- [x] **A4. `(uv)` vs `(u^n)` crossover.** *Succeeded* — the run-aware rule
      wins whenever there is run mass; `docs/DICTIONARY_RULES.md`.
- [x] **A5. Rewrite `TREE_WORDS.md` for pedagogy.** *Done.*
- [x] **A6. Run-fusion theory** (mirror A1 for runs). *Solved* — a run collapse
      never enlarges `CS`.  `docs/TREE_WORDS.md` §9.1,
      `scripts/check_merge_delta.py`.
- [x] **A7. Boundary words (`v\n`).** *Negative* — not worth it; not adopted.
      `docs/BOUNDARY_TRIGRAM.md`, `scripts/boundary_trigram.py`.
- [x] **A8. Rescan-based dictionary builder.** *Done and adopted.*  The builder
      and the bigram counter are now streaming and array-based in
      `scripts/tree_words.py` (`read_corpus_array`, `build_dictionary_arr`,
      `count_adjacency_stream`): the packed array replaces the position index,
      and the adjacency count no longer materialises the corpus.  Output is
      identical to the old path (checked by `scripts/word_build_rescan.py`), and
      the full canonical-grid rebuild now fits in this box.  `docs/TREE_WORDS.md`
      §11.
- [x] **A9. No run words.** *Succeeded — a simplification at no cost.*
      Self-merge is forbidden outright: no `('run', …)` rule can be produced, so
      a doubled character is absorbed only through a pair word that also
      contains a neighbour.  At the vocabularies in use the held-out score and
      the co-clustered fit rates are unchanged;
      at the smallest vocabulary the no-run list is slightly *better*.  The run
      machinery (run rule, run-length table, run replay in the tokeniser) is
      therefore deleted.  `docs/DICTIONARY_RULES.md`,
      `docs/TREE_WORDS.md`, `scripts/tree_words.py`,
      `scripts/check_tree_words.py`.

## B. Adjacency matrix construction

- [x] **B1. Canonical `docs/ADJACENCY_MATRIX.md`** (how to build the matrix,
      choice of `κ`). *Done* — the experiment docs refer to it.

## C. Apply the dictionary model to `merged.txt`

- [x] **C1. Word × word adjacency counts** (run-aware tokenisation).
      *Done* — `scripts/tree_words.py train`.
- [x] **C2. Fill unobserved adjacencies** with the `κ` prior.
      *Done* — `scripts/tree_words.py score`; best `κ` in
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C3. Held-out compressibility.** *Succeeded* — the word model wins at
      equal dictionary size; `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C4. "Breaking open the pair" prior** — design + feasibility pass.
      *Plausible but modest; adopted only if it wins held-out likelihood*
      (resolved by C5). `docs/BREAK_OPEN_PRIOR.md`.
- [x] **C5. Bottom-up `M` construction (break-open prior).** *FAILED — the
      prior LOSES to `P_mar` at every size and `κ`; not adopted.*
      `docs/BREAK_OPEN_PRIOR.md` §8, `scripts/break_open_prior.py`.
- [x] **C6. Re-run C1–C3 on the run-aware dictionary** (C5's baseline).
      *Done* — `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C7. Smooth the break-open shape, or drop it.** *DROPPED (not needed).*

- [x] **C8. Tokeniser speed: precedence parser vs buckets.** *Succeeded* — the
      bucket parser is production. `docs/TOKENISATION.md`.
- [x] **C9. Re-target the adjacency experiments to tree words.** *Negative* —
      the Hellinger factorisation loses to the full table.
      `docs/HELLINGER_FACTORISATION.md`, `scripts/hfactor_words.py`.
- [x] **C10. Structural zeros of the tree-word matrix in `M_mar`/`P_mar`.**
      *Done — NEGLIGIBLE.* `docs/STRUCTURAL_ZEROS.md`.
- [x] **C11. Retract the break-open prior on absorbed row/column mass.**
      *Tested (`--shrink prop|hard`): REJECTED.* `docs/BREAK_OPEN_PRIOR.md` §9.
- [x] **C12. Word list: overshoot then prune by `Δ_CS`.** *Unsuccessful* —
      worse once the matrix is co-clustered; not adopted.
      `docs/PRUNE_WORDS.md`, `scripts/prune_words.py`.
- [x] **C13. Compress the word adjacency matrix by K-means co-clustering.**
      *Succeeded.* `docs/CLUSTER_WORDS.md`, `scripts/cluster_words.py`.
- [x] **C14. How large an overshoot is worth it?** *Closed* — 512 and 2040
      suffice; no further sweep. `docs/PRUNE_WORDS.md`.
- [x] **C15. Adopt the pruned 2040 word list?** *No.*
      `docs/PRUNE_WORDS.md`, `scripts/prune_words.py`.
- [x] **C16. Why the pruned list regresses under co-clustering.** *Closed* —
      objective mismatch; recomputation cancelled. `docs/PRUNE_WORDS.md`.
- [x] **C17. `WORD_COMPRESSIBILITY.md` on the pruned list.** *Cancelled.*
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C18. Cluster loss vs `k`.** *Closed* — the loss is essentially
      unavoidable for the block model. `docs/CLUSTER_WORDS.md`,
      `scripts/cluster_words.py`.
- [x] **C19. Compress the word × word matrix directly.** *Closed, negative* —
      the residual is not sparse; at matched store a top-`N` table only ties the
      block model, and that tie reverses once the cost of naming the coded cells
      is counted; no compact near-lossless table.
      `docs/MATRIX_COMPRESSION.md`, `scripts/matrix_compress.py`.
- [~] **C20. Rank-4 factor clouds (visualisation).** *Tool ready* — plot the
      left/right `√M_ref` factorisation as 3D point clouds to look for structure
      worth compressing.  First shape/gain test built (`scripts/shape_gain_test.py`):
      the apparent "gain × shape" factorisation does **not** survive a
      pipeline-matched null — it is largely a low-rank reconstruction artefact.
      `scripts/factor_cloud.py`, `docs/HELLINGER_FACTORISATION.md`.
- [x] **C21. Where the co-clustering loss lives.** *Closed* — the loss is spread
      across the whole low-mass tail rather than concentrated in a few bad
      cells, the junk clusters carry nothing, and on part of the bigrams the
      block model *beats* the table.  `docs/CLUSTER_LOSS.md`,
      `scripts/cluster_loss_attribution.py`.
- [x] **C22. Structure of a high-loss cluster-pair block.** *Closed, negative for
      per-block corrections* — the loss is the within-left-cluster heterogeneity
      (the clustering residual); the worst blocks are neither low-rank nor
      sparsely deviating from the row-independent marginal (the deviation
      concentration matches a permutation null), so a per-cell "splat" would
      cost as much as the block.  `docs/CLUSTER_LOSS.md`,
      `scripts/block_structure.py`.
- [x] **C23. Word-list size vs cluster-matrix budget.** *Closed, positive* —
      at matched model size the largest word list that fits beats a finer `k`;
      the word list, not the table, is the dominant budget lever.
      `docs/WORD_COMPRESSIBILITY.md`, `docs/CLUSTER_WORDS.md`,
      `scripts/wordlist_budget.py`.
- [x] **C24. Model size in bytes, word list included.** *Closed, positive* — the
      word list is small next to the cluster table once `k` grows, so the
      "buy words, keep `k` small" conclusion holds in bytes; one-byte
      quantisation of the probabilities is free; it is the clustering, not the
      size, that costs the 64-bit fit.  `docs/MODEL_BUDGET.md`,
      `scripts/model_budget.py`, `scripts/model_fit_rates.py`.

- [x] **C25. Words per identifier; Huffman vs arithmetic.** *Closed* — the
      Huffman penalty is small and is not a size argument; a two-stage code
      costs more than a joint one per left cluster.  The joint tree is
      unaffordable at the canonical vocabularies, which is what C28 is for.
      `docs/CODING_OVERHEAD.md`, `scripts/words_per_identifier.py`.

- [x] **C26. One cluster assignment for both sides.** *Adopted at the canonical
      grid; rejected at the testing point, where the byte frontier is too cheap
      for the saving to be worth a fit point.* `docs/SHARED_CLUSTERS.md`,
      `scripts/shared_clusters.py`.
- [x] **C27. Reserved stop clusters.** *Rejected — cheap but inert; the exact
      boundary table it would replace cannot pay for itself.  The sample-0
      dictionaries stay plain.* `docs/NEWLINE_CLUSTER.md`,
      `scripts/newline_cluster.py`.
- [x] **C28. Cluster quarters.** *Adopted at `q = 2`, rejected at `q = 4`.*  It
      is a Huffman-only optimisation: it wins on the 64-bit threshold, not on
      mean bits, and its value is largest at a coarse `k`.  Open follow-up:
      re-measure with the rest at H6. `docs/ENCODING.md` §5,
      `scripts/quarter_accounting.py`, `scripts/quarter_codes.py`.
- [ ] **C29. Codesign the assignment and the code.** *Planned, re-scoped* —
      collapse clustering and Huffman building into one greedy merge loop over
      cells, keyed on the fit loss, the code-length increase and the model bytes
      freed, so that `k` falls out of the trade instead of being swept.  The
      target is the *model* term: the code side is now measured as exhausted
      (C28), while the gap to the exact conditional is large and unimplemented.
      `docs/ENCODING.md` §6.

## D. Corpus preprocessing

- [x] **D1. Case-normalisation ablation.** *Closed, positive* — normalisation
      helps; it is injective within a class, so the class must be kept to invert
      it (all collapses are cross-class).  `docs/CASE_NORMALISATION.md`,
      `scripts/case_ablation.py`, `scripts/camelize_identifiers.py`.

## E. Productisation (long-term horizon)

The distant target. **Not started** — recorded so the research lines above can be
steered toward it. Order roughly as listed; the encoding (E1) and the write-ups
(E2–E4) precede the standard (E6). Design intent, scope and audiences:
`docs/PRODUCTISATION.md`.

- [~] **E1. Design the encoding.** *Started* — little-endian; the stop token is
      the all-zeros Huffman codeword, never written, so the zero padding past the
      budget *is* the terminator (an arithmetic coder cannot do this and must
      encode the stop); the standard publishes the code rather than the
      probabilities.  Still open: which tables ship, and the quarter and cluster
      choices.  `docs/ENCODING.md`.
- [ ] **E2. Write up the best algorithm** — corpus, case normalisation, word
      list, tokenisation, adjacency matrix, clustering, encoding.
- [ ] **E3. Write up rejected alternatives** — reframe the gathered data as
      justifications for the design decisions.
- [ ] **E4. Ablation study** (design TBD).
- [x] **E5. Study the 64-bit and 128-bit identifier sets.** *Done* — the
      64-bit set covers 71–83 % of distinct identifiers over 17–85 kB (128-bit
      97–99 %); membership is not a length rule (failures are unpredictable
      names of ordinary length, and a larger vocabulary widens the overlap);
      model samples reproduce the identifier shape but ~98 % are unreal and the
      generative tail is heavier than the corpus.  `docs/BUDGET64_STUDY.md`,
      `scripts/budget64_study.py`.
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
- [ ] **E11. Licence** — permissive.

## Housekeeping / deferred regenerations

- [x] **H1. Rebuild `work/*/pair_stats.txt` and `pair_factors_L*.npy`** with the
      raised `randomized_svd` `n_iter=8` default. *Done* — all 5
      `PAIR_THRESHOLDS`; log `work/afk_pairmatrix.log`.
- [x] **H2. Corpus hardening.** *Done — re-extracted into `work/newcorpus/`.*
      Audited the production scrubber against the retained trees
      (`scripts/audit_extract.py` scans with `extract.scrub` and reports files
      whose *output* still carries hex-blob / digit-blob tokens), fixed the
      missed literal constructs in `scripts/extract.py` by rule, added
      `scripts/check_extract.py` as a regression suite, then found and fixed a
      second-order bug the fix itself introduced (the multi-line regex matcher
      opening inside ordinary strings) — also pinned by a test.  All six
      existing ecosystems are re-extracted; the live `corpus/` is still
      untouched, so swapping it in is part of the rebuild below.
      `docs/CORPUS.md`, `scripts/extract.py`, `scripts/audit_extract.py`,
      `scripts/check_extract.py`.
- [~] **H3. Broaden the corpus.** *Harvests done, extraction not started.*
      Download counts are not published by any of the four registries, so the
      top-2,000 cap is applied through the best available popularity proxy per
      ecosystem — reverse dependencies for Haskell (Hackage) and OCaml (opam),
      version count for Lua (LuaRocks), `org/apache` `-sources.jar` for Java
      (Maven Central).  Harvesting is a resumable `plan`/`fetch` pair
      (`scripts/harvest_packages.py`); archives are deleted after extraction;
      no host toolchain is needed because source is harvested, not built.
      `docs/CORPUS.md`.

### Rebuilds the corpus change (H2/H3) will force

The pre-change corpus is archived in git (`corpus/` at commit `7228753`), so
these can be rebuilt in any order, later, without losing the old numbers.

- [ ] **H4. Rebuild the corpus inputs** (deferred, blocked on H2/H3):
      `work/clean_ids/*.shards`, `corpus/by_language/*.txt`,
      `corpus/identifiers.multilang.txt`, then `work/raw/` and `work/camel/`
      (case-normalised variants + `merged_training.txt` /
      `merged_validation.txt` from `scripts/split_corpus.py`), `work/tokcache/`.
- [ ] **H5. Rebuild the model artefacts** (dictionaries done for the whole
      canonical grid plus the `s0` twins; the remaining artefacts are): the
      dictionaries on the canonical grid (H7, which now includes an
      intermediate `V`) and their `s0` twins
      (`dict.txt`, `sym.npy`, `adj.npz`, `meta.json`), the case-ablation and
      break-open variants of the canonical `V`, `_ttw*` scratch dirs, the pair
      matrix (`work/*/pair_stats.txt`, `pair_factors_L*.npy` via
      `scripts/pair_matrix.py`), and `work/occ/`.
- [ ] **H6. Re-measure the corpus-dependent reports** (deferred, blocked on H5):
      the numbers (not the arguments) in `docs/CORPUS.md`, `CODE_LENGTHS.md`,
      `CASE_NORMALISATION.md`, `ADJACENCY_MATRIX.md` (κ choice),
      `TREE_WORDS.md`, `DICTIONARY_RULES.md`, `RUN_LENGTHS.md`,
      `WORD_COMPRESSIBILITY.md`, `BOUNDARY_TRIGRAM.md`,
      `CLUSTER_SIZE_STUDY.md`, `CLUSTER_WORDS.md`, `CLUSTER_LOSS.md`,
      `MATRIX_COMPRESSION.md`, `PRUNE_WORDS.md`, `BREAK_OPEN_PRIOR.md`,
      `STRUCTURAL_ZEROS.md`, `CODING_OVERHEAD.md`, `MODEL_BUDGET.md`,
      `BUDGET64_STUDY.md`, the measurements in `SHARED_CLUSTERS.md`,
      `NEWLINE_CLUSTER.md` and `ENCODING.md`, and the headline figures in
      `README.md`/`PLAN.md`.
- [ ] **H8. Charge the dictionary term in every byte table.** *Half done* —
      `k_frontier.py` and `MODEL_BUDGET.md` now include the rule table; the
      pricing in `shared_clusters.py`, `quarter_accounting.py` and the C26–C28
      comparisons still quote code-side bytes.  The verdicts are unaffected
      (they are within-`V`), but any cross-`V` price must carry the term.
      `docs/MODEL_BUDGET.md` ("What the byte numbers include").
- [ ] **H7. Rationalise the `(V, k)` grid.** *Partly done* — the grid is now
      `V ∈ {512, 4096, 6144, 8192}` (`NUM_PAIRS` 448, 4032, 6080, 8128; 512 is
      for testing only), and the measured operating points replace the old
      `k ∈ {32, 64}` default; see `docs/MODEL_BUDGET.md` for the frontier.  The old sweep (`V` 96/2040/4414/11694, `k`
      26/52/105/210) is retired from the rebuild; H4/H5 build this grid only and
      H6 re-measures at it.  Testing at `V = 512` uses `k = 16` only; anything
      measured there is labelled testing-only.

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
