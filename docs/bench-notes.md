# Bench notes

Measured facts about the hardware, toolchain and signal that are easy to
forget and slow to rediscover. Each one cost time once. Add to this file
whenever something surprises you, with the number and how it was found.

## Where test-run time goes

One rung with `run_suite.py` takes about **3.0 s**:

| Stage | Time | Notes |
|---|---|---|
| Switch test on the ESP32 | ~0.4 s | Serial command; the line pool is re-rendered |
| TBC lock (`--settle`) | 2.0 s | A fixed allowance, not measured. A candidate for tuning per TBC |
| Scope input settling | 2.0 s, **once per session** | Overlaps the TBC lock. See the ADP2230 section |
| Acquisition | = capture length | 0.4–0.6 s typical |
| Download, 2 × 30 M samples | ~0.25 s | int16 over USB |
| Save | ~0.1 s | Uncompressed `.npz` |

Before the two waits overlapped and the scope stayed open, each run took
6.5 s. `verify_timing.py` took about 10 minutes at 115200 baud with blocking
serial reads; at 921600 baud with non-blocking reads it takes 24 s.

**Disk:** a capture is 4 bytes × rate × seconds (two int16 channels), so
0.5 s at 50 MS/s is 100 MB per run. About 25 exploratory runs filled 2.6 GB,
so runs are now deleted after their report unless `--keep` is given.

## ADP2230 and the WaveForms SDK

- **The scope inputs need about 2 s to settle after a range or offset
  change.** The first capture after one reads garbage levels (e.g.
  0.001–0.105 V for a 0–1 V signal). Found in the earlier NTSC project
  (`../NTSC/NTSC_FINDINGS.md`). `dwf_scope.Scope` starts the clock when
  opened, and only the first capture waits.
- **Buffer:** 64 M samples per channel in the default configuration
  (config 5 has 128 M); at most 100 MS/s. That is 0.67 s at 100 MS/s or
  1.34 s at 50 MS/s.
- **Download as int16** (`FDwfAnalogInStatusData16`, in 1 M-sample chunks).
  As doubles, a full buffer is 512 MB per channel. Volts come from a linear
  fit against a short `FDwfAnalogInStatusData` read.
- **The inputs are 1 MΩ.** They never terminate a 75 Ω line.
- `FDwfEnumDevices` does not exist; it is `FDwfEnum`.

## ESP32 and toolchain

