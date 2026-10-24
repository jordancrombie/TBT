"""Text cards shown between tests (run_suite.py --cards).

A card tells a viewer what's about to happen:

    H1 * TEST 2 OF 31
    RANDOM LINE JITTER
    6 RUNGS: 5 TO 200 NS RMS
    WATCH: EDGES SHOULD STAY STRAIGHT
    LAST: V0 RUNG 1: FAIL

It is never part of a test: the runner restores the test pattern before the
next capture. Names and ladders come from the firmware's own catalog
(`tests`); the "watch for" hints are below, written from docs/tests.md.
"""
import re

# What a viewer should look at on the monitor (<= 34 characters each).
HINTS = {
    "V0": "CLEAN BARS: THE REFERENCE",
    "H1": "EDGES SHOULD STAY STRAIGHT",
    "H2": "NO SLOW SIDE-TO-SIDE WOBBLE",
    "H3": "THE PICTURE SHOULD NOT JUMP",
    "H4": "NO BEND AT THE BOTTOM",
    "H5": "NO TORN LINE MID-PICTURE",
    "H6": "THE WOBBLE GETS FASTER",
    "F1": "DECK RUNNING FAST OR SLOW",
    "F2": "COLOUR SHOULD STAY STEADY",
    "F3": "SPEED DRIFTS SLOWLY",
    "S1": "WEAK SYNC: SHOULD STILL LOCK",
    "S2": "SOFT SYNC EDGES: NO JITTER",
    "S3": "LINES WITHOUT SYNC: NO TEAR",
    "S4": "BROKEN V-SYNC: NO ROLL",
    "S5": "240P, LIKE A GAME CONSOLE",
    "S6": "WRONG LINE COUNT PER FIELD",
    "S7": "A FIELD GOES MISSING",
    "S8": "FIELD LENGTH WOBBLES: NO ROLL",
    "S9": "SEARCH NOISE BAR: NO ROLL",
    "S10": "GAPS: NEVER ITS OWN BARS",
    "S11": "SNOW GAPS: RIDE THROUGH",
    "C1": "WEAK OR HOT COLOUR BURST",
    "C2": "NO BURST: SHOULD GO B/W",
    "C3": "HUE SHIMMERS LINE TO LINE",
    "C4": "TINT SHIFT: PASS IT UNCHANGED",
    "L1": "TAPE DROPOUT STREAKS",
    "L2": "MORE NOISE EACH RUNG",
    "L3": "HUM BARS ROLLING UP",
    "L4": "TOO DARK OR TOO BRIGHT",
    "X1": "BAD TAPE, THEN RECOVERY",
    "V1": "NO INPUT: WHAT DOES IT SHOW?",
    "B1": "TURN CAPTIONS ON (CC1) TO READ",
    "B2": "HIDDEN VBI LINES: KEPT?",
}

# The firmware's parameter names, as a viewer would say them.
UNITS = {
    "rms_ns": "NS RMS", "peak_ns": "NS PEAK", "step_us": "US STEP", "skew_us": "US SKEW",
    "samples": "SAMPLES", "ppm": "PPM", "peak_ppm": "PPM PEAK", "sync_ire": "IRE SYNC",
    "rise_ns": "NS EDGES", "lines": "LINES", "variant": "", "delta_lines": "LINES",
    "every_frames": "FRAMES APART", "peak_lines": "LINES", "burst_pp_ire": "IRE BURST",
    "rms_deg": "DEG RMS", "deg": "DEG", "length_us": "US", "snr_db": "DB SNR",
    "pp_ire": "IRE P-P", "white_pct": "% LEVEL", "fields": "FIELDS", "stress": "", "disruption": "",
}
PX = (7, 5, 4, 3, 3)   # font size per card line (the firmware shrinks a line to fit)

_LINE = re.compile(r"^\s*(\S+)\s+(.+?)\s+\[[^\]]*\]\s+(\S+):\s*(.*)$")


