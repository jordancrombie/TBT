"""Colour watch: does a device's colour (or clock) drift as it warms up?

usage: colour_watch.py [--minutes 30] [--interval 10] [--dut NAME] [--note TEXT]

Starts clean V0 once, then only listens: every --interval seconds it
captures 0.3 s of CH1 (the device's output) and CH2 (its input). It never
restarts the test, because each restart briefly sends a black frame while
the generator rebuilds, which a device can see as a signal drop. It logs:
  hue and chroma against the input, burst, noise on the gray bar,
  the output's line rate against the input (ppm), latency,
  and whether the output is still our picture.
Start it with the device cold (just powered on) to see whether a fault
appears at a consistent warm-up time (heat) or at random (a failing part
or a marginal lock). Needs two channels. Saves reports/<time>_colour_<dut>.json.
"""
import argparse, json, os, re, shutil, time

import numpy as np

import dwf_scope
from gen_cmd import open_gen, request
from observe_tbc import analyze, compare_input
from run_test import RUNS, ask_json, run_one

REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--interval", type=float, default=10)
    ap.add_argument("--dut", default=os.environ.get("TBC_DUT", ""))
    ap.add_argument("--note", default=os.environ.get("TBC_NOTE", ""))
    a = ap.parse_args()
    dut = {"name": a.dut, "notes": a.note}
    samples, t0 = [], time.time()
    print(f"{'min':>5} {'state':6} {'hue':>7} {'chroma':>7} {'burst':>6} {'noise':>6} {'ppm':>7} {'latency':>8}")
    with dwf_scope.Scope(25e6, 0.3) as scope:
        s = open_gen()
        if ask_json(s, "info", "}\n").get("pattern") != "smpte_bars":
            request(s, "p smpte_bars", until="\n", timeout=10)
        # Start V0 once (not even that if it's already playing); then only capture.
        info = ask_json(s, "info", "}\n")
        if info.get("test") == "V0" and info.get("pattern") == "smpte_bars":
            scope.set_timebase(25e6, 0.3)
            manifest = ask_json(s, "manifest", "}}\n")
            manifest.update(dut=dut, generator_state=info,
                            capture={"rate_hz": 25e6, "volts": "raw * scale + offset", "dma_restarts_during": 0})
        else:
            first, _ = run_one(s, scope, "V0", 1, 1, 2.0, RUNS, dut, (25e6, 0.3))
            manifest = json.load(open(os.path.join(first, "manifest.json")))
            shutil.rmtree(first, ignore_errors=True)
        while time.time() - t0 < a.minutes * 60:
            tick = time.time()
            cap = scope.capture()
            run = os.path.join(RUNS, time.strftime("%Y%m%d-%H%M%S") + "_colourwatch")
            os.makedirs(run, exist_ok=True)
            manifest["capture"].update(started_unix=tick, samples=int(cap["raw"].shape[1]), dma_restarts_during=0)
            with open(os.path.join(run, "manifest.json"), "w") as fh:
                json.dump(manifest, fh)
            np.savez(os.path.join(run, "capture.npz"), **{f"ch{c + 1}": cap["raw"][c] for c in range(cap["raw"].shape[0])},
                     scale=cap["scale"], offset=cap["offset"], rate=cap["rate"])
            try:
                out, inp = analyze(run, 1), analyze(run, 2)
                ci = compare_input(out, inp)
            finally:
                shutil.rmtree(run, ignore_errors=True)
            pc, v = out.get("picture") or {}, ci.get("vs_input") or {}
            fs_ = out.get("field_summary") or {}
            st = {"t_min": round((tick - t0) / 60, 2), "dead": out.get("dead"),
                  "ours": fs_.get("ours", 0), "hue_vs_input": v.get("hue_deg"), "chroma_ratio": v.get("chroma"),
                  "burst_ire": pc.get("burst_pp_ire"), "hue_jitter": pc.get("yellow_hue_jitter_deg"),
                  "noise_ire": pc.get("gray_noise_ire_rms"), "rate_ppm": ci.get("rate_ppm"),
                  "latency_ms": (ci.get("latency") or {}).get("median_ms")}
            samples.append(st)
            state = "DEAD" if st["dead"] else "ours" if st["ours"] else "other"
            f = lambda x, fmt: format(x, fmt) if x is not None else "—"
            print(f"{st['t_min']:5.1f} {state:6} {f(st['hue_vs_input'], '+7.1f')} {f(st['chroma_ratio'], '7.2f')} "
                  f"{f(st['burst_ire'], '6.1f')} {f(st['noise_ire'], '6.2f')} {f(st['rate_ppm'], '+7.1f')} "
                  f"{f(st['latency_ms'], '8.1f')}", flush=True)
            time.sleep(max(0.0, a.interval - (time.time() - tick)))
    os.makedirs(REPORTS, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", a.dut).strip("-").lower() or "dut"
    path = os.path.join(REPORTS, time.strftime("%Y%m%d-%H%M%S") + f"_colour_{slug}.json")
    with open(path, "w") as fh:
        json.dump({"kind": "colour_watch", "dut": dut, "interval_s": a.interval, "samples": samples}, fh, indent=1)
    print(f"saved {os.path.normpath(path)}")


if __name__ == "__main__":
    main()
