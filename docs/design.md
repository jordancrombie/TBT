# TBT test catalog & grader contract

The design of TBT (Time Base Torture): what each test sends, what a perfect TBC should do with
it, how results will be scored, and what the generator hands the grader.
Moved into the repo from a claude.ai doc on 2026-10-14 and brought up to date.
Measured facts live in [bench-notes.md](bench-notes.md), and open work in
[TODO.md](../TODO.md).

## Purpose and rig

Each test sends a known, deliberately damaged NTSC signal through the TBC
under test. The grader then judges how close the TBC's output comes to the
undamaged signal. The generator's job is to make every perturbation exact,
repeatable, and described in a machine-readable manifest.

![Test rig: the ESP32 feeds the TBC; CH2 records the generator output, CH1 the TBC output](rig.svg)

- **Generator:** ESP32 DAC on GPIO25 through a 75 Ω series resistor,
  commanded over USB serial by the host tools.
- **CH2, reference:** a tee at the TBC's input, so the analysis sees exactly
  what was sent.
- **TBC under test,** then a monitor and vectorscope on loop-through for a
  human check.
- **CH1, result:** the end of the chain, terminated in 75 Ω.
- **Analysis and grading:** `tools/observe_tbc.py` reads the manifest plus
  the CH1 (and CH2) capture, and `tools/grade.py` scores its output (see
  Scoring).

**One-channel rigs are supported.** With `--channels 1` only CH1 is captured,
so a single-channel scope and no tee are enough. Everything that depends on
the output alone still works: field classes, the frame markers, lost-field
tolerance, the fault hunt and the dropout watch. What's lost is the input
check, latency, and gain against the real input. Picture levels are then
judged against nominal values. Wiring is in the README.

The TBC re-times the signal, so its output is not sample-aligned with the
input. The analysis therefore compares CH1 against the *ideal* signal the
manifest describes, not against CH2 sample for sample. It uses the frame
marker to know which frame and test rung it's looking at. CH2's job is to
confirm that the input was what the manifest says, and to anchor latency and
gain.

## Signal conventions

"Nominal" means NTSC-M per SMPTE 170M as the generator produces it. Every
perturbation is stated as a change from that.

| Quantity | Convention |
|---|---|
| Sample clock | 4 × fsc = 14.318182 MHz; 1 sample = 69.84 ns; 910 samples per line |
| Horizontal time origin | 50 % point of the H-sync leading edge. In the generator's buffers, sample 16 (`LINE_ORIGIN`), leaving room for early shifts and slow edges |
| Time units in the manifest | ns for timing, samples where the DAC grid matters (both given) |
| Levels | IRE: sync −40, blanking 0, setup 7.5, white 100; 1 V p-p into 75 Ω nominal |
| Line numbers | SMPTE 1–525; field 1 = lines 1–263.5, field 2 = 263.5–525 |
| Picture rows | 0–485 top to bottom, interlaced (field 1 lines 21–263, field 2 lines 283–525) |
| Colour sequence | 4 fields (frames A and B). Each test states the frame its sequence starts on (`frame_start_mod4`), so dropped fields keep the subcarrier continuous |
| Subcarrier phase | Burst on −U (180°). Hue measured relative to burst, as a vectorscope does |
| Pattern | Each test runs over a stated pattern (default SMPTE bars), described as Y/U/V segments per row |
| Colour model | **Colour-under** (default, VHS/Betamax): sync, luma and the colour envelopes are disturbed, but the 3.58 MHz carrier stays on a continuous reference, as the deck's crystal-referenced colour processor delivers it. *Chroma follows timing* (direct colour, U-matic/1") is a switch, recorded in the manifest's `chroma` field |

## Test catalog

The catalog has 34 tests in 8 groups. [tests.md](tests.md) describes each one in plain words, with every rung. Each test is tagged with the TBC class it
targets: line TBC, frame TBC/synchroniser, or both. Its manifest gives the
ideal output per class, so a line TBC that rightly passes a dropped field
through is not marked down. Each test sweeps one parameter up a severity
ladder, from rung 1 (mild) upward. `tests` on the serial console prints the
live catalog. If this table and the firmware ever disagree, the firmware
(`src/perturb.cpp`) is right.

