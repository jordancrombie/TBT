# The tests, in plain words

What each TBT test does to the signal, which real-world problem it imitates,
what a good TBC should do with it, and every rung (version) of it.

**How to read this page**

- **Rungs.** Each test is a ladder of *rungs*, from mild (rung 1) to severe.
  Run one with `run_test.py H1 4`, or several with `run_suite.py H1:1-6`.
  The default field trial runs one representative rung of every test, plus
  every rung of S10, S11, B1, B3 and X1.
- **Two kinds of TBC.** A *line TBC* straightens each line's timing but passes
  the field structure through as it came. A *frame TBC* or synchroniser
  stores whole frames and always outputs standard fields. Where they should
  behave differently, both ideals are given.
- **Units.** 1 µs = 1000 ns. One NTSC line lasts 63.6 µs; one field is
  262.5 lines (1/60 s); one frame is two fields. IRE is the video level
  scale: sync −40, black 7.5, white 100. "p-p" means peak to peak.
- **Timing resolution.** Timing shifts move in steps of 70 ns today (the
  generator's memory allows two sub-sample copies of each line). A shift
  smaller than half a step rounds to none: see H1.
- **Colour-under.** By default TBT imitates VHS and Betamax: sync, picture
  and the colour signal's envelope are disturbed, but the colour carrier
  itself stays steady, as a deck's colour processor delivers it.
- **Catalog version.** Test model `perturb/1`, firmware `ntsc-gen 0.5.0`
  (0.5.0 added B3, AGC pulses; 0.4.0 added B1 and B2, captions and the VBI
  line map; 0.3.0 added H6 and the title card). On
  the serial console, `tests` prints the catalog the firmware actually runs.
  If this page and the firmware disagree, the firmware is right (and this
  page needs fixing).

Grading thresholds are in [design.md](design.md#scoring-implemented-provisional).

## V: Verification

### V0 · Clean baseline
**What it does:** sends perfect colour bars with no faults.
**Why:** it's the reference for everything else. It shows what the TBC does
to a perfect signal: its luma and colour gain, hue accuracy, and timing
floor. Every other test is judged against the TBC's own V0 result, so each
grade reflects only how the TBC handled that test's fault.
**Good TBC:** output identical to the input.
**Rungs:** 1.

### V1 · No signal
**What it does:** sends nothing at all (0 V).
**Why:** to see what the TBC shows when its input disappears: black, its own
bars, or a frozen frame. It also checks the analysis itself. A TBC's own
fallback bars must never be mistaken for our signal, and V1 proves they
aren't.
**Good TBC:** its own fallback output (bars or black). Not graded.
**Rungs:** 1.

## H: Horizontal timing (the core TBC job)

The timing errors a tape deck makes as the tape stretches, the heads spin and
the transport wobbles. A TBC exists to remove these.

### H1 · Random line jitter
**Imitates:** tape stretch and head-drum noise. Each line arrives a slightly
random amount early or late.
**Good TBC:** straight vertical edges. The picture shouldn't shimmer or
"wiggle" at all.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Jitter, rms | 5 ns | 10 ns | 20 ns | 50 ns | 100 ns | 200 ns |

**Note:** with today's 70 ns timing steps, rungs 1 and 2 deliver no jitter
at all (every line rounds to no shift), and rung 3 arrives as occasional
70 ns jumps rather than a fine shimmer. Rungs 4–6 are accurate. Treat a
"pass" on rungs 1–2 as meaningless until the resolution is raised.

### H2 · Sinusoidal jitter (wow and flutter)
**Imitates:** a capstan or drum with a periodic speed error. Timing swings
smoothly back and forth.
**Good TBC:** as H1, at every rate.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Swing, peak | 50 ns | 100 ns | 200 ns | 500 ns | 1 µs | 2 µs |
| Rate | 1 Hz | 3 Hz | 5 Hz | 10 Hz | 20 Hz | 30 Hz |

### H3 · Timing step
**Imitates:** a sudden jump in timing, such as a splice or a tape-tension
change. The whole picture timing jumps, and jumps back every 0.5 s.
**Good TBC:** the picture stays put, recovering within a few lines of each
jump. TBT measures how many lines the picture takes to settle after each
jump (it captures 1.1 s so at least two jumps are seen). A line TBC shows no
disturbance at all.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Jump | 0.25 µs | 0.5 µs | 1 µs | 2 µs | 5 µs |

### H4 · Head-switch skew
**Imitates:** the head switch near the bottom of a VHS picture, where one
video head hands over to the other. The last few lines of each field
(lines 520–256 across the field boundary) arrive shifted, which is the
familiar "flagging" bend at the bottom of a tape picture.
**Good TBC:** no bend at the bottom of the picture.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Shift | 0.5 µs | 1 µs | 2 µs | 5 µs | 10 µs |

### H5 · Displaced single line
**Imitates:** a single glitched line (a tape crease, say). One line per field
(lines 100 and 362) arrives early or late, and the lines after it are
normal.
**Good TBC:** no tear, and the following lines are unaffected.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Shift (samples) | +2 | −2 | +4 | −4 | +10 | −10 | +20 | −20 |
| Shift (time) | +140 ns | −140 ns | +279 ns | −279 ns | +698 ns | −698 ns | +1.4 µs | −1.4 µs |

### H6 · Jitter frequency sweep
**Imitates:** nothing on its own. It measures **how fast a timing error can
change and still be corrected**, which is what separates a line TBC from a
frame synchroniser. Each rung is a sine-wave timing wobble of the same size
(200 ns peak) at a different speed.
**Good TBC:** a line TBC re-times every line, so it removes the wobble at
every rung. A frame synchroniser's lock only follows slow changes: it
removes the 50 Hz rung but passes the faster ones.
**Graded on:** the share of the wobble still on the output. At 1 kHz and
below, under 30 % must be left; above, under 50 % is a minor check. On a
two-channel rig, H1 also gives the full curve (see "jitter transfer" in
[design.md](design.md)).

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Wobble speed | 50 Hz | 250 Hz | 1 kHz | 3 kHz | 7 kHz |
| Size | 200 ns peak | 200 ns | 200 ns | 200 ns | 200 ns |

## F: Frequency

Errors in the *rate* of the signal rather than individual lines: a deck
running slightly fast or slow, or drifting.

### F1 · Clock offset
**Imitates:** a deck running slightly fast or slow. Line rate and colour
carrier both move together.
**Good TBC:** locks and follows. A frame TBC outputs at its own (or its
reference's) rate, dropping or repeating frames as needed.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Offset, ppm | +10 | −10 | +30 | −30 | +100 | −100 | +300 | −300 | +1000 | −1000 |

### F2 · Line rate not locked to colour
**Imitates:** colour-under playback, where the line timing comes from the
tape but the colour carrier comes from the deck's crystal, so the two
slide against each other (the "SCH" relationship drifts).
**Good TBC:** locks, and the hue stays correct.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Line rate vs colour, ppm | +10 | −10 | +50 | −50 | +200 | −200 | +1000 | −1000 |

### F3 · Slow drift
**Imitates:** a deck whose speed wanders slowly, over a 10-second cycle.
**Good TBC:** stays locked the whole time.

| Rung | 1 | 2 | 3 |
|---|---|---|---|
| Swing, peak | 50 ppm | 300 ppm | 1000 ppm |

## S: Sync and structure

Damage to the sync pulses and to the field structure itself: what worn tape,
trick play and badly made recordings do.

### S1 · Weak sync
**Imitates:** low-level or worn tape, where the sync pulses come out
shallow.
**Good TBC:** locks anyway, and regenerates full 40 IRE sync.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Sync depth (40 is normal) | 30 IRE | 25 IRE | 20 IRE | 15 IRE | 10 IRE |

### S2 · Slow sync edges
**Imitates:** a bandwidth-limited playback path that rounds the sync edges.
**Good TBC:** locks with no extra jitter, and outputs sharp edges.

| Rung | 1 | 2 | 3 |
|---|---|---|---|
| Edge rise time (10–90 %) | 250 ns | 500 ns | 1 µs |

### S3 · Missing line syncs
**Imitates:** a dropout that wipes out the sync on a run of lines (from
line 100).
**Good TBC:** "flywheels" through: it keeps the line timing going and
regenerates the missing syncs, with no tear.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Lines without sync | 1 | 2 | 5 | 10 | 20 |

### S4 · Malformed vertical interval
**Imitates:** recordings and decks that mangle the vertical sync, the pulses
that mark the start of each field. Copy-protection and cheap
camcorders are classic sources.
**Good TBC:** stable vertical lock, and a standard vertical interval out
(frame TBC).

| Rung | What's wrong |
|---|---|
| 1 | Equalizing pulses replaced by ordinary line syncs |
| 2 | Vertical sync without its serrations (one long pulse) |
| 3 | Both of the above |
| 4 | Vertical sync missing in field 1 every 30 frames |
| 5 | Vertical sync missing in field 1 every 6 frames |
| 6 | Vertical sync missing in every field |

### S5 · Progressive 240p
**Imitates:** game consoles and some computers, which send 262 lines per field
with no half-line, so the two fields never interlace.
**Good TBC:** a line TBC passes it unchanged. A frame TBC outputs a stable
picture, either passing 240p or converting it to standard fields.
**Rungs:** 1.

### S6 · Wrong line count
**Imitates:** a deck in trick play, or a damaged tape, where fields come out
with lines missing or extra (removed or repeated at lines 200 and 462).
**Good TBC:** a frame TBC outputs standard 262.5-line fields anyway. A line
TBC passes the count through.

| Rung | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Lines per field changed by | −1 | +1 | −3 | +3 | −10 | +10 |

### S7 · Dropped field
**Imitates:** a field lost entirely (field 2 missing every N frames), as in a
dropout during the vertical interval or a bad edit.
**Good TBC:** a frame TBC repeats a field cleanly, with no tear or roll.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| A field dropped every | 60 frames | 30 frames | 15 frames | 6 frames | 2 frames |

### S8 · Field-length wow
**Imitates:** a transport whose speed swings enough that each field has a
different number of lines.
**Good TBC:** a frame TBC outputs standard fields, dropping or repeating as
needed, never rolling.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Lines added/removed, peak | 1 | 2 | 5 | 10 | 20 |
| Rate | 0.5 Hz | 1 Hz | 1 Hz | 2 Hz | 2 Hz |

### S9 · Search noise bar
**Imitates:** fast-forward or rewind with picture search: a band of noise with
no sync, moving down the picture (23 lines a frame).
**Good TBC:** flywheels through the bar, and the rest of the picture stays
straight with no roll.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Bar height | 2 lines | 5 lines | 10 lines | 20 lines | 40 lines |

### S10 · Lost fields (no signal)
**Imitates:** the signal disappearing completely for a moment: a bad cable,
a tape gap, the deck switching modes. Once a second, N fields in a row
are replaced by 0 V.
**Why it matters:** this measures **how much loss a TBC rides through**. Some
units (the AVT-8710 at 7 fields) give up and show their own colour bars,
which ruins a capture.
**Good TBC:** holds the last frame (or blanks) through the gap, never falls
back to its own pattern, and relocks at once. The field trial reports the
tolerance as the largest N handled, where 11 counts as "∞, more than 10".

| Rung | 1 | 2 | 3 | … | 10 | 11 |
|---|---|---|---|---|---|---|
| Fields lost in a row | 1 | 2 | 3 | … | 10 | 11 (∞) |

### S11 · Lost fields (snow)
**Imitates:** as S10, but the gap is filled with snow (noise with no sync), as
from a blank or damaged stretch of tape.
**Good TBC:** as S10.
**Rungs:** 1 to 11 fields, as S10.

## C: Colour

### C1 · Burst level
**Imitates:** tape with weak (or hot) colour. The colour burst, the reference
the TV uses to decode colour, comes in at the wrong level.
**Good TBC:** regenerates a normal 40 IRE burst and keeps saturation right
(automatic colour control, ACC).

| Rung | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Burst (40 is normal) | 30 IRE | 20 IRE | 10 IRE | 60 IRE (too hot) |

### C2 · No burst
**Imitates:** a black-and-white recording, or colour lost entirely.
**Good TBC:** a clean monochrome picture with no colour noise. That needs a
"colour killer", which the AVT-8710 lacks and the TBC-1000 has.
**Rungs:** 1.

### C3 · Colour phase jitter
**Imitates:** colour that wobbles line to line, so the hue shimmers.
**Good TBC:** steady hue, if it corrects colour phase line by line. Many TBCs
don't, and pass the shimmer through.

| Rung | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Phase jitter, rms | 2° | 5° | 10° | 20° |

### C4 · Hue offset
**Imitates:** a recording with a tint error.
**Good TBC:** passes it unchanged (with the proc amp at unity). A TBC
shouldn't silently "correct" tint.

| Rung | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Hue shift | 5° | 10° | 20° | 45° |

## L: Levels, noise and dropouts

### L1 · Dropouts
**Imitates:** tape dropouts, where oxide is missing and a streak of snow
replaces part of a line.
**Good TBC:** passes them (or conceals them, given a dropout-detect signal),
and the timing isn't upset.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Streak length | 2 µs | 5 µs | 10 µs | 20 µs | 50 µs |
| Streaks per field | 1 | 2 | 5 | 5 | 10 |

### L2 · Noise
**Imitates:** noisy tape (generation loss, worn heads). Random noise is added
to the whole picture.
**Good TBC:** stays locked, and passes the noise without adding to it.

| Rung | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Signal-to-noise | 40 dB | 34 dB | 28 dB | 22 dB | 16 dB |
| Noise, about | 1 IRE rms | 2 IRE | 4 IRE | 8 IRE | 16 IRE |

### L3 · Hum
**Imitates:** a ground loop or mains interference: a 60 Hz wave rolling up
the picture as bands of light and dark.
**Good TBC:** a frame TBC clamps it out (DC restore). A line TBC may pass it.

| Rung | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Hum, p-p | 5 IRE | 10 IRE | 20 IRE | 40 IRE |

### L4 · Video level
**Imitates:** a recording that's too dark or too bright overall.
**Good TBC:** passes the level unchanged, or corrects it if it has AGC or a
proc amp.

| Rung | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Level (100 is normal) | 80 % | 90 % | 110 % | 120 % |

## B: Vertical blanking interval

The lines between the vertical sync and the picture (lines 10–21 of each
field) carry data on many tapes: closed captions on line 21, and on some,
timecode (VITC) or other data in lines 10–20. A TBC may pass these lines,
blank them, or damage them. For an archive, captions are content: a capture
that loses them has lost something.

### B1 · Captions (line 21)
**Imitates:** a captioned tape. Line 21 of both fields carries standard
closed captions (EIA/CTA-608). Field 1 is a caption that a TV with captions
on (CC1) shows as "Brought to you by the / Media Archive Project", sent again
every 32 frames. Field 2 carries a frame counter, so repeated or lost fields
show up.
**Why it matters:** captions are part of the recording. The analysis checks
every field's two caption bytes against what was sent for that frame:
intact, damaged (parity), missing (stripped), or carrying another frame's
data.
**Good TBC:** every caption arrives intact, including around dropped and lost
fields.

| Rung | What else happens |
|---|---|
| 1 | Nothing: clean input |
| 2 | A field dropped every 30 frames (as S7) |
| 3 | 2 fields of no signal once a second (as S10) |

### B2 · VBI line map
**Imitates:** a tape with data in the whole vertical interval. Lines 10–20 of
field 1 and 273–282 of field 2 each carry an ID for their line, and a
25/50/75 IRE staircase. Captions are on line 21 as in B1.
**Why it matters:** shows which lines a TBC passes, blanks, moves to another
line, or damages, and whether it changes their levels.
**Good TBC:** every line passed in place at its own level. Blanking lines
10–20 is common by design and counts as a minor miss; moving or damaging them
fails.
**Rungs:** 1.

### B3 · AGC pulses (copy protection)
**Imitates:** a copy-protected commercial tape (Macrovision-like). Lines
12–19 and 275–282 each carry 6 pairs of a *pseudo-sync* pulse (down to sync
level) and an *AGC pulse* at 110 IRE, above peak white. A recorder's automatic
gain control measures sync against these and sees a signal far too strong, so
it turns the picture down. The licensed Macrovision spec isn't public: this
is built from the Ryan patents (US4631603, US4819098), within their stated
ranges.
**Why it matters:** many commercial VHS tapes carry it. A TBC can remove it
(good for whatever captures its output), pass it on, or be fooled by it
itself: its picture level pumps, or it loses lock.
**Good TBC:** locks and keeps its picture level steady; ideally removes the
pulses (and the colour stripe).

| Rung | Signal |
|---|---|
| 1 | AGC pulses steady at 110 IRE |
| 2 | Cycling: 1 s at 110 IRE, then 1 s at blanking (pseudo-syncs stay), the brightness-pumping pattern of copied tapes |
| 3 | Rung 2 plus colour stripe: the colour burst inverted on 4 lines in every 20 of the picture |

## X: Fault hunt

### X1 · Stress and recovery
**Imitates:** stretches of really bad tape, to provoke faults that outlast the
damage. Newer "black" AVT-8710 units are reported to get stuck fields,
random dropped or repeated frames, ghosting, and a "ghost mode" that
persists until a power cycle.
**How:** a 3-second cycle of 1 s clean, 1 s of stress, 1 s clean. The
output is split into before / stress / settling / after windows, so a fault
that outlasts the stress shows up in "after".
**Good TBC:** no stuck or blended fields, and clean again within 3 frames of
each burst.

| Rung | Stress |
|---|---|
| 1 | Line jitter, 200 ns rms |
| 2 | Dropped fields: field 2 missing in every other frame |
| 3 | Lost fields: 3 fields of no signal in every 20 |
| 4 | A 40-line noise bar plus 100 ns rms jitter |
| 5 | "Bad tape" mix: 100 ns rms jitter, a 5 µs head-switch skew, a 20-line noise bar, and 2 lost fields in every 30 |