- **PlatformIO:** Homebrew's `pio` runs on Python 3.14, which the
  pioarduino platform rejects ("Python version must be between 3.10 and
  3.13"). Use `~/.platformio/penv/bin/pio` (Python 3.11).
- **The esptool in the PlatformIO env** fails standalone (missing
  `rich_click`). Use a separate venv `pip install esptool` for `chip-id`
  and similar.
- **The serial port is renamed per USB socket** (`/dev/cu.wchusbserial210`,
  then `…110`). The tools auto-detect `wchusbserial*`, or set `GEN_PORT`.
- **Serial runs at 921600 baud.** The CH340 handles it. `BAUD` in
  `tools/gen_cmd.py` must match `Serial.begin()` in `src/main.cpp`. Read
  only what has arrived (`in_waiting`): `read(65536)` with a timeout blocks
  for the whole timeout on every call.
- **IDF 5 APLL:** `rtc_clk_apll_coeff_set()` hangs forever if the APLL is
  not powered. Call `periph_rtc_apll_acquire()` first.
- **APLL resolution** is about 1.8 ppm per step. The default sample clock
  is 14,318,186 Hz (+0.3 ppm), before crystal error.
- **The I2S → DAC path plays 16-bit samples swapped in pairs:** sample *k*
  is stored at index *k* ^ 1, with the code in the high byte. Every DMA
  descriptor must hold an **even** number of samples, which is why a lone
  half-line plays as 456 samples, not 455.
- **Double-precision math is software-emulated.** A stray `double` constant
  in the per-sample loop made a frame rewrite take 27 ms of a 33 ms budget.
  With float copies plus visiting only nearby segments, it takes 6–9 ms.
  Per-line `fmod`, `sin` or division in double cost as much again (L3 hit
  28.8 ms). Periodic tests now use a 32-bit integer phase (`n × phase_inc`,
  wrapping at 2³²) with float trig. That is exact and reproducible in Python,
  and every test rewrites in under 10 ms.
- **Ties in quantization:** F2's shifts land exactly on half-steps
  (910 samples × ppm × 10⁻⁶), where float rounding in C and Python disagree.
  F2 is quantized in exact 64-bit integer arithmetic instead.

- **DMA stop signature, more data:** also about once per verifier run at
  X1 stress 5 (no signal, snow and a 5 µs skew mixed). Never during a capture
  so far.
- **Test-switch race, found and fixed 2026-10-24 (likely the DMA-stop
  cause).** The setters (`set_test`, `set_pattern`, `set_levels`,
  `set_chroma_follows`) changed the state before `rebuild()` took the lock.
  A frame written in that gap used the *new* test with the *old* buffers.
  With captions that wrote to a null buffer and crashed (StoreProhibited);
  for S10, S11, X1 and L1 it handed the DMA a null no-signal, snow or dropout
  buffer, which fits the DMA stops below (the last one logged was X1 r5,
  which uses both). Now each setter stages its change under the lock and the
  frame task writes nothing until the rebuild finishes. Three full verifier
  passes afterwards (55 configurations each) had **no DMA restarts**, against
  about one per pass before. Keep watching `dma_restarts`.
- **Verifier flake, fixed 2026-10-24:** about once per full
  `verify_timing.py` run, one test showed a 180° burst-phase error (S1 r5,
  S2 r3, S4 r5; never the same one, and never in isolation). The previous
  firmware did it too. Cause: `hold 1` didn't take the lock, so a frame write
  already in progress finished after `hold` reported the frame numbers, and
  the half held the next frame (the other colour phase). `hold` now takes the
  lock and the frame task checks it under the lock.
- **Open issue (probably fixed, see above): the I2S DMA occasionally stops.** Seen as the frame counter
  freezing, with `diag` showing the same descriptor every time. It happens
  about once per full `verify_timing.py` run, always on the switch from S8
  (variable-length frames) to S9, after the freeze/dump/unfreeze and two
  rebuilds that the verifier does. 48 plain test switches (including S8→S9)
  did not reproduce it. Mitigations: the APLL is only retuned when its rate
  changes; a frame watchdog restarts the DMA after 200 ms without an
  end-of-frame interrupt and counts it (`dma_restarts` and
  `dma_restart_last` in `info`); and runs flag any restart during a
  capture.

## Analog signal

- **The ESP32 DAC can push its output up but barely pull it down.** Into an
  unterminated line, falling edges decay slowly through the cable
  capacitance: the burst became a sawtooth and chroma came out about 4×
  too small, while luma (slow) looked fine. Every coax run needs exactly one
  75 Ω termination at its far end (see `docs/wiring.svg`).
- **Sync sits at DAC code 0, so nothing can go below it.** Noise on the
  sync tip (L2) is half clipped, and S1 can't make sync *deeper* than 40 IRE.
  When levels are calibrated, leave headroom below the sync tip (e.g. sync
  at code ~15–20).
- **The DAC's quantization floor** is about 1.9 IRE per code (direct drive),
  or 0.55 IRE rms of quantization noise: roughly 45 dB SNR. Below that, L2
  measures the DAC, not the test.
- **Line buffers place sync 16 samples in** (`LINE_ORIGIN`). With 4, S2's
  slowest edge (1000 ns, about 24 samples wide) started before the buffer
  did, giving a jump halfway down the edge instead of a slow edge.
- **Unloaded DAC output** is about 12.9 mV per code (0–3.3 V). Measured
  open-circuit: blanking 283 mV (code 21), white 911 mV (code 73). With a
  75 Ω series resistor into a 75 Ω termination, expect about half.
- **A back-terminated TBC output into an open line reads about 1.9×**
  (540 mV of sync instead of 286 mV).

## AVT-8710

- **Fingerprint series, 2026-10-15** (green unit, CH2 wired, single
  termination; `reports/20261015-11*_suite_avt-8710-green.json`,
  `fingerprints/avt-8710-green.json`): 3 graded field trials, scores
  44 / 42 / 43.
  - **Output free-runs** at +12.4 ppm against its input (12.38–12.54), so
    latency drifts (1–31 ms seen).
  - **Picture accuracy:** luma ×0.99, saturation ×0.985, hue −1.6°, output
    burst 42.8 IRE. Much closer to its input than the TBC-1000.
  - **Output H jitter:** 0.42 ns rms, half the TBC-1000's.
  - **Lost fields:** 6, falling back to its own bars at 7, as on
    2026-10-13. One trial held on through 7.
  - **Timing:** like the TBC-1000, it corrects slow timing (H2, H3, F1) but
    **not** random line jitter (−1.3 dB at 50 ns rms), head-switch skew or
    chroma phase. The 13 Oct estimate of "23 ns residual at 50 ns in" came
    from a cruder measure.
- **Double termination check:** the first V0 of the session showed CH2 at
  0.45 V p-p instead of 0.87 V, because a second 75 Ω load was on the
  generator's line. Fixed before the trials. CH2's level now flags this at
  a glance: generator sync should read about 0.23 V.

- **Its fallback output (no input)** is 8 full-field bars at 100 % white
  (100, 69, 56, 48, 36, 28, 16, 7.5 IRE). The yellow bar's hue matches ours
  (~165°), so a bar-shape check alone can be fooled; our frame marker can't
  be. The analysis only measures fields that carry our marker.
- **Lost fields:** rides through up to 6 consecutive fields of no signal or
  snow (black during the gap, often one garbled field as it re-acquires);
  from 7 it switches to its own bars.
- **Reported faults of the newer "black" units** (forum reports, no
  manufacturer statement): stuck/frozen fields, random dropped and repeated
  frames, a "ghost mode" after bad tape that only a power-cycle clears, and
  tearing, jitter and ghosting. X1 is designed around these. The unit tested
  here recovered cleanly from every X1 stress, with 1–2 ghosted fields under
  jitter alone.

- **It blanks lines 10–21** (the vertical interval). That is why the frame
  marker lives on picture lines 24 and 287.
- **With no V-sync at all (S4 rung 6)** it still outputs standard fields in
  order, but the picture sits far lower: the marker at line 201–209 after its
  V-sync instead of 15, landing somewhere different each time it locks. That is why the marker decoder searches the
  whole field and reports the marker's line.
- **Its output is always standard:** 262.5 lines per field and 0.4–0.6 ns
  rms line jitter, whatever the input does.

### First observations (2026-10-13, CH1 only, before CH2)

Observations of the green AVT-8710 from CH1 alone, before CH2 was wired.
Kept as history: the later CH2-era figures above supersede them. In
particular, **"H4 fully corrected" was wrong.** It came from the marker
offset, which rounds to 0.1 µs. The displacement measure later showed
75–101 ns of head-switch skew left.

| Test | What came out of the TBC |
|---|---|
| V0, S3 (20 missing syncs), S5 (240p), H3 (5 µs steps) | Every field passed once, in order |
| H4 (10 µs head-switch skew) | Marker at 0.0 µs offset (later measured: 75–101 ns of skew left) |
| S6 −10 lines per field | Drops a field now and then to keep up |
| S6 +10 lines per field | Repeats a frame |
| S7 dropped fields | Re-shows earlier fields (…168 169 168 169…) |
| H1 50 ns rms jitter | About 23 ns rms residual picture displacement (floor 0.7 ns) |
| S4 unserrated V-sync, EQ pulses as H sync | Locks normally |
| S4 V-sync missing in every field | Still outputs standard fields in order, but with no vertical reference the picture sits far lower: marker at line 201–209 after V-sync instead of 15, landing somewhere different each time it locks |
| S8 field-length wow (±20 lines at 2 Hz) | Occasionally repeats a field to keep its output standard |
| S9 noise bar (20 lines) | Every field passed in order |
| C1 burst 10 / 60 IRE | Burst regenerated at ~43 IRE; chroma ×1.7 (partial ACC) with ~22° hue error and jitter / ×0.65 (ACC) |
| C2 no burst | **No colour killer:** burst inserted, chroma passed with a random hue |
| C3 phase jitter 10° / 20° rms | Passed: output hue wanders ±9° / ±18° (no per-line chroma phase correction) |
| C4 hue +20° | Passed unchanged |
| L2 noise 4 IRE rms | ~2.6 IRE rms out (some noise reduction or bandwidth limiting) |
| L3 hum 20 / 40 IRE p-p | Blanking clamped flat, but the gray bar reads higher (84 / 95 IRE vs 79); not yet explained |
| L4 level 80 % / 120 % | Passed unchanged (no AGC) |
| V1 no signal | Outputs its own bars: 8 full-field bars, 100 % white (100/69/56/48/36/28/16/7.5 IRE) |
| S10/S11 lost fields | **Rides through up to 6 consecutive lost fields; from 7 falls back to its own bars.** The gap shows as black, often followed by one garbled field on recovery |
| X1 fault hunt (all 5 stresses) | Clean after every stress burst. Under stress: stuck/torn fields and back-steps with dropped/lost fields (expected for a frame sync), and 1–2 ghosted fields under jitter alone |

Picture figures are relative to the TBC's own V0 output (gray 79 IRE, yellow
chroma 70 IRE p-p, burst 43 IRE). CH1 is still unterminated, so absolute
levels wait for the tees.

