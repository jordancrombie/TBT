"""Measure the generator's output levels on CH2 and suggest `levels` codes.

usage: calibrate_levels.py [--set SYNC WHITE] [--tip CODE]

CH2 must see the generator's output where the TBC sees it: teed at the TBC's
75-ohm input (see the README's Wiring). The script shows flat fields at 0, 50
and 100 IRE, measures the sync tip, blanking and each flat level on CH2, and
prints them against the targets (286 mV of sync, 714 mV of white above
blanking). It then suggests codes that would hit the targets, keeping the
sync tip at --tip (default: where it is now).

--set SYNC WHITE applies those codes first, then measures. The setting lasts
until the generator restarts: to keep it, change DEFAULT_LEVELS in
src/main.cpp and reflash. Afterwards the generator is back on SMPTE bars.
"""
import argparse, json, time

import numpy as np

import dwf_scope
import observe_tbc as ob
from gen_cmd import open_gen, request

SYNC_MV, WHITE_MV = 286.0, 714.0


def flat_levels(scope, s, ire):
    """(sync tip, blanking, flat level) on CH2, volts, for a flat field at `ire`."""
    request(s, f"flat {ire}")
    time.sleep(0.6)
    cap = scope.capture()
    x = dwf_scope.volts(cap, 1).astype(np.float32)
    us = cap["rate"] / 1e6
    ft, w = ob.sync_pulses(x, us)
    hs = ft[(w > 3.5) & (w < 6)][100:600]
    seg = lambda a, b: float(np.median([x[int(h + a * us):int(h + b * us)].mean() for h in hs]))
    return seg(1.5, 3.5), seg(8.2, 9.1), seg(20, 50)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", nargs=2, type=float, metavar=("SYNC", "WHITE"), help="apply these DAC codes first")
    ap.add_argument("--tip", type=float, help="DAC code to keep the sync tip at, for the suggestion")
    a = ap.parse_args()
    s = open_gen()
    request(s, "test V0")
    if a.set:
        print(request(s, f"levels {a.set[0]:g} {a.set[1]:g}").strip())
    info = json.loads(request(s, "info").strip().splitlines()[-1])
    lo, hi = info["sync_code"], info["white_code"]
    request(s, "p flat")
    r = {}
    try:
        with dwf_scope.Scope(50e6, 0.1) as sc:
            for ire in (0, 50, 100):
                r[ire] = flat_levels(sc, s, ire)
    finally:
        request(s, "flat 50")
        request(s, "p smpte_bars")
    tip = np.mean([v[0] for v in r.values()])
    blank = np.mean([v[1] for v in r.values()])
    sync_mv, white_mv = 1000 * (blank - tip), 1000 * (r[100][2] - blank)
    print(f"levels {lo:g} {hi:g} on CH2: sync {sync_mv:.1f} mV ({100 * sync_mv / SYNC_MV:.1f} %), "
          f"white {white_mv:.1f} mV ({100 * white_mv / WHITE_MV:.1f} %), "
          f"50 IRE {1000 * (r[50][2] - blank):.1f} mV (nominal {WHITE_MV / 2:.0f})")
    # Volts per code from the measured span; keep the tip where asked.
    mv_per_code = (sync_mv + white_mv) / (hi - lo)
    t = lo if a.tip is None else a.tip
    span = (SYNC_MV + WHITE_MV) / mv_per_code
    print(f"suggested: levels {t:g} {t + span:.0f}  ({mv_per_code:.1f} mV per code). "
          f"Codes are whole numbers, so expect about ±1 code ({mv_per_code:.0f} mV) of error.")


if __name__ == "__main__":
    main()
