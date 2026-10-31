"""Write a field trial as a sample for the repo: a summary GitHub renders, plus the full report.

    python3 tools/sample_report.py reports/<time>_suite_<dut>.json [--class line] [--name "..."]

Writes docs/samples/<slug>/:
  README.md     the summary: score, grades per test, fault tests and three charts. GitHub
                renders it in place.
  *.svg         the charts, as standalone files. GitHub strips inline SVG from Markdown, and
                the report's charts take their colours from the page's CSS, so each file
                carries its own light and dark palette.
  report.html   the full report, unchanged. GitHub shows HTML as source; GitHub Pages
                (main, /docs) serves it as a page.

  sample.json   what the index needs (name, trial, score).

The trial is re-graded from its saved runs, so the score matches what the trial printed.
Every call refreshes the table in docs/samples/README.md from all the samples (`--index`
alone just refreshes it).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil

import grade
import html_report

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAMPLES = os.path.join(ROOT, "docs", "samples")
PAGES = "https://jordancrombie.github.io/TBT/samples"

VERDICT = {"pass": "✅", "marginal": "🟡", "fail": "❌", "invalid": "⛔", "info": "ℹ️"}

# The report's palette (html_report.CSS), for SVGs shown outside the page.
SVG_STYLE = """<style>
svg { --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --ok:#1a7f37; --warn:#9a6700;
      --bad:#cf222e; --info:#0969da; --cell:#e7ecf0; }
@media (prefers-color-scheme: dark) {
  svg { --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --ok:#3fb950; --warn:#d29922;
        --bad:#f85149; --info:#4493f8; --cell:#262c36; }
}
text { fill: var(--muted); font-size: 11px; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
</style>"""

FIELD_LEGEND = ("Each cell is one output field, numbered by the frame it carried. Grey: our picture; "
                "amber: ghosted or went back a frame; dark grey: blank; red: garbled; purple (B): the TBC's own "
                "pattern. A clean output shows every frame twice, in order.")


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "dut"


def standalone(svg):
    """An inline report SVG as a file: namespaced, with its palette inside."""
    if not svg:
        return ""
    svg = svg[:svg.rindex("</svg>") + 6]      # drop the HTML legend that follows some charts
    return svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).replace(">", ">" + SVG_STYLE, 1)


def chart(out, fname, svg):
    svg = standalone(svg)
    if not svg:
        return None
    with open(os.path.join(out, fname), "w") as f:
        f.write(svg)
    return fname


def trial_time(path):
    m = re.match(r"(\d{8}-\d{6})_suite_", os.path.basename(path))
    return dt.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S") if m else None


def original_report(suite, when, dut_name):
    """The trial's own HTML report: written beside the suite JSON within a few seconds of it."""
    if not when:
        return None
    for d in range(4):
        p = os.path.join(os.path.dirname(suite), f"{when + dt.timedelta(seconds=d):%Y%m%d-%H%M%S}_{slug(dut_name)}.html")
        if os.path.exists(p):
            return p
    return None


def find(results, tid, top=False):
    runs = [r for r in results if r["test"]["id"] == tid]
    return (max(runs, key=lambda r: r["test"]["rung"]) if top else runs[0]) if runs else None


def write_sample(suite, tbc_class="frame", name=None):
    data = json.load(open(suite))
    results = data["runs"]
    G = grade.grade(results, tbc_class)
    first = results[0]
    dut = first.get("dut", {}) or {}
    name = name or dut.get("name") or "unspecified device"
    when = trial_time(suite)
    s = slug(name)
    out = os.path.join(SAMPLES, s)
    os.makedirs(out, exist_ok=True)
    # The trial's own report, if it was run with --html, has the waveforms; the suite JSON
    # doesn't keep them, so a report re-written from it has every card but no waveform.
    orig = original_report(suite, when, dut.get("name") or "")
    if orig:
        shutil.copyfile(orig, os.path.join(out, "report.html"))
    else:
        html_report.write(results, os.path.join(out, "report.html"), grades=G, when=when)

    gen = first.get("generator", {})
    lv = gen.get("levels", {})
    groups = " · ".join(f"{k} {100 * v:.0f}" for k, v in sorted(G["groups"].items()))
    size = max(1, round(os.path.getsize(os.path.join(out, "report.html")) / 1e6))
    kind = ("the trial's own report" if orig else
            "re-written from the saved trial, which doesn't keep the waveforms; every other part is there")
    md = [f"# {name}: sample field trial", "",
          f"**Full report:** [{PAGES}/{s}/report.html]({PAGES}/{s}/report.html) "
          f"({kind}; self-contained, about {size} MB; [source](report.html))", "",
          "| | |", "|---|---|",
          f"| Trial | {when:%Y-%m-%d %H:%M} · {len(results)} runs · `{os.path.basename(suite)}` |" if when else
          f"| Trial | {len(results)} runs · `{os.path.basename(suite)}` |",
          f"| Generator | firmware {gen.get('firmware', '?')} · levels {lv.get('sync_code', 0):g} / "
          f"{lv.get('white_code', 0):g} (sync / white code) · {first['test'].get('chroma', '?')} |",
          f"| Graded as | {G['class']} TBC (provisional thresholds, [docs/design.md](../../design.md)) |"]
    if G["score"] is not None:
        md += [f"| **Score** | **{G['score']:.0f} / 100** ({groups}) |"]
    fp = [f for f in glob.glob(os.path.join(ROOT, "fingerprints", "*.json"))
          if json.load(open(f)).get("name") == name]
    if fp:
        md += [f"| Fingerprint | [fingerprints/{os.path.basename(fp[0])}](../../../fingerprints/{os.path.basename(fp[0])}) |"]
    md += [""]

    v0, s10 = find(results, "V0"), find(results, "S10", top=True)
    figs = []
    if v0 and v0.get("excerpt"):
        f = chart(out, "v0-line.svg", html_report.waveform(v0["excerpt"]))
        figs.append((f, "V0, one picture line of the output",
                     "Min/max envelope of one line about 60 lines into a field; the shading is the colour subcarrier."))
    if v0 and v0.get("field_log"):
        figs.append((chart(out, "v0-fields.svg", html_report.field_strip(v0["field_log"])),
                     "V0, every output field (clean input)", FIELD_LEGEND))
    if s10 and s10.get("field_log"):
        figs.append((chart(out, "s10-fields.svg", html_report.field_strip(s10["field_log"])),
                     f"S10 rung {s10['test']['rung']}, output fields while input fields are lost", FIELD_LEGEND))
    for f, title, cap in (x for x in figs if x[0]):
        md += [f"### {title}", "", f"![{title}]({f})", "", f"<sub>{cap}</sub>", ""]

    md += ["## Grades", "", "✅ pass · 🟡 marginal · ❌ fail · ℹ️ not graded", "",
           "| Test | | Result | Rungs |", "|---|---|---|---|"]
    names = {r["test"]["id"]: r["test"].get("name", "") for r in results}
    for tid, t in G["tests"].items():
        rungs = " ".join(f"r{r}{VERDICT.get(v, v)}" for r, v in t["rungs"])
        md.append(f"| {tid} | {names.get(tid, '')} | {t['summary']} | {rungs} |")
    md += [""]
    from run_suite import tolerance_lines
    tol = tolerance_lines(results)
    if tol:
        md += ["## Fault tests", ""] + [f"- {l}" for l in tol] + [""]
    if G["notes"]:
        md += ["## Notes", ""] + [f"- {n}" for n in G["notes"]] + [""]
    md += ["---", "",
           "<sub>Written by `tools/sample_report.py` from the saved trial. What each test does: "
           "[docs/tests.md](../../tests.md). How these samples are laid out for GitHub: "
           "[docs/samples/README.md](../README.md).</sub>", ""]
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write("\n".join(md))
    meta = {"name": name, "suite": os.path.basename(suite), "class": tbc_class,
            "when": f"{when:%Y-%m-%d}" if when else "", "runs": len(results), "score": G["score"],
            "report": "original" if orig else "re-written"}
    with open(os.path.join(out, "sample.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return out, G


INDEX_START, INDEX_END = "<!-- samples:start -->", "<!-- samples:end -->"


def write_index():
    """Refresh the table of samples between the markers in docs/samples/README.md."""
    rows = []
    for m in sorted(glob.glob(os.path.join(SAMPLES, "*", "sample.json"))):
        d = json.load(open(m))
        s = os.path.basename(os.path.dirname(m))
        score = f"{d['score']:.0f}" if d["score"] is not None else "—"
        rows.append(f"| [{d['name']}]({s}/README.md) | {score} | {d['when']} | {d['runs']} | "
                    f"[open]({PAGES}/{s}/report.html) |")
    table = "\n".join(["| Device (input) | Score | Trial | Runs | Full report |", "|---|---|---|---|---|", *rows])
    path = os.path.join(SAMPLES, "README.md")
    text = open(path).read()
    a, b = text.index(INDEX_START) + len(INDEX_START), text.index(INDEX_END)
    with open(path, "w") as f:
        f.write(text[:a] + "\n" + table + "\n" + text[b:])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("suites", nargs="*", help="reports/<time>_suite_<dut>.json")
    ap.add_argument("--class", dest="tbc_class", choices=("frame", "line"), default="frame")
    ap.add_argument("--name", help="sample name (default: the trial's DUT name)")
    ap.add_argument("--index", action="store_true", help="rebuild docs/samples/README.md")
    a = ap.parse_args()
    for s in a.suites:
        out, G = write_sample(s, a.tbc_class, a.name)
        score = f"{G['score']:.1f}" if G["score"] is not None else "not scored"
        print(f"{os.path.relpath(out, ROOT)}: score {score}")
    if a.index or a.suites:
        write_index()
        print("docs/samples/README.md")


if __name__ == "__main__":
    main()