In every run the output stayed standard: 262.5 lines per field and 0.4–0.6 ns
rms line jitter.

## Datavideo TBC-1000

- **Its output intermittently goes dead for about a minute.** No sync at all,
  only ~40 mV of energy near 3.58 MHz on CH1, then it recovers on its own.
  Seen twice on 2026-10-13, both times starting during an input-loss test
  (X1 stress 3, lost fields; S11 rung 2, snow). It's flagged as "output dead"
  in reports.
- **Dropout watch, 5 minutes** (60 s clean / 180 s S11:2 / 60 s clean):
  one dead sample, 134 s into the stimulus, alive again a second later.
  It's genuine: 0 syncs and under 0.2 V of swing for the whole 50 ms
  window, which two fields of snow can't produce. No dropouts on clean
  input. So the dropouts vary from under a second to about a minute, and
  have only been seen during input loss.
- **More data, 2026-10-13 evening** (reports `20261013-2122*` to `2147*`):
  - Three suites back to back (`compare_suites.py`): suites 1 and 2 were
    clean, with lost-field tolerance ∞ in both. In suite 3 the output died
    from S4 r6 to S6 r6 (~13 s) and was back by S7 r4. S10 tolerance fell
    to 2.
  - S4:6 watch (30 / 180 / 30 s): 5 episodes, lasting 1–10 s, including one
    in the clean baseline.
  - **Rig artifact found and fixed:** on every test switch the generator
    parked the DMA ring on sync-only lines with no vertical sync for
    ≥100 ms. It now parks on a standard 525-line black frame.
  - After the fix, a 4-minute clean V0 control had 0/238 dead samples.
  - After the fix, an S4:6 repeat died 98 s into the stimulus. It stayed
    dead through 30 s of clean V0 and was still dead minutes later, with
    0 syncs and ~0.2 V of swing. The generator was healthy (frames
    advancing, no DMA restart).
  - **The swing sags before it dies.** CH1 peak-to-peak fell over the
    preceding ~6 s before 4 of 7 episodes (e.g. 1.39 → 1.08 V, 1.33 →
    1.21 V). One stretch ran at ~0.24 V with sync still present. The
    control held a steady 1.45–1.52 V. This looks like the output stage or
    supply browning out (heat or capacitors?) rather than a sync-logic
    lock-up. So far it has only started while the input is disturbed or
    soon after.
