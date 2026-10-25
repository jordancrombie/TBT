# TODO

Open work for TBT, roughly in priority order. Measured facts and open issues
live in [docs/bench-notes.md](docs/bench-notes.md).

## Next
- [ ] **Timing resolution (found 2026-10-24):** every test gets 2 sub-sample
      copies (70 ns steps) since 2026-10-13, so H1 rungs 1–2 (5, 10 ns rms)
      deliver no jitter and rung 3 is coarse. Options: find the memory for 4
      or 8 copies on timing tests, dither the low rungs, or redefine them.
      To discuss.
- [ ] **Identification and regression tool:** `tools/identify.py` matches a
      new fingerprint against `fingerprints/`, model traits first and then
      unit traits (the clock offset tells units apart), and reports the
      closest match and how close it is. The same comparison, run on one
      trial against a known unit's fingerprint, is the regression check in
      [docs/validation.md](docs/validation.md). The 2026-10-23 blind test and
      the 2026-10-24 regression trials did it by hand. Match clock offsets
      within about ±0.5 ppm: a unit's crystal drifts by 0.2–0.3 ppm over a
      day (bench notes).
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
- [x] Terminate CH1 (2026-10-24): sync 0.56 → 0.281 V. Output jitter and
      noise floors rose (half the volts against the same scope noise); see
      the bench notes.
  - [x] Output jitter and noise are rig-dependent fingerprint traits, and
        fingerprints record CH1's termination; the library (all
        unterminated) was rebuilt with it.
  - [ ] After the levels calibration: terminated baselines, starting with
        the reference unit (TBC-3000 input A), then the others as they come
        back on the bench. Keep the unterminated entries as references.
- [x] Calibrate `levels` on CH2 (2026-10-24): `5 92`, sync 283 mV, white
      718 mV. `tools/calibrate_levels.py` measures and suggests codes.
- [ ] A video buffer amplifier between the DAC and the 75 Ω resistor
      (a THS7314-class part, or a transistor follower): the DAC distorts
      colour slightly at full amplitude into 150 Ω (hue −2.6°, chroma −7 %).
- [ ] Measure the DAC's staircase (all 256 codes on CH2) for its linearity;
      a one-code step at code 64 is known.
- [ ] A reconstruction low-pass after the DAC (with the buffer): the falling
      sync edge bounces ~40 mV (a DAC glitch near code 16), which the
      analysis now tolerates but a TBC's own sync slicer might not.
- [ ] **Rebaseline every unit on the calibrated rig** (CH1 terminated,
      levels 5/92), 3 field trials each, moving old entries to
      `fingerprints/old-rig/`:
  - [x] Datavideo TBC-3000 input B (Source B), 2026-10-24
  - [x] Datavideo TBC-3000 input A (the reference unit), 2026-10-24
  - [x] Datavideo TBC-1000, 2026-10-25 (its output sync wandered; see the
        bench notes)
  - [ ] AVT-8710 (green)
  - [x] Pioneer DVR-220, 2026-10-24/25 (third set: the first had V0 caught
        mid-recovery, the second the old B3 detector)
  - [x] Panasonic DMR-ES10 (lid off), 2026-10-24 (third attempt: the first
        two were spoilt by analysis bugs, since fixed; see the bench notes)
- [ ] Longer S10/S11 captures for slow-recovering units: the DVR-220's
      picture often hasn't come back within the 1.3 s capture after an 8-11
      field gap, so those rungs read "gap not captured" and its tolerance
      comes out 8 (1 of 3 trials agree) where it blanked through every gap
      seen.
- [ ] Checksum the other serial replies (`lens`, `pdump`, `manifest`), as
      `dump` now is.
- [x] Generator chroma: it read about 0.68× nominal on CH2 until 2026-10-14,
      and 0.92–0.97× from 2026-10-15 on (a rig change overnight, not
      recorded). The ~5 % left fits the DAC's sinc roll-off.
  - [ ] Optional: pre-emphasise chroma ~5 % in the renderer, so
        single-channel rigs get a nominal input.
- [ ] Check each test's input on CH2 against the model across the whole
      catalog, not just the field trial's rungs.
- [ ] F1: confirm on the scope that the sample clock moves by the commanded
      ppm (CH2's line period makes it measurable).
- [ ] Lower the displacement floor (~11 ns on CH1, ~15 ns on CH2: scope
      noise). Terminating CH1 didn't change it, and nor does the scope's
      range; averaging over more of the line is what's left.

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
      test switches, was fixed 2026-10-24. Since then: four full verifier
      passes and three full field trials, no restarts. Keep watching
      `dma_restarts` for a few more before closing it (see the bench notes).
- [ ] H7 velocity error: timing that drifts *within* a line (needs
      pre-stretched line copies). For line TBCs and the tape-deck phase.
- [ ] Tape program mode: step through test rungs on a timed schedule while
      recording a test tape, logging each segment's manifest; a V0 segment
      per tape.
- [ ] More variant levels for C3/L2/L3 when memory allows (now
      `subsample_steps`, 2 for every test). Goes with the timing resolution
      item above.
