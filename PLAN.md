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

- [x] **A1. Prove `Δ ≤ 0` exactly.** *Solved (distinct pairs)* — for `u ≠ v`,
      `Δ ≤ R[H(p) − H(α) − H(β)] ≤ 0` by Jensen on the two context sums plus
      subadditivity, and the equality condition is the §7.1 sufficient
      condition.  The doubled word is the only case outside the proof (the
      run-aware rule never performs it). `docs/TREE_WORDS.md` §9.0,
      `scripts/check_merge_delta.py`.
- [x] **A2. Relax "no threefold repetition"** (run-aware rule). *Succeeded* —
      sign-safe; `docs/TREE_WORDS.md` §9.1.
- [x] **A3. Greedy alternative** (largest `Δ` vs most frequent pair).
      *Succeeded: the frequency rule is the robust proxy.*
      `docs/DICTIONARY_RULES.md`.
- [x] **A4. `(uv)` vs `(u^n)` crossover.** *Succeeded* — the run-aware rule
      wins whenever there is run mass; `docs/DICTIONARY_RULES.md`.
- [x] **A5. Rewrite `TREE_WORDS.md` for pedagogy.** *Done.*
- [ ] **A6. Run-fusion theory** (mirror A1 for runs). *Empirical only* — a
      symbolic proof and the `Δ = 0`-under-Markov question are open.
      `docs/TREE_WORDS.md` §9.1.
- [x] **A7. Boundary words (`v\n`).** *Negative* — not worth it; not adopted.
      `docs/BOUNDARY_TRIGRAM.md`, `scripts/boundary_trigram.py`.
- [ ] **A8. Rescan-based dictionary builder** (deferred): drop the position
      index for a global per-merge rescan. Prototype `scripts/word_build_rescan.py`
      gives an identical word list and is ~2× faster / ~30 % lighter on the
      stride-20 sample; adopt only after a stride-0 timing.
      `docs/TREE_WORDS.md`.

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
- [x] **C18. Cluster loss vs `k`.** *Closed* — the loss closes smoothly with no
      knee; ~1 bit only at `k ≈ V/2` (~25 % of the matrix), so it is essentially
      unavoidable for the block model. `docs/CLUSTER_WORDS.md`,
      `scripts/cluster_words.py`.
- [x] **C19. Compress the word × word matrix directly.** *Closed* — the residual
      is not sparse (a rank-256 fit spreads 90% of its error over 19% of `V²`),
      and top-`N` cells over a flat floor stays within ~1 bit only at `N ≈ 300K`
      (`tw2040`, ~15× smaller than `V²`).  Neither clustering nor direct coding
      gives a compact, near-lossless table.
      `docs/HELLINGER_FACTORISATION.md`, `docs/CLUSTER_WORDS.md`,
      `work/c19_matrix.py`, `work/c19_hybrid.py`, `work/c19_cluster_hybrid.py`.

## D. Corpus preprocessing

- [x] **D1. Case-normalisation ablation.** *Closed* — normalisation helps: a
      paired test on the CamelCase subset (identical strings) is 5.4 bits
      shorter when trained on the normalised corpus; it must be applied
      consistently (raw input costs +14 bits).  Caveat: lossy (3.0% of ids
      collapse), so exact raw recovery would need the case pattern.
      `docs/CASE_NORMALISATION.md`, `scripts/case_ablation.py`.

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