- **After a power-cycle (with the parking fix): 10 suites, 45 minutes, no
  dead output** (`reports/20261013-2228*` to `2308*`, comparison
  `20261013-230832_compare10_*`). Output sync depth held at 0.42–0.43 V
  throughout, with no sag. Lost-field tolerance was ∞ / ∞ for 8 suites. In
  suites 9 and 10, one snow run each lost sync for a field (S11 r1 and
  r6), so the snow tolerance read 0 and 5. These look like one-off
  glitches, not a dying output. So the long episode before this cleared
  with a power-cycle and didn't come back in 45 minutes. Either the
  test-switch artifact was a trigger, or the fault needs a longer warm or
  stressed run to appear.
- **Heat series, 2026-10-14 19:30–20:16** (unit moved to a cooler spot):
  five graded field trials back to back, 355 runs in 46 minutes. **No dead
  output.** Comparison: `reports/20261014-heat5_compare_*`.
  - **Scores:** 53, 52, 50, 53, 51. Only 5 of 71 verdicts varied between
    trials: frame-sequence events on S5 r1, S6 r5/r6 and S8 r5, and S10 r2's
    garbled recovery field. Lost-field tolerance was ∞ / ∞ every time.
  - **Output sync depth:** a steady 0.491 V in every trial (min 0.487).
    Last night, before the unit died, it ran at 0.42–0.43 V. Cooler and
    healthier, or a wiring difference: worth watching.
  - **Latency** covered the whole 0–2 field range within a single trial. The
    delay drifts with the free-running clock and wraps, as predicted.
  - So far this fits the heat theory: it died warm and in its old spot, and
    survived 46 minutes of continuous testing after being moved. It isn't
    proof. A long run with the unit deliberately warmed would test it.
