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
- [ ] **A8. Rescan-based dictionary builder** (deferred): drop the position
      index for a global per-merge rescan. Prototype `scripts/word_build_rescan.py`
      gives an identical word list and is ~2× faster / ~30 % lighter on the
      stride-20 sample; adopt only after a stride-0 timing.
      `docs/TREE_WORDS.md`.
- [ ] **A9. No run words** (deferred): never build a run word, not even `(uu)`,
      so a doubled character is absorbed only through a neighbouring pair word.
      Measure the held-out cost, especially the 64/128-bit *fit rates* rather
      than the mean.  Middle ground (allow `(uu)` only for isolated length-2
      runs, never longer) is nearly the current rule, since 99 % of runs are
      length 2.  `docs/RUN_LENGTHS.md`, `docs/WORD_COMPRESSIBILITY.md`.

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
      `docs/HELLINGER_FACTORISATION.md`, `scripts/matrix_compress.py`.
- [~] **C20. Rank-4 factor clouds (visualisation).** *Tool ready* — plot the
      left/right `√M_ref` factorisation as 3D point clouds to look for structure
      worth compressing.  `scripts/factor_cloud.py`,
      `docs/HELLINGER_FACTORISATION.md`.
- [ ] **C21. Where the co-clustering loss lives** (deferred): attribute the
      `assoc`-vs-word×word loss to each (left cluster, right cluster) pair — is
      it concentrated in the high-mass pairs, the tail, or the junk clusters?
      `docs/CLUSTER_WORDS.md`.
- [ ] **C22. Structure of a high-loss cluster-pair block** (deferred): for a
      chosen `(a, b)`, study `P(u, v | a, b)` — is the block low-rank, or a
      sparse deviation from its marginal?  Feasibility of a per-cluster-pair
      "splat" model for the whole matrix.  `docs/CLUSTER_WORDS.md`.
- [ ] **C23. Word-list size vs cluster-matrix budget** (deferred): spend more on
      the word list (e.g. 4478 or 11758 words) and less on the `k × k` matrix;
      compression improves with the word list even at constant `k`.  Note the
      memory obstacle: `V = 11758` makes a dense `V²` matrix ~1.1 GB, so this
      needs a sparse/streaming path.  `docs/CLUSTER_WORDS.md`,
      `docs/WORD_COMPRESSIBILITY.md`.

## D. Corpus preprocessing

- [x] **D1. Case-normalisation ablation.** *Closed, positive* — normalisation
      helps; it is injective within a class, so the class must be kept to invert
      it (all 3.0 % "collapses" are cross-class).  `docs/CASE_NORMALISATION.md`,
      `scripts/case_ablation.py`, `scripts/camelize_identifiers.py`.

## E. Productisation (long-term horizon)

The distant target. **Not started** — recorded so the research lines above can be
steered toward it. Order roughly as listed; the encoding (E1) and the write-ups
(E2–E4) precede the standard (E6). Design intent, scope and audiences:
`docs/PRODUCTISATION.md`.

- [ ] **E1. Design the encoding.** Little-endian; the stop token is a zero-length
      code placed beyond the target compressed length (64 or 128 bits).
- [ ] **E2. Write up the best algorithm** — corpus, case normalisation, word
      list, tokenisation, adjacency matrix, clustering, encoding.
- [ ] **E3. Write up rejected alternatives** — reframe the gathered data as
      justifications for the design decisions.
- [ ] **E4. Ablation study** (design TBD).
- [ ] **E5. Study the 64-bit and 128-bit identifier sets** — what fraction of
      real identifiers fit; longest compressed length that fits vs shortest
      uncompressed length that does not; use the model generatively to ask what
      random identifiers look like.
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
- [ ] **H2. Corpus hardening** (deferred, optional): Ruby heredoc markers /
      UUID fixtures.
- [ ] **H3. Broaden the corpus** (deferred): add Java/Lua/OCaml/Haskell
      harvests; keep a stable versioned snapshot for a later full rebuild.
      `docs/CORPUS.md`.