### H — Horizontal timing (the core TBC job)

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| H1 | Random line-to-line jitter | rms ns (Gaussian, seeded) | 5, 10, 20, 50, 100, 200 (see the resolution note below) | Straight vertical edges; output H jitter < 5 ns rms |
| H2 | Sinusoidal jitter (wow/flutter) | peak ns @ Hz | 50 ns @ 1 Hz … 2 µs @ 30 Hz, 6 rungs | As H1 at every rate |
| H3 | Timing step | µs, toggling every 0.5 s | 0.25, 0.5, 1, 2, 5 | Picture stays put; recovers within N lines (measured) |
| H4 | Head-switch skew | µs, lines 520–256 shifted until V-sync | 0.5, 1, 2, 5, 10 | No bend at the bottom of the picture |
| H5 | Displaced single line | samples, at lines 100 and 362 | +2, −2, +4, −4, +10, −10, +20, −20 (8 rungs) | No tear; following lines unaffected |
| H6 | Jitter frequency sweep | sine jitter, 200 ns peak @ Hz | 50, 250, 1000, 3000, 7000 | Corrected at every rate (a line TBC); a frame synchroniser only corrects the slow rungs |

**Timing resolution.** Shifts are quantized to 2/`subsample_steps` samples:
70 ns with the 2 copies every test gets today (since 2026-10-13; 35 ns with
4). H1's random jitter is bounded at ±3.46 σ, so its 5 and 10 ns rms rungs
never reach half a step and deliver no jitter at all; the 20 ns rung arrives
as 70 ns steps on about 8 % of lines (its rms is right). From 50 ns rms up,
and for H2–H6, the delivered timing is within a few percent of the ladder
(the reference model computes it exactly). Raising the copy count is open
work (TODO).

H7, velocity error (timing that drifts *within* a line), is deferred to the
tape-deck phase. It needs pre-stretched line copies.

**Line TBC or frame synchroniser?** The deciding property is *correction
bandwidth*: how fast a timing error can change and still be corrected. A
line TBC re-times every line, so it corrects close to the line rate. A frame
synchroniser's lock follows only slow changes. TBT measures it two ways:
- **H6** gives the share of jitter passed at five rates. It works on any rig.
- **Jitter transfer** (two-channel rigs, from H1 rung 4 and up) compares
  each line's input timing error (CH2) with its output picture shift (CH1).
  It reports the share passed in six bands from 150 Hz to 8 kHz, and the
  bandwidth where half gets through.

Bandwidth alone isn't enough: any digital decoder with a line-locked clock
follows sync quickly. Calibrated on four devices (2026-10-20 to 10-23):

| | AVT-8710 (frame sync) | Datavideo TBC-1000 (frame sync) | Pioneer DVR-220 (no TBC) | Panasonic DMR-ES10 (line TBC) |
|---|---|---|---|---|
| Correction bandwidth (H1, CH2) | 0.4–0.5 kHz | 0.4 kHz | 2.8–3.8 kHz | 2.6 kHz to over 8 kHz |
| Jitter passed at 4–8 kHz | 110–116 % (amplified) | 108–111 % (amplified) | 99–112 % (amplified) | 38–73 % |
| H6 at 1 kHz | 87 % | 95 % | 13 % | 21–23 % |
| H4 head-switch skew left | 75–101 ns | 85–109 ns | 10.6–12.5 ns | 2.4–3.5 ns |
| H3 5 µs step | one line jolted 1.3 µs | no jolt (glides through) | one line jolted 1.4 µs | nothing above the 50 ns floor |

So `fingerprint.py` sorts devices into three timing classes:
- **Frame synchroniser (slow lock):** bandwidth under 1 kHz, or more than
  half the 1 kHz H6 jitter passed.
- **Line TBC:** fast lock, *and* jitter near the line rate still reduced
  (under 90 % passed), head-switch skew gone (under 5 ns), and no jolt at a
  step (under 300 ns).
- **Fast lock, no per-line correction:** everything else. That's the
  decoder of a DVD recorder without a TBC.

Single-channel rigs use H6 instead of the bandwidth. The thresholds come
from one or two units of each class, so more devices may move them.

### F — Frequency

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| F1 | Line and subcarrier offset together | ppm (APLL retune) | +10, −10, +30, −30 … +1000, −1000 (10 rungs) | Locks; output at nominal rate if genlocked |
| F2 | fH not locked to fsc | H rate against a fixed subcarrier, ppm (SCH drifts) | +10, −10, +50, −50 … +1000, −1000 (8 rungs) | Correct hue; no SCH drift on output |
| F3 | Slow frequency drift | peak ppm over a 10 s period | 50, 300, 1000 | Continuous lock |