- **First graded field trial** (2026-10-14, after a power-cycle;
  `reports/20261014-192342_suite_*`, report `20261014-192558_*`):
  51 / 100, provisional.
  - **Timing:** corrects slow timing errors (H2 wow, H3 steps, F1 clock
    offset) but **not random line jitter**. H1 passes up to 10 ns rms; at
    50 ns rms in, the picture still moves 57 ns rms. Head-switch skew (H4)
    and a single displaced line (H5) also pass through. So it looks like a
    line-locked sampling clock with a slow PLL, not a per-line correcting
    TBC.
  - **Colour:** no per-line chroma phase correction (C3 hue wander passes
    straight through). ACC isn't proportional: with a weak burst,
    saturation falls 27–62 %.
  - **Picture:** V0 fails on static accuracy: luma −31 IRE against its
    input (×0.64 gain), saturation −6 %.
  - **Structure:** S4 r6 (no V-sync) garbles fields; S7 and S8 tear frames.
    S10 rides through ∞, with a garbled field on recovery at 1–4.
    S11 r3 lost sync once.
- **Died on clean input, 2026-10-14.** Alive at 18:14. By 19:01, with only
  clean V0 playing and no test switches in between, the output was dead, and
  it stayed dead for a whole 71-run field trial (`reports/20261014-190845_*`).
  CH2 showed our signal throughout. So the dead state doesn't need input loss
  to start. The dead output is a single tone at **3.548 MHz**, 0.20 V p-p:
  about 31 kHz (0.9 %) below the 3.579545 MHz subcarrier. It looks like the
  TBC's own subcarrier oscillator running unlocked, with the sync and video
  path gone.
- **CH2 wired (2026-10-14): latency and lock.** The TBC-1000's output is
  **not locked to its input**: its line period is 63555.05 ns against our
  63556.45 ns, so it runs about +22 ppm fast. It behaves as a frame
  synchroniser with its own clock. Latency was 9.1 ms (0.55 field) in one
  session and 30.1 ms (1.8 fields) an hour later. Within a session it shrinks
  by about 0.1 ms per run (22 ppm × ~4 s). Expect it to repeat a frame about
  every 25 minutes when the delay wraps. Confirmed: latency fell from
  30.1 ms to 25.0 ms over 217 s, a drift of 23 ppm.
- **Gain against the real input (CH2):** luma ×0.64 (gray 53 IRE out for
  82 in), burst brought up to ~38 IRE whatever comes in (×1.42 on our
  27 IRE burst), chroma ×1.34 with it. So it has ACC keyed on the burst. With
  a 6 IRE burst (C1 r3) chroma goes ×2.1 and hue shifts by 14°.
- **No proc amp.** Its output runs about 30 % below the AVT-8710's: gray
  bar 56 IRE (AVT 79), burst 38 (43), yellow chroma 58 (70).
- **Lost fields** vary between runs: rode through up to 8 (then its own
  pattern at 9, lost sync at 10–11) in one run, and all 11 with one odd
  261-line field in another. With no input at all it outputs black (V1)
  rather than bars.
- **Colour:** kills colour when burst is missing (C2), unlike the AVT-8710.
  Partial ACC for a weak burst (×1.6). Clamps hum cleanly.
- **Ghost detection** first flagged every field because of the lower output
  level. Marker cells are now judged against each field's own framing cells.

## Datavideo TBC-3000 (two inputs)

- **Blind test, 2026-10-23:** three field trials per input, each input
  presented as an unknown device. `fingerprints/datavideo-tbc-3000-input-a.json`
  and `-input-b.json`.
- **Frame synchroniser,** the same timing core as the TBC-1000:
  - bandwidth 0.42–0.47 kHz;
  - 110–113 % of the jitter passed at 4–8 kHz;
  - 92 % at 1 kHz (H6);
  - 79–87 ns of head-switch skew left.

  It shares 16–17 of 18 model traits with the TBC-1000: black with no
  input, ∞ lost fields, a colour killer, partial ACC, 240p converted.
