# TODO

Open work for TBT, roughly in priority order. Measured facts and open issues
live in [docs/bench-notes.md](docs/bench-notes.md).

## Next
- [ ] **Automatic identification:** `tools/identify.py` matches a new
      fingerprint against `fingerprints/`, model traits first and then unit
      traits (the clock offset tells units apart), and reports the closest
      match and how close it is. The 2026-10-23 blind test did this by hand.
- [ ] **Regenerate the sample report** (`docs/sample-report.html` and
      `docs/sample-report.jpg`). The current one predates CH2, grading and
      H6. Run `run_suite.py full --grade --html`, copy the report from
      `reports/` to `docs/sample-report.html`, then re-render the
      screenshot:
      `qlmanage -t -s 1400 -o /tmp docs/sample-report.html` and
      `sips -s format jpeg -s formatOptions 80 /tmp/sample-report.html.png --out docs/sample-report.jpg`.
      Repeat whenever tests or the report layout change.

## Feature requests (ranked 2026-10-24)
Scored for value against what the suite already covers.
- [x] **#25 VBI data and line 21 integrity (82).** Done 2026-10-24: B1
      captions (clean, dropped field, lost fields) and the B2 line map,
      first measured on the TBC-3000.
  - [ ] Run B1/B2 on the other units (TBC-1000, AVT-8710, DVR-220, ES-10)
        and add the traits to their fingerprints.
  - [ ] Optional: VITC timecode on a line in 10–20, decoded the same way.
- [x] **#27 Macrovision-like AGC pulses (76).** Done 2026-10-24: B3 (steady,
      cycling, cycling + colour stripe), first measured on the TBC-3000.
  - [ ] Run B3 on the other units. None tested so far passes the pulses, so
        the "passed" and "blinded" outcomes are checked only on the input
        (CH2) and synthetically; a unit that passes them would confirm them.
- [ ] **#26 Head-switching disruption (34).** H4 and H3 mostly cover it. Add
      a line-by-line recovery count after H4's switch point, check whether
      the marker line moves under H4 (vertical stretch in a frame TBC), and
      perhaps a variant that adjusts where the switch happens.
- [ ] **#28 SCH phase drift (30).** F2 and C3 mostly cover it. Add a wandering
      (back-and-forth) drift rung to F2, and measure the output's own
      sync-to-subcarrier phase, not just its hue.

## Rig calibration
- [x] CH2 wired, teed at the TBC input (2026-10-14): input check, latency,
      output lock and gain against the input on every two-channel run.
- [x] Single-channel option (`--channels 1`).
- [ ] Terminate CH1. Its sync reads about 0.55 V against CH2's 0.23 V, so
      the end of the TBC's output run is still open.
- [ ] Calibrate `levels` on CH2 to 286 mV sync / 714 mV white (now about
      230 mV sync, 80 %). Leave headroom below the sync tip (sync at code
      ~15–20), so S1 can go deeper than 40 IRE and L2 noise isn't clipped.
- [ ] Generator chroma reads about 0.68× nominal on CH2 (burst 27 IRE p-p
      instead of 40). Find out where: DAC hold (sinc, 0.90 at fs/4), the
      DAC's output impedance into the cable, or the measurement. Then
      pre-emphasise chroma in the renderer, so single-channel rigs get a
      nominal input too.
- [ ] Check each test's input on CH2 against the model across the whole
      catalog, not just the field trial's rungs.
- [ ] F1: confirm on the scope that the sample clock moves by the commanded
      ppm (CH2's line period makes it measurable).
- [ ] Lower the displacement floor (~11 ns on CH1, ~20 ns on CH2: scope
      noise). Terminate CH1 and recheck; average over more of the line; try
      a smaller scope range.

## Grader and fingerprints
- [x] `tools/grade.py` with provisional thresholds (2026-10-14).
- [x] Fingerprints and the library: 7 entries for 5 devices (2026-10-24).
- [x] Line TBC or frame synchroniser: H6, jitter transfer, H3 step recovery,
      and the timing class, calibrated on four devices (2026-10-23).
- [ ] Check the thresholds and group weights against a known-good TBC.
- [ ] Recovery time for S4 and S6; burst phase stability.
- [ ] A second unit of one model (a black AVT-8710, or a second TBC-1000 or
      TBC-3000), to see whether model traits hold across units.
- [ ] More line TBCs (a JVC or Panasonic S-VHS deck's TBC in passthrough,
      if one allows it; a Panasonic DMR-ES15), to firm up the timing-class
      thresholds, which come from one or two units per class.

## Devices
- **AVT-8710 (green)**
  - [x] Colour killer: none (confirmed by its fingerprint).
  - [ ] X1 on a suspect black unit, to set what "buggy" looks like in the
        numbers; a longer X1 to provoke the reported "ghost mode".
  - [ ] Explain L3: with hum on the input, blanking is clamped flat but the
        gray bar reads higher (84 / 95 IRE vs 79 at 20 / 40 IRE p-p).
  - [ ] H4: output hue wanders ±19° line to line on the AVT and TBC-1000,
        probably inherent to colour-under timing jumps. Confirm.
- **Datavideo TBC-1000**
  - [x] Dead-output episodes: `dropout_watch.py`. None since it was moved
        to a cooler spot (2026-10-14); 10+ field trials clean since.
  - [ ] If it recurs: a long warm watch (an hour or more) logging output
        sync depth, and check the supply rail and temperature.
- **Datavideo TBC-3000**
  - [x] Identified blind; both inputs fingerprinted at baseline
        (2026-10-23/24).
  - [ ] Find which control setting caused input B's step jolt (one
        control moved at a time).
- **Pioneer DVR-220**
  - [ ] One more field trial for its fingerprint (has 2).
  - [ ] Look at L3 (hum) and X1 r4 on the monitor. Are its saturation swings
        (±8 % between runs) real?
- **Panasonic DMR-ES10**
  - [x] Fingerprinted from 4 lid-off trials; line TBC (2026-10-21/23).
  - [ ] Its overheating colour fault, with the cover on: check the fan,
        heatsink and thermal pad, then retest with the cover on. Back-to-back
        field trials failed within about an hour before. A reliable fix
        should survive that.

## Generator
- [ ] Confirm the intermittent DMA stop is gone. A likely cause, a race on
      test switches, was fixed 2026-10-24 and three full verifier passes
      since showed no restarts; keep watching `dma_restarts` over a few
      field trials before closing it (see the bench notes).
- [ ] H7 velocity error: timing that drifts *within* a line (needs
      pre-stretched line copies). For line TBCs and the tape-deck phase.
- [ ] Tape program mode: step through test rungs on a timed schedule while
      recording a test tape, logging each segment's manifest; a V0 segment
      per tape.
- [ ] More variant levels for C3/L2/L3 when memory allows (now
      `subsample_steps`, 4 with SMPTE bars).