F2 and F3 are done in the timing model, not by retuning the clock.

### S — Sync and structure

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| S1 | Sync amplitude | sync depth, IRE | 30, 25, 20, 15, 10 | Locks; regenerated 40 IRE sync |
| S2 | Slow sync edges | 10–90 % rise, ns | 250, 500, 1000 | Locks; output edges nominal |
| S3 | Missing H syncs | consecutive lines with no sync, from line 100 | 1, 2, 5, 10, 20 | No tear; lines regenerated |
| S4 | Malformed vertical interval | variant | 1 EQ pulses as H sync · 2 unserrated V-sync · 3 both · 4/5 V-sync missing in field 1 every 30/6 frames · 6 V-sync missing in every field | Stable vertical lock |
| S5 | Progressive 240p | 262 lines, no half-line | 1 rung | Passes or flags; no roll |
| S6 | Wrong line count per field | lines removed/repeated at lines 200 and 462 | −1, +1, −3, +3, −10, +10 | Stable output with a standard line count |
| S7 | Dropped field | field 2 missing every N frames | 60, 30, 15, 6, 2 | Standard 262.5-line fields out; repeats a field cleanly, no tear or roll |
| S8 | Field-length wow | lines added/removed per field, peak @ Hz | 1@0.5, 2@1, 5@1, 10@2, 20@2 | Standard fields out; drops/repeats allowed, no roll |
| S9 | Search noise bar | height of a band of sync-less snow moving 23 lines/frame | 2, 5, 10, 20, 40 | Flywheels through the bar; stable lock, no roll |
| S10 | Lost fields (no signal) | consecutive fields of 0 V, once a second | 1 … 11 (11 = "∞, more than 10") | Holds or blanks through the gap; never falls back to its own pattern; relocks at once |
| S11 | Lost fields (snow) | consecutive fields of sync-less snow, once a second | 1 … 11 | As S10 |

### C — Burst and colour

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| C1 | Burst amplitude | burst p-p, IRE (40 nominal) | 30, 20, 10, 60 | Correct saturation (ACC) |
| C2 | No burst | burst removed | 1 rung | Monochrome output; no colour noise |
| C3 | Burst + chroma phase jitter | rms degrees, line to line | 2, 5, 10, 20 | Stable hue |
| C4 | Static hue offset | picture hue against burst, degrees | 5, 10, 20, 45 | Passes unchanged (proc amp off) |

### L — Levels, noise, dropouts

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| L1 | Dropouts | snow over part of a line: µs × count per field | 2×1, 5×2, 10×5, 20×5, 50×10 | Concealed (needs a DOC input) or passed |
| L2 | Additive noise | SNR, dB (100 IRE / rms, unweighted) | 40, 34, 28, 22, 16 (DAC floor ~45 dB) | Locks; noise passed, not amplified |
| L3 | Hum / DC wander | 60 Hz sine on video, IRE p-p | 5, 10, 20, 40 | Clamped flat |
| L4 | Video level | white level, % | 80, 90, 110, 120 | Passes, or corrected if the TBC has AGC |

C3, L2 and L3 reuse each line's pre-rendered copies as phase, noise or DC
versions, so their resolution is `subsample_steps` levels (2 today).
The manifest records each variant's value.

### V — Verification

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| V0 | Clean baseline | none | 1 rung | Identical to the input; sets the floor for every other figure |
| V1 | No signal | none | 1 rung | Captures the TBC's own fallback output, proving the analysis never mistakes it for ours |

### B — Vertical blanking interval

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| B1 | Captions (EIA/CTA-608) on line 21 of both fields: field 1 a pop-on caption, field 2 a frame counter | disruption | 1 none · 2 a field dropped every 30 frames · 3 2 fields of no signal once a second | Captions passed intact |
| B2 | VBI line map: an ID and a 25/50/75 IRE staircase on lines 10–20 and 273–282, captions on line 21 | none | 1 rung | Lines passed in place, levels unchanged (blanked by design: minor) |
| B3 | AGC pulses (Macrovision-like): 6 pseudo-sync (−40 IRE, 2 µs) + AGC (110 IRE, 3 µs) pairs per line, every 8 µs from 12 µs, on lines 12–19 and 275–282 | mode | 1 steady · 2 cycling 1 s on / 1 s off · 3 cycling + colour stripe (burst inverted on 4 lines in 20) | Locks, picture level steady (not blinded); pulses and stripe removed (minor) |