- **One unit, recognisable by its crystal:** the output clock sits at
  +1.75 ppm (input A) and +1.85 ppm (input B). The TBC-1000 sits at
  +22.1 ppm, steady to ±0.04 over 9 days.
- **Controls matter; the timing core doesn't change.** Each configuration
  was run 3 times, and every reading was steady within its own trials:

  | | Input A, baseline | Input B, baseline | Input B, controls adjusted |
  |---|---|---|---|
  | Luma gain | ×0.82–0.83 | ×0.79 | ×1.02 |
  | Saturation | ×1.03 | ×1.00 | ×1.12 |
  | Hue offset | −1.1° | +3.1° | −2.6° |
  | H3 5 µs step | no jolt | no jolt | 2 lines jolted 1.2 µs |
  | L4 | passes | passes | fails |
  | Score | 48–50 (6 trials) | 51–52 | 40–43 |

  - **Input A's controls were already at baseline in the blind test;** a
    second session at baseline matched it.
  - **The adjusted controls on input B caused its step jolt and L4
    failure.** At baseline it behaves like input A and the TBC-1000 (18 of
    18 traits). My first reading, that the jolt came from input B's
    hardware, was wrong. A raised level changing how the input slices sync
    is a guess at the mechanism.
  - **At baseline the inputs still differ slightly:** hue 4° apart, luma
    and saturation about 3 % apart. Per-input front-end calibration. Input
    B's +3.1° hue is worth trimming if you capture through it.
  - **Unchanged across all four configurations:** bandwidth 424–460 Hz,
    head-switch skew 77–86 ns left, H6 91–92 % at 1 kHz, clock +1.75 to
    +1.85 ppm.
- **Cleanest output of the frame synchronisers:** noise 0.28–0.35 IRE,
  output jitter 0.57–0.58 ns.
- **Output H jitter drifts with the session:** 0.57–0.58 ns in the
  2026-10-23 trials, 0.59 the next morning, 0.62–0.67 that afternoon. An A/B
  test (V0 five times each, old and new firmware, interleaved twice) read
  0.62–0.67 on both, so it's the unit or the rig on the day, not the
  generator.
- **Vertical blanking (input A, 2026-10-24, first B-test unit):**
  - **Captions (line 21) pass intact** in both fields, clean (77 of 77) and
    through a dropped field every 30 frames (76 of 76), at ×0.84 of the
    input's level (42 IRE for 50 sent). That matches its luma gain (×0.82),
    so line 21 goes through the same level processing as the picture.
  - **After lost fields, the first field 2 after each gap has a damaged line
    21** (68 IRE of picture-like swing, bad parity): 2 of 74 fields, the
    same in two trials. Its field 1, and everything after, is intact.
  - **Lines 10–20 and 273–282 are blanked,** all 21 of them, in every field
    (305 of 305). It keeps line 21 only: a deliberate choice, presumably to
    keep captions while stripping other VBI data.
  - **AGC copy-protection pulses (B3) are removed,** with lines 12–19 flat on
    every field, as its blanking of lines 10–20 predicted. It isn't blinded:
    the gray bar stays at 63 IRE through the 1 s on / 1 s off cycle (0.0 IRE
    pumping). **Colour stripe is removed too:** striped lines come out at the
    same hue as the rest (the input shows the 180° stripe), so it decodes
    colour against a steady reference, not each line's own burst.
  - **Torn frames on line-count changes are occasional, not fixed:** S6 r6
    (+10 lines a field) tears a frame in about 1 run in 4 (2 of 8 trials, 2 of
    6 repeats). S6 r5 (−10 lines) did it once in 15 runs (the B3 regression
    trial; 6 repeats on the same firmware passed). It's the frame
    synchroniser slipping a field as the frame store wraps, so it depends on
    when that falls in the capture.

## Pioneer DVR-220 (DVD recorder, line-in to line-out)

- **First field trial, 2026-10-20** (CH2 at its input, single termination;
  `reports/20261020-164815_*`): 31 / 100, provisional.
- **Locked to its input** (+0.1 ppm), the first device that is. Latency is
  fixed within a run (steady to 0.05 ms), but varies from 2.0 to 3.5 fields
  between runs as it relocks: a frame store of about two frames.
- **Lost fields: ∞ / ∞, cleanly.** No garbled fields on recovery, the best
  of the three devices so far.
