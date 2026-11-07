"""Draw the size-versus-fit scatter plot that README.md embeds.

Reads the two tables in `docs/MODEL_BUDGET.md` — the 64-bit frontier and the
handful of extra measured points — so the figure has one source of truth and
cannot drift from the numbers it illustrates.

    python3 scripts/frontier_plot.py --doc docs/MODEL_BUDGET.md \
        --out docs/frontier.svg [--png /tmp/frontier.png]

Axes: model size in kilobytes (horizontal) and the fraction of held-out
identifiers that do *not* fit in 64 bits (vertical).  The best model is the one
furthest bottom-left.  The figure says nothing that the table does not; the
convention (which code, which terminator) is stated in the caption in README.
"""

import argparse
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _num(s):
    s = s.replace(",", "").replace("kB", "").replace("kB", "")
    s = re.sub(r"\(.*?\)", "", s).strip()
    m = re.match(r"^[−-]?[0-9.]+", s)
    return float(m.group(0).replace("−", "-")) if m else None


def read_tables(path):
    """Return (frontier, extra): lists of dicts.

    `frontier` rows are `(kB, V, k, fit64)`; `extra` rows are
    `(label, kB, fit64)`.
    """
    frontier, extra = [], []
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        head = _cells(line)
        # The frontier table: "| bytes | `V` | `k` | mean bits | fit ≤64 | ..."
        if "kB/pt to next" in " ".join(head):
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                c = _cells(row)
                if len(c) < 5 or _num(c[0]) is None:
                    continue
                frontier.append(dict(kB=_num(c[0]) / 1000.0, V=int(_num(c[1])),
                                     k=int(_num(c[2])), fit=_num(c[4])))
        # The extra-points table: "| point | kB | fit ≤64 | note |"
        if len(head) >= 3 and head[0] == "point" and "kB" in head[1]:
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                c = _cells(row)
                if len(c) < 3 or _num(c[1]) is None:
                    continue
                extra.append(dict(label=c[0], kB=_num(c[1]), fit=_num(c[2])))
    return frontier, extra


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="docs/MODEL_BUDGET.md")
    ap.add_argument("--out", default="docs/frontier.svg")
    ap.add_argument("--png", default=None, help="also write a raster preview")
    args = ap.parse_args()

    frontier, extra = read_tables(args.doc)
    if not frontier:
        raise SystemExit(f"{args.doc}: no frontier table found")

    style = {4096: ("o", "#1f77b4", "V = 4096"),
             6144: ("s", "#2ca02c", "V = 6144"),
             8192: ("^", "#d62728", "V = 8192")}

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for V, (marker, colour, label) in style.items():
        rows = sorted((r for r in frontier if r["V"] == V), key=lambda r: r["kB"])
        if not rows:
            continue
        xs = [r["kB"] for r in rows]
        ys = [100.0 - r["fit"] for r in rows]
        ax.plot(xs, ys, marker=marker, ms=4.5, lw=0.9, color=colour,
                alpha=0.75, label=label, zorder=3)
        for r, x, y in zip(rows, xs, ys):
            ax.annotate(str(r["k"]), (x, y), textcoords="offset points",
                        xytext=(0, -9), ha="center", fontsize=5.5, color=colour,
                        alpha=0.9)

    for j, e in enumerate(extra):
        ax.plot([e["kB"]], [100.0 - e["fit"]], marker="D", ms=7.0,
                mfc="none", mec="#444444", mew=1.2, zorder=4,
                label="shipped code" if j == 0 else None)
        ax.annotate(e["label"], (e["kB"], 100.0 - e["fit"]),
                    textcoords="offset points", xytext=(-10, 4 - 12 * j),
                    ha="right", fontsize=6.5, color="#444444")

    ax.set_xlabel("model size (kB, word list and code included)")
    ax.set_ylabel("unencodable at 64 bits (%)")
    ax.grid(True, lw=0.4, alpha=0.45, zorder=0)
    ax.margins(x=0.04, y=0.12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=7, loc="upper right",
              title="small numbers are k", title_fontsize=7)
    fig.tight_layout()

    fig.savefig(args.out, format="svg", metadata={"Date": None})
    if args.png:
        fig.savefig(args.png, dpi=160)
    print(f"wrote {args.out}: {len(frontier)} frontier points, "
          f"{len(extra)} extra")


if __name__ == "__main__":
    main()