Caption timing follows 608 as decoders read it (zvbi: run-in from 10.5 µs,
32 × fH bit rate): a 7-cycle run-in at 503 kHz from 10.5 µs after the sync
edge, the start bit at 27.382 µs, then two bytes NRZ, LSB first, 7 bits plus
odd parity; 0 is blanking, 1 is 50 IRE. Field 1 repeats a 32-frame cycle:
RCL, ENM, PAC row 14, "Brought to you by the", PAC row 15, "Media Archive
Project", EOC, control codes sent twice. Field 2 carries the frame number,
6 bits per byte plus 0x20. `src/vbi.*` and `tools/perturb_model.py` hold both.

B3 follows the Ryan patents' ranges (pseudo-sync at least 0.5–1 µs to sync
tip, 6 µs or more apart; AGC pulse at least 3 µs at 100–125 % of peak white;
20–30 or more pairs a field): 48 pairs a field here. The slow cycle follows
the published descriptions of the brightness pumping ("a couple of seconds"
on, then reduced); 1 s each way fits one 2.2 s capture. Colour stripe uses
the bands the patents describe (4 lines inverted in every 20), outside the
VBI. It is a model of the mechanism, not the licensed signal.

### X — Fault hunt

| ID | Test | Parameter | Ladder | Ideal TBC output |
|---|---|---|---|---|
| X1 | Stress then recovery: a 90-frame (3 s) cycle of 1 s clean, 1 s stress, 1 s clean | stress type | 1 jitter 200 ns rms · 2 dropped fields · 3 lost fields · 4 noise bar + jitter · 5 bad-tape mix | No stuck or blended fields; clean again within 3 frames of each burst |

X1 targets the faults reported for newer "black" AVT-8710 units: stuck
fields, random dropped and repeated frames, ghosting, and a "ghost mode" that
persists after bad tape. The output is split by input frame into before,
stress, settling and after windows. A fault that outlasts the stress shows up
in the "after" window.

## What the analysis measures today

`tools/observe_tbc.py` observes; it does not grade. For each run it reports:

- **Output timing:** H-sync count, line period, line jitter, field lengths
  (262.5 lines is standard).
- **Field classes.** Every complete output field is one of:
  - ours (carries our marker, so its frame number is known);
  - ours, unmarked (our picture, but the marker line was lost);
  - blended (our marker with in-between cells: two frames mixed);
  - blank;
  - garbled (matches neither ours nor a uniform pattern);
  - the TBC's own pattern (fallback bars, for example).

  Frames whose two fields come from different input frames are counted as
  stuck or torn.
- **Frame sequence** from the markers: back-steps, skipped and repeated
  frames, single-field frames, and the marker's line and offset after the
  output's V-sync (vertical position and residual H error).
- **Picture figures** on our own fields only: burst, yellow hue and chroma,
  gray level, blanking wander, noise. They're scaled from the output's own sync
  depth, so termination errors don't skew them. **A TBC that falls back to its
  own bars can never pass as our signal.**
- **Output dead:** no vertical sync on CH1. Such runs are flagged and left out
  of tolerance figures. `tools/dropout_watch.py` samples the output once a
  second over minutes to catch these episodes.
- **VBI data (B1, B2):** on each of our fields, line 21's caption is
  decoded (run-in, start bit, 16 bits, parity) and checked against what the
  generator sent for that frame: intact, damaged, missing, wrong, or another
  frame's data (VBI passed out of step with the picture). Which field's data
  it is comes from the bytes, since after a dropped field the next field
  arrives with the other timing parity. The caption streams of each field
  show repeated or skipped data. B2 also decodes each line's ID: passed in
  place, moved, blank or damaged, with the staircase levels.