- **Picture:** luma, chroma and burst within 2 % of its input on V0, and
  hue +0.7°. But saturation varies by up to ±8 % from run to run, so most
  C and L tests miss the 5 % saturation check against V0. No colour killer
  (C2 passes chroma through).
- **Timing:** doesn't correct random line jitter (40 ns rms left at 50 ns
  in). Slow timing errors (H3, F1) and head-switch skew (H4) leave
  11–13 ns: just over the 10 ns threshold, where the TBCs passed. Missing
  syncs (S3, 20 lines) leave 179 ns: it doesn't flywheel well.
- **Rejects some inputs outright.** It outputs plain black, as with no input,
  for S4 r6 (no V-sync) and S6 r5 (10 lines short per field). It outputs
  garbled video for S1 r5 (10 IRE sync) and S4 r3 (malformed vertical
  interval).
- **To look at on the monitor:** L3 (20 IRE hum) reads the gray bar 37 IRE
  low. X1 r4 (noise bar + jitter) wasn't clean after the stress.
- **Stray marker copy.** It outputs a partial copy of our frame marker
  4 lines above the real one. That fooled the bar-line test until
  2026-10-20 (see below).

## Panasonic DMR-ES10 (DVD recorder, line-in to line-out)

- **A line TBC, by measurement** (2026-10-20 to 10-23): it corrects jitter
  up to the line rate (38–73 % left near 8 kHz, against 99–116 % for the
  others), removes head-switch skew (2.4–3.5 ns left) and shows nothing at a
  5 µs timing step. Lid-off field trials score 59–62.
- **Lost fields:** ∞ with no signal. With snow it shows its own picture from
  rung 2 (S11 tolerance 1).
- **Latency:** 4–7 fields, through its encoder path. Output clock: wanders
  between −43 and +12 ppm against its input, and often pulls in to 0.
- **Intermittent colour fault: overheating.** The bad state looks the same
  every time:
  - hue about −16° against its input (read as +164° after a frame drop,
    a 180° ambiguity);
  - chroma about ×0.94, instead of ×1.12 when healthy;
  - noise about 2 IRE, 4× normal, in slow 2-minute waves;
  - **the output clock pinned at −19.4 ppm**, which looks like a fallback
    mode.

  Once in it, the unit stays there until it cools. A channel change cleared
  it once; a quick power cycle didn't.
  - Cover on: it failed after long warm running and load. Once it failed
    spontaneously, with the generator idle. Once it failed 10 runs into a
    field trial, on H4 r5 (10 µs head-switch skew), and stayed bad.
  - Cover off: 4 back-to-back field trials (44 minutes, 216 clean-signal
    runs) with no fault. Neither our test restarts (75 per trial) nor heat
    without load triggered it.
  - The main processing chips were very hot. Pressing a finger on them,
    which both cools and presses, then power-cycling, cleared it. Suspects:
    cooling (fan, heatsink, thermal pad), or cracked BGA solder joints
    that open when hot.
- **Our test restarts flash the output black for ~0.1 s** (the parking
  frame). `tools/colour_watch.py` therefore starts V0 once and only
  listens.

## Generator: vertical blanking data (B tests)

- **Caption lines are rendered every frame,** like the frame markers: their
  bytes change each frame. Two caption lines (about 90 segments each, the
  run-in drawn as 8 ramps per cycle) take the frame rewrite from ~8.5 ms to
  ~16 ms of the 33 ms budget.
- **The segment arrays are static:** two 80-entry arrays (~3.8 KB) on the
  frame task's 4 KB stack overflowed it (stack canary).
- **B2's line map lives in the line pool:** IDs are the same in both fields,
  so 11 lines × 2 burst phases. B2 runs with 37 distinct lines, one copy
  each (no timing shifts), and 170 KB of heap free.
- **Caption timing** comes from zvbi's service table (run-in 10.5 µs after
  sync, 32 × fH) and the FCC figure's 27.382 µs start bit. The 608 standard
  itself (CTA-608-E) wasn't read; its free download needs a CTA account.
- **After a dropped field the next field arrives with the other timing
  parity,** so the analysis tells field 1 from field 2 by the caption bytes,
  not by the half-line timing.

## Generator: text cards

- **A text card needs up to ~85 distinct lines.** That's each font row of
  each text line, in both colour-burst phases, plus the frame structure.
  Test patterns need at most about 40, so `MAX_BASES` went from 64 to 96.
  A card uses one sub-sample copy per line, and leaves about 92 KB of heap.
