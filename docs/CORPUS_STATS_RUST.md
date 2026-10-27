# Rust corpus statistics

Identifiers harvested from Rust crates published on [crates.io](https://crates.io),
using the shared streaming tokeniser (`scripts/extract.py`) with the ASCII identifier
regex `[A-Za-z_][A-Za-z0-9_]*`.

## Summary

| metric | value |
|---|---|
| crates listed | 2,500 |
| crates downloaded | 2,500 |
| crates unpacked | 2,500 |
| `.rs` files scanned | 64,650 |
| distinct identifiers | **1,290,194** |

## Method

* **Source list:** crates.io API `/api/v1/crates?page=N&per_page=100&sort=downloads`
  (pages 1–25), no auth, custom `User-Agent`. Up to 2,500 crates collected; for each
  we used `max_stable_version` (falling back to `max_version`). Saved to
  `work/rust_crates.txt` as `name version` lines.
* **Download:** `https://static.crates.io/crates/NAME/NAME-VERSION.crate`, fetched
  with `xargs -P32` and `curl --max-time 60`, into `work/rust_dl/`.
* **Unpack:** each `.crate` is a gzipped tarball with top directory `NAME-VERSION/`,
  extracted into `work/rust_src/`. Corrupt/truncated archives are skipped; already
  unpacked directories are not re-extracted.
* **Extraction:** `python3 scripts/extract.py work/clean_ids/rust.shards work/rust_src
  --exts .rs --threshold 400000`. Walks the tree, keeps `.rs` files, skips files
  containing NUL bytes (treated as binary), and writes the distinct token set
  one-per-line, memory-bounded via the shard threshold.
* **Finalize:** `LC_ALL=C sort -u work/clean_ids/rust.shards > corpus/by_language/rust.txt`.

## Validation

| check | value | requirement |
|---|---|---|
| empty lines in `corpus/by_language/rust.txt` | 0 | must be 0 |
| tokens violating `^[A-Za-z_][A-Za-z0-9_]*$` | 0 | must be 0 |

Both checks pass.

## Failures / skips

* **Downloads:** the parallel batch initially missed one crate (`v8-152.2.0`); it was
  re-fetched explicitly with a longer timeout and succeeded. Final download count is
  **2,500 / 2,500** (no permanent failures).
* **Unpack:** no corrupt or truncated archives were encountered; all 2,500 archives
  unpacked and each unpacked tree contains a top-level `Cargo.toml`.
* **Scan skips:** `find` located 64,651 `.rs` files; the tokeniser scanned 64,650,
  i.e. **1 file was skipped** for containing NUL bytes (binary content).
* Throughput was network-bound as expected; the bounded 2,500-crate sample completed
  within budget (≈374 MB of archives, ≈2.4 GB unpacked).