- **AGC pulses (B3):** on our fields' lines 12–19 and 275–282, the
  pseudo-sync and AGC pulse levels: each line passed, stripped (flat) or
  altered. The gray bar's level in the cycle's on half against its off half
  (pumping: the TBC's own AGC fooled). On rung 3, chroma against each line's
  own burst on striped and unstriped lines: 180° apart means the stripe is
  still on the output.
- **Loss and hunt summaries:** per S10/S11 rung, whether the gap was handled
  (no fallback, no sync loss), clean, and how (held, blanked, garbled on
  recovery). A suite gives the lost-field tolerance. Per X1 rung, the four
  windows.
- **With CH2 (two-channel runs):**
  - **Input check:** markers decoded in order, and no generator DMA restart.
    V1 must show no signal on CH2.
  - **Latency:** the same field (frame and parity) on both channels.
  - **Output line rate against the input:** 0 ppm (within ±0.5) means the TBC locks its
    output to its input. A free-running frame synchroniser shows an offset,
    a latency that drifts, and a dropped or repeated frame each time it
    wraps.
  - **Gain against the real input:** burst, chroma and gray ratios, and the
    hue shift.
  - **Output level** (sync depth in volts), to catch a sagging output. It
    also tells whether CH1 is terminated (about 0.28 V) or open (about
    0.56 V), which fingerprints record: an open CH1 doubles the volts and
    lowers the measured jitter and noise floors.

## Scoring (implemented, provisional)

`tools/grade.py` grades a field trial from its saved analysis. Use
`run_suite.py --grade`, or `grade.py reports/<time>_suite_<dut>.json` to
re-grade an old trial. The thresholds are first proposals and haven't been
checked against a known-good TBC, so every grade is labelled provisional.

**Each run gets one verdict:**

| Verdict | Meaning |
|---|---|
| pass | every check met |
| marginal | only minor checks missed: a garbled field on recovery, a repeated frame, peak displacement, the picture not quite where V0 put it |
| fail | a main check missed |
| invalid | the rig is at fault: CH2 shows the generator's own output was wrong, or the analysis took a V1 fallback for our picture |
| info | nothing to grade: V1, or the event fell outside the capture |

**A test's grade:**
- *Ordered ladders:* the highest rung passed with every rung below it also
  passed.
- *Unordered ladders* (S4 variants, S6 ±, C1 with its 60 IRE rung, X1
  stress types): k of n rungs passed.
- *Overall:* a weighted mean of the group scores, out of 100. Pass counts
  1, marginal 0.5, fail 0. Weights: H 3, S 2, F 1.5, C 1.5, L 1, B 1, X 1, V 1.

**Checks:**

| Check | Applies to | How it is measured | Pass threshold |
|---|---|---|---|
| Output alive, standard fields, never its own pattern | every test (standard fields: not S5–S8 for a line TBC) | V-syncs; field lengths; field classes | 262.5 lines; 0 fallback fields |
| Output H stability | every test | line-period jitter of the output's own H sync | < 5 ns rms |
| Frame sequence | continuous-input tests | markers: back-steps, skips (main); repeats, single-field frames (minor) | 0 |
| No garbled, ghosted or torn fields | all but S10/S11/X1 | field classes; frames whose fields disagree | 0 |
| Picture steady vertically | marker tests | marker line after V-sync: spread (main); offset from V0 (minor) | ±1 line |
| Jitter corrected | H6 | share of the 200 ns peak sine jitter (141 ns rms) left on the output, excess over V0 | < 30 % at ≤ 1 kHz (main); < 50 % above (minor) |
| Back in place after a step | H3 | lines from the first visibly displaced line until the picture is back (displaced = more than 4× the median spread, at least 30 ns) | ≤ 3 lines |
| Residual horizontal displacement | H1–H5, F, S1–S3, S9 (the timing tests; S3 minor under `--class line`, since a line TBC needs each line's sync) | each colour-bar line's luma against the median line, relative to the line's own sync (Gaussian low-pass removes chroma; offset, gain and tilt fitted alongside the shift); excess over V0's floor | < 10 ns rms (main), < 35 ns at the 99th percentile (minor) |
| Hue | picture tests | yellow vs burst. V0: against the input (CH2) or nominal 167.1°. Other tests: against the TBC's own V0 transfer applied to this test's input | < 3° |
| Saturation | picture tests | yellow chroma ÷ burst, judged the same way | < 5 % |
| Luma | picture tests | gray bar, judged the same way (L4: unchanged or AGC-restored both pass) | < 2 IRE |
| Output burst | V0 (C1: burst as on V0) | burst amplitude | 40 ± 2 IRE p-p (C1: ± 2 of V0's) |
| Colour killed | C2 | chroma left with no burst | < 3 IRE p-p |
| Hue stability | C3 | line-to-line hue jitter | < 3° |
| Noise not amplified | L2 | added gray-bar noise (each side's V0 noise removed in quadrature), out ÷ (in × the TBC's luma gain) | < ×1.1 |
| Hum clamped | L3 | blanking wander | < 1 IRE rms |
| Rides through the gap; clean recovery (minor) | S10, S11 | loss summary | handled; no garbled fields |
| Clean after stress; no stuck or ghosted fields (minor) | X1 | hunt windows | after window clean |
| Captions intact; every caption intact (minor); in step with the picture (minor); caption stream as sent (minor) | B1, B2 | line 21 decoded on every one of our fields: intact = the exact bytes of a frame within 3 of the picture's (the offsets are reported); repeated or skipped data in field 2's frame counter, against the input's | ≥ 98 % of fields (B1 r2/r3: ≥ 90 %, since a field damaged as the TBC recovers is minor, as in S10); 0; ≤ the input's |
| VBI lines not corrupted; lines 10–20 passed (minor) | B2 | line IDs | 0 moved or damaged; 0 blanked |
| Not blinded; AGC pulses removed (minor); output sync as on V0 (minor); colour stripe removed (minor) | B3 | picture level in volts above black against V0's (and the cycle's on half against its off half), since a unit may change its sync; pulse lines flat (a unit that puts out its own protection reads "replaced"); output sync depth against V0's; hue on striped lines | ± 5 IRE (a fooled AGC shifts far more; 2–3 IRE isn't it); all lines flat; ± 5 %; < 90° |

**Not yet graded:**
- *Recovery time* for S4 and S6 (H3's is graded, above).
- *Correction ratio:* input displacement ÷ output displacement, in dB
  (H6 and the jitter transfer now give it per frequency).
- *Burst phase stability.*
- *Lost-field tolerance:* reported, not thresholded.
- *Latency and lock:* reported, not graded.

Rules:

- **V0 runs first in every field trial.** Its picture displacement is the
  measurement floor (scope noise: about 11 ns rms on an unterminated CH1,
  20 ns on CH2). Other runs are judged on their excess over it, in
  quadrature. If V0's *input* check fails, the rig is at fault and its
  results are invalid. A TBC that fails V0's picture checks, for example
  through low luma gain, has simply failed them.
- **Only fields carrying our marker are measured.** A field of the TBC's own
  pattern scores as a failure, never as a pass.
- **Static picture accuracy is V0's job.** V0 judges the TBC's picture
  against what went in: gain, hue, saturation and burst. Every other test is
  judged against the TBC's own V0 transfer applied to that test's input. So a
  TBC with low luma gain fails V0 once, and each other test grades only how
  it handled its own fault.
- **Single-channel runs** use the nominal picture (adjusted for what the test
  changes) where two-channel runs use CH2. That matters because the
  generator's real output differs from nominal (hue about 2.6° and chroma
  7 % low on yellow at the calibrated levels).
  When CH2's picture can't be measured for a test (S1's shallow sync, L3's
  hum, L2's heaviest noise), the input is worked out from V0's input
  instead.
- `--class line` grades the structure tests (S5–S8) against the line-TBC
  ideal, where the structure passes through. Frame is the default.

## Grader contract

Each run gives the grader three things:

- a JSON manifest;
- the capture: CH1, plus CH2 on two-channel rigs;
- a frame marker inside the video itself.

The manifest says exactly what was sent and what the ideal output is. It is
enough to rebuild the ideal waveform without the generator.

**Frame marker.** Lines 24 (field 1) and 287 (field 2), the picture's top rows,
carry 36 cells of 1.4 µs starting 10.5 µs after the sync edge, at 7.5 or
70 IRE. The cells are:

| Cells | Content |
|---|---|
| 2 | start, "10" |
| 8 | test code |
| 4 | rung |
| 16 | frame counter |
| 4 | CRC-4 |
| 2 | stop, "01" |

It lets the grader match any captured field to its manifest entry, whatever
the TBC's delay. It sits in the picture for two reasons. TBCs commonly blank
the vertical interval; the AVT-8710 blanks lines 10–21. And the picture is
above every line the structure tests add, remove or skew. Lost lines take
priority over the marker. A decoded marker counts only if it names the run's
own test and rung, because snow occasionally passes the 4-bit CRC by chance.

**Determinism.** Every perturbation is a pure function of the absolute line
number n = frame × 525 + line index, so sequences never loop. Random jitter
uses a seeded hash (lowbias32) summed Irwin-Hall style, which is
integer-exact. Periodic tests use an integer phase increment. F2's
quantization uses exact integer arithmetic. `tools/perturb_model.py` is the
reference implementation for the grader. `tools/verify_timing.py` checks the
firmware against it in 60 configurations (about 90 s): shifts agree to
0.002 ns, every line length matches, and the B tests' caption bytes, line
IDs and AGC pulse levels decode as sent.

**Manifest example**, trimmed from a real run (H1, rung 4):

```json
{
  "schema": "tbc-test/1",
  "generator": {"firmware": "ntsc-gen 0.3.0", "sample_hz": 14318186.442,
                "nominal_sample_hz": 14318181.818, "clock_ppm_base": 0.0,
                "levels": {"sync_code": 0.0, "white_code": 73.0},
                "subsample_steps": 2, "max_ext_samples": 10},
  "test": {"id": "H1", "code": 17, "name": "random line jitter", "rung": 4, "rungs": 6,
           "params": {"rms_ns": 50}, "seed": 1, "model": "perturb/1", "phase_inc": 0,
           "chroma": "colour_under", "targets": ["line_tbc", "frame_tbc"]},
  "ideal": {"pattern": "unperturbed",
            "line_tbc": "timing corrected; vertical edges straight, picture steady",
            "frame_tbc": "timing corrected; vertical edges straight, picture steady"},
  "timing": {"samples_per_line": 910, "lines_per_frame": 525, "half_line_samples": 456,
             "loop": "none (frame counter)", "time_origin": "50% of H-sync leading edge",
             "structure": "perturb/1 frame_slots"},
  "marker": {"lines": [24, 287], "cells": 36, "cell_us": 1.4, "start_us": 10.5,
             "lo_ire": 7.5, "hi_ire": 70.0,
             "layout": "start 10, code 8, rung 4, frame 16, crc4 (poly 0x3 init 0, 28 bits MSB first), stop 01"},
  "pattern": {"name": "smpte_bars", "regions": [{"rows": [0, 323], "key": 0,
              "segments": [{"x0": 0.0, "x1": 0.142857, "y0": 76.875, "y1": 76.875, "u": 0.0, "v": 0.0}]}]},
  "capture": {"rate_hz": 50000000.0, "samples": 20000000, "volts": "raw * scale + offset",
              "channels": {"ch1": "result (end of chain, after TBC)", "ch2": "reference (generator output)"},
              "started_unix": 1792015263.6, "frames_at_start": 62, "dma_restarts_during": 0},
  "dut": {"name": "Datavideo TBC-1000", "notes": "composite in/out"},
  "generator_state": {"frames": 62, "dma_restarts": 0, "...": "the generator's info at capture time"}
}
```

The example shows one bar of one region; real manifests list every region
and segment. The `capture`, `dut` and `generator_state` blocks are added by
the host runner, which saves the manifest as `manifest.json` next to
`capture.npz`. The capture holds raw int16 samples per channel (`ch1`, and
`ch2` when captured), plus `scale`, `offset` and `rate`. A single-channel
run's `capture.channels` lists CH1 only. Positions are fractions of the
active width, and levels are IRE. The encoding is the same Y/U/V segment
model the firmware renders from.

## Generator design

- **DMA ring:** two halves of up to 600 descriptors each. Each half holds one
  frame of any length, so frames can drop fields or change line count.
- **Frame task:** an end-of-frame interrupt wakes it to rewrite the half that
  just finished, as "the other half's frame + 1", while the other half
  plays. That takes 6–9 ms of a 33 ms frame (about 16 ms with B1/B2's
  per-frame caption lines). A watchdog restarts the DMA if no end-of-frame
  arrives for 200 ms; restarts are counted, and runs that see one are
  flagged. None has been seen since the test-switch race fix (2026-10-24).
- **Timing faults are in the ring, not the picture.** A descriptor's length
  sets where the next line's sync falls, in 2-sample (140 ns) steps.
  Pre-rendered sub-sample-shifted copies of each line fill in the fine steps.
- **Pools:** variant copies (timing, carrier, noise and DC), snow, dropout,
  dead (0 V) and caption lines. Memory is the binding constraint: after the
  pool, about 170–190 KB is free, and the copy count is whatever the
  remaining budget allows (2 for every test today; 1 for B2).
- **Test switches** park the ring on a standard 525-line black frame with full
  vertical sync while the new test is built. An earlier version parked on
  sync-only lines with no V-sync, which could provoke the TBC under test.
  Each setter stages its change under the frame lock, and the frame task
  writes nothing until the rebuild finishes, so no frame is ever built from
  the new test with the old buffers. `hold` takes the lock too, so the frame
  numbers it reports match the halves' contents.

### Phases

1. **Phase 0, rig calibration (done 2026-10-24):** CH2 wired 2026-10-14;
   the chroma shortfall (0.68×) went away on 2026-10-15; CH1 terminated and
   `levels` calibrated (283 / 718 mV) on 2026-10-24. Every unit is being
   re-measured on the calibrated rig. Optional: trim `ppm`.
2. **Phase 1, timing (done 2026-10-13):** descriptor-length control, frame
   task, frame marker, manifest, host capture runner. V0, H1–H5, F1.
3. **Phase 2, structure and colour (done 2026-10-13):** S1–S9, C1–C4, F2,
   F3.
4. **Phase 3, levels and noise (done 2026-10-13):** L1–L4, the suite runner
   and HTML reports.
5. **Phase 4, fault tests (done 2026-10-13/14):** S10, S11, V1 and X1, the
   dropout watch, suite comparison, CH2 input check and latency,
   single-channel mode.
6. **Phase 5, grading and fingerprints (2026-10-14 to 10-15):** `grade.py`
   with provisional thresholds and picture displacement; `fingerprint.py` and
   the `fingerprints/` library.
7. **Phase 6, line TBC or frame synchroniser (2026-10-20 to 10-24):** H6, the
   jitter transfer and H3 step recovery, calibrated on four devices; the
   timing class in fingerprints; the colour watch. A blind test identified a
   Datavideo TBC-3000, and both its inputs, against the library.
8. **Phase 7, vertical blanking data (2026-10-24):** B1 captions and the B2
   VBI line map (issue #25); B3 AGC pulses and colour stripe (issue #27).
   Every unit re-measured on the calibrated rig (2026-10-24/25).
   A second blind test identified a Datavideo TBC-4000 (2026-10-28); all
   four of its inputs fingerprinted, and a sample report per device and
   input published in `docs/samples/` (2026-10-31).
9. **Next:** an automatic identification and regression tool (the blind
   test's comparison, formalised).
10. **Later:** H7 velocity error, and a tape program mode
   that steps through rungs on a timed schedule for recording test tapes,
   for tape-based TBCs with no passthrough.

## Open questions

- [ ] **Genlock.** If a TBC takes a reference input, the ESP32 can output
      black burst on GPIO26 (DAC2) from the same DMA stream. That makes
      "output at nominal rate" testable. The TBC-1000 free-runs at about
      +22 ppm against its input.
- [ ] **Pass thresholds and group weights** in Scoring are first proposals.
      They need checking against a known-good TBC.
- [x] **Generator chroma level.** CH2 read chroma and burst at about 0.68× of
      nominal until 2026-10-14; from 2026-10-15 on, 0.92–0.97×, on every
      unit (the TBC-1000 included, so it wasn't that unit's input). Some
      change on the rig overnight; which one isn't recorded. The ~5 % left
      fits the DAC's own roll-off (sinc, 0.90 at fs/4).
- [ ] **TBC-1000 dead output.** Its output intermittently dies, the swing
      sagging first. A power-cycle cleared it. Trigger and cause are open
      (bench notes).
- [x] **Vertical interval:** TBCs blank it (the AVT-8710 blanks lines 10–21,
      the TBC-3000 lines 10–20), so the marker moved to picture lines 24/287.
- [x] **Jitter model:** colour-under is the default (VHS/Betamax). Direct
      colour stays as an option.
- [x] **Grader language:** Python with NumPy, reading `capture.npz` and
      `manifest.json`, as the existing tools do.
- [x] **Capture length per rung:** slow tests capture longer automatically
      (S10/S11 and B1 1.3 s at 25 MS/s, B3 2.2 s and X1 3.3 s at 12.5 MS/s;
      `CAPTURE_HINTS` in `tools/run_test.py`). Output H jitter reads higher
      at lower rates (2.5 ns at 12.5 MS/s against 0.6 at 50).
- [x] **One-channel rigs:** supported with `--channels 1`.
