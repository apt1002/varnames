# Local Corpus Statistics (offline harvest)

Distinct ASCII programming-language identifiers harvested **offline** (no network)
from language sources already installed on this Debian machine.

Identifier definition: a token matching the ASCII regex `[A-Za-z_][A-Za-z0-9_]*`,
extracted lexically from raw file bytes.

Extractor: `scripts/extract.py` (used read-only), invoked as
`python3 scripts/extract.py OUT.shards ROOT [ROOT ...] --exts ... --threshold 400000`,
then de-duplicated with `LC_ALL=C sort -u`.

## Per-language counts

| Language   | Source roots                                                        | Files scanned | Distinct identifiers | Violations |
|------------|---------------------------------------------------------------------|---------------|----------------------|------------|
| Go         | `/usr/share/go-1.24/src`                                            | 7,115         | 154,229              | 0          |
| Python     | `/usr/lib/python3.13`, `/usr/lib/python3/dist-packages`             | 13,710        | 363,927              | 0          |
| JavaScript | `/usr/share/javascript`                                             | 2,786         | 10,049               | 0          |
| Perl       | `/usr/share/perl5`, `/usr/lib/aarch64-linux-gnu/perl5`              | 752           | 17,304               | 0          |

## Union total

Grand total of distinct identifiers across the union of all four files:

```
cat corpus/by_language/*.txt | LC_ALL=C sort -u | wc -l
527316
```

## Method

Each source file is lexically scrubbed before tokenisation: string literals
(quoted, triple-quoted, raw, backtick), comments, heredocs, regex literals,
numeric literals and non-ASCII runs are replaced by spaces so that base64 blobs,
PEM data, URLs, English prose and the tails of hex/binary/decimal literals never
reach the corpus. The scrubbed buffer is then tokenised.

For each language, `scripts/extract.py` recursively walked the listed roots,
kept only files whose extension was in the language's extension set, skipped any
file containing NUL bytes (binary), and streamed the distinct token set to
`work/clean_ids/<lang>.shards` using a 400,000-token flush threshold to bound
memory. The shard file was then sorted and de-duplicated with
`LC_ALL=C sort -u` into `corpus/by_language/<lang>.txt`.

Per-language extension sets: Go `.go`; Python `.py,.pyi,.pyx`; JavaScript
`.js,.mjs,.jsx`; Perl `.pl,.pm`.

## Missing / skipped paths

All requested roots existed and were scanned:
`/usr/share/go-1.24/src`, `/usr/lib/python3.13`, `/usr/lib/python3/dist-packages`,
`/usr/share/javascript`, `/usr/share/perl5`, `/usr/lib/aarch64-linux-gnu/perl5`.
No root paths were missing. Individual files within the trees may have been skipped
by the extractor for being binary (containing NUL bytes), for having an extension
outside the per-language set, or for unreadable/permission errors (OSError).

## Validation

| File                              | Empty lines | Non-matching / violating lines |
|-----------------------------------|-------------|--------------------------------|
| `corpus/by_language/go.txt`        | 0           | 0                              |
| `corpus/by_language/python.txt`    | 0           | 0                              |
| `corpus/by_language/javascript.txt`| 0           | 0                              |
| `corpus/by_language/perl.txt`      | 0           | 0                              |

Validation commands:

```
grep -cE '^$' corpus/by_language/<lang>.txt          # empty lines (must be 0)
grep -cvE '^[A-Za-z_][A-Za-z0-9_]*$' corpus/by_language/<lang>.txt   # violations (must be 0)
```
