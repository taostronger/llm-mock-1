"""Build the editable Beamer source and synchronize charts from reference CSVs.

Requires Python 3.11+ and a TeX Live/MiKTeX installation with XeLaTeX,
beamer, ctex, Fandol fonts, TikZ and PGFPlots. No Python package required.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUILD = ROOT / "_build" / "beamer"


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "results" / "reference" / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, header: list[str], values: list[list[object]]) -> None:
    target = HERE / "data" / name
    target.parent.mkdir(exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(values)


def main() -> None:
    eplb = {(r["case"], r["mode"]): r for r in rows("eplb_aggregate.csv")}
    cases = ["steady", "shift", "oscillate", "uniform", "costly_shift"]
    write_csv("eplb.csv", ["index", "uniform", "static", "dynamic"], [
        [i, *(eplb[(case, mode)]["mean_layer_ms"] for mode in ("uniform", "static", "dynamic"))]
        for i, case in enumerate(cases)
    ])
    routing = {(r["case"], r["policy"]): r for r in rows("routing_aggregate.csv")}
    route_cases = ["steady_8", "hot_shift_8", "burst_8", "small_cache_8", "stale_8"]
    write_csv("routing.csv", ["index", "change_pct"], [
        [i, f"{(float(routing[(case, 'algorithm_two')]['ttft_mean_s']) / float(routing[(case, 'algorithm_one')]['ttft_mean_s']) - 1) * 100:.10f}"]
        for i, case in enumerate(route_cases)
    ])
    engine = shutil.which("xelatex")
    if not engine:
        raise SystemExit("XeLaTeX not found; install TeX Live or MiKTeX, then rerun.")
    BUILD.mkdir(parents=True, exist_ok=True)
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
           f"-output-directory={BUILD}", "project-introduction.tex"]
    for pass_no in (1, 2):
        result = subprocess.run(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = result.stdout.decode("utf-8", errors="replace")
        (BUILD / f"xelatex-pass-{pass_no}.txt").write_text(output, encoding="utf-8")
        if result.returncode:
            print(output[-12000:])
            raise SystemExit(result.returncode)
    log = (BUILD / "project-introduction.log").read_text(encoding="utf-8", errors="replace")
    warnings = [line for line in log.splitlines() if "Overfull" in line or "Missing character" in line]
    if warnings:
        print("Layout/font warnings:\n" + "\n".join(warnings))
        raise SystemExit("Fix TeX layout/font warnings before delivery.")
    target = HERE / "project-introduction.pdf"
    shutil.copyfile(BUILD / target.name, target)
    print(f"Built {target.name}; 2 XeLaTeX passes, no overfull boxes or missing characters.")


if __name__ == "__main__":
    main()