- **The serial receive buffer is 1024 bytes** (`Serial.setRxBufferSize`). A
  ~250-byte `card` command at 921600 baud arrives in under 3 ms, faster
  than `loop()` drains the default 256-byte buffer. Command lines may be
  up to 320 characters.
- **Right after flashing,** the first command can arrive before the ESP32
  has finished booting (`verify_timing.py` failed once that way). Give it a
  second.

## Measurement pitfalls

- **Output H jitter depends on the capture rate:** 0.62 ns at 50 MS/s, 2.51
  ns at 12.5 MS/s on the same unit (V0, TBC-3000), from coarser sampling of
  the sync edges. B3 and X1 capture at 12.5 MS/s, so their 2.5 ns isn't the
  TBC. Compare jitter only between runs at the same rate.

- **A capture that starts inside a vertical interval** (fixed 2026-10-24,
  found by the PR #29 regression trial). It sees only that interval's later
  broad pulses, so its first "field" measured 0.5–3 lines short and read as
  non-standard. That failed whatever structure check it landed on, at
  random, about once per field trial on every unit. In the 39 saved trials
  that record field times, 160 runs began this way. All 36 non-standard first
  fields were among them, and none was a real field. Correcting them changes 23
  past verdicts, all fail to pass or marginal (H1 r2, S10 r8/r9 and others):
  some of the "variable" behaviours in the fingerprints came from this. The
  first field start now counts only if the capture began 12 or more lines
  before it (`observe_tbc.field_starts`). Results saved before the fix are
  corrected the same way when `grade.py` or `fingerprint.py` loads them
  (`correct_saved`), and the fingerprint library was rebuilt with it. Scores
  quoted in the device sections above are as measured at the time.

- **"Locked" means within ±0.5 ppm.** Genuinely locked devices read
  0.0 ± 0.1 ppm against their input. A blind-tested unit (2026-10-23) held a
  steady +1.75 ppm. Its latency swept the full 0–2 fields within a trial, so
  it was free-running with a crystal close to ours. The old 2 ppm threshold
  called it locked.

- **Bar lines must look like bars.** A line qualifies for picture figures
  only if gray is high, blue low, *and* yellow at least 0.7× gray. The
  DVR-220's stray marker copy (black, with the marker's start cell on the
  gray bar) passed the old test. One such line per field made the
  displacement floor read 76 ns instead of 11, and the hue jitter ±7°
  instead of ±0.5°. Frame-marker lines themselves are also excluded.

- **Generator output on CH2** (tee at the TBC's 75 Ω input): sync 0.226 V
  (79 % of 286 mV), burst 27 IRE p-p and yellow chroma 44 IRE p-p (both
  about 0.68× nominal), gray bar 82 IRE. Line jitter floor 3.1 ns rms
  (CH2's line-period jitter for H1 r4, 50 ns rms injected, reads 77 ns: a
  period spans two independently jittered syncs, so expect √2 × 50 = 71 ns).
- **Picture lines are picked relatively.** `picture_metrics` used to accept
  only lines with the gray bar above 55 IRE. The TBC-1000's gray sits near
  53, so most of its output was skipped and its picture figures were
  missing or based on a few lines. Lines now qualify when gray is above
  35 IRE and at least twice the blue bar.

- **Sync slicing:** with full-size chroma, red and blue bars (down to
  −16 IRE) and the burst trough (−20 IRE) dip into a mid-level sync slicer.
  Accept only pulses wider than 2 µs.
- **"No sync here" checks** must use a threshold below −20 IRE (we use
  −30 IRE), or the burst trough reads as sync.
- **Blanking level:** measure it on the back porch (8.2–9.1 µs after sync).
  A histogram of the whole line picks the wrong level.
- **False markers in snow:** S9's snow, scanned at 241 offsets on every line,
  occasionally passes the marker's 4-bit CRC (it once produced a "frame
  31410"). Only markers naming the run's own test code and rung are accepted;
  rejects are counted as `spurious_rejected`.
- **Vertical-interval lines have no burst:** a check that measures burst
  phase must skip them. S8's varying line counts move them to unexpected
  slot positions; that gave a false 180° error.
- **Picture displacement:** compare lines of one type against their median
  (template correlation). Edge-finding across mixed line types gives
  nonsense (530 ns "spread" on a clean signal).