def parse_catalog(text):
    """The firmware's `tests` output -> {id: {name, p1, ladder}}."""
    out = {}
    for line in text.splitlines():
        m = _LINE.match(line)
        if m:
            out[m.group(1)] = {"name": m.group(2), "p1": m.group(3), "ladder": m.group(4).split()}
    return out


def clean(s, n=40):
    """Upper case, characters the firmware's font has, at most n characters."""
    s = s.upper().replace("·", "*").replace("µ", "U").replace("|", "/")
    return re.sub(r"[^A-Z0-9 .,:\-+/%()!?#=*']", "", s)[:n]


def rungs_text(info, rungs):
    """'6 RUNGS: 5 TO 200 NS RMS', or 'RUNG 4: 50 NS RMS'."""
    if not info or info["p1"] == "-":
        return "ONE RUN"
    unit = UNITS.get(info["p1"], info["p1"].replace("_", " "))
    val = lambda r: info["ladder"][r - 1].split("@")[0] if 0 < r <= len(info["ladder"]) else "?"
    if info["p1"] == "stress":
        return f"{len(rungs)} STRESS TYPES" if len(rungs) > 1 else f"STRESS TYPE {rungs[0]}"
    if info["p1"] == "disruption":  # B1
        names = {1: "CLEAN", 2: "DROPPED FIELD", 3: "LOST FIELDS"}
        return ", ".join(names.get(r, str(r)) for r in rungs)
    if info["p1"] == "variant":
        return f"VARIANT{'S' if len(rungs) > 1 else ''} {', '.join(str(r) for r in rungs)}"
    p1 = {val(r) for r in rungs}
    if len(rungs) > 1 and len(p1) == 1 and "@" in info["ladder"][0]:
        # The first parameter is fixed (H6: 200 ns); the sweep is in the second (Hz).
        hz = lambda r: info["ladder"][r - 1].split("@")[1]
        return f"{len(rungs)} RUNGS: {hz(rungs[0])} TO {hz(rungs[-1])} HZ, {val(rungs[0])} {unit}"
    if len(rungs) == 1:
        return f"RUNG {rungs[0]}: {val(rungs[0])} {unit}".strip()
    return f"{len(rungs)} RUNGS: {val(rungs[0])} TO {val(rungs[-1])} {unit}".strip()


def short_summary(tid, t):
    """grade.grade()'s per-test summary, short enough for a card line."""
    s = t["summary"]
    m = re.match(r"passes up to rung (\d+) of (\d+)", s)
    if m:
        s = f"PASSED TO RUNG {m.group(1)}/{m.group(2)}"
    m = re.match(r"(\d+) of (\d+) rungs passed", s)
    if m:
        s = f"{m.group(1)}/{m.group(2)} RUNGS PASSED"
    m = re.match(r"fails from rung (\d+)", s)
    if m:
        s = f"FAILED FROM RUNG {m.group(1)}"
    m = re.match(r"rung (\d+): (\w+)", s)
    if m:
        s = f"RUNG {m.group(1)}: {m.group(2)}"
    return clean(f"LAST: {tid} {s}", 34)


def spec(tid, k, n, info, rungs, last=None):
    """The `card` command's argument: px:text|px:text|..."""
    lines = [f"{tid} * TEST {k} OF {n}", (info or {}).get("name", tid), rungs_text(info, rungs),
             "WATCH: " + HINTS.get(tid, "")]
    if last:
        lines.append(last)
    return "|".join(f"{px}:{clean(t)}" for px, t in zip(PX, lines))


def final_spec(score, n_runs, last=None):
    lines = ["FIELD TRIAL DONE", f"{n_runs} RUNS",
             f"SCORE {score:.0f} / 100 (PROVISIONAL)" if score is not None else "NOT SCORED", "TBT * TIME BASE TORTURE"]
    if last:
        lines.append(last)
    return "|".join(f"{px}:{clean(t)}" for px, t in zip(PX, lines))
