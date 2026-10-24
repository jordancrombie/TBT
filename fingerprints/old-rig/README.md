# Old-rig fingerprints

Measured from 2026-10-13 to 2026-10-24 on TBT's first rig, before it was
calibrated:
- **CH1 unterminated** (the TBC's output read twice the volts);
- **generator at about 82 % of nominal level** (sync 235 mV, white 605 mV,
  where the standard is 286 / 714).

Each entry records both (`ch1_termination`, and the sync depths). What they
mean for the figures:
- **Behaviour traits** (timing class, lost-field tolerance, colour killer, VBI
  and so on) held when units were re-measured on the calibrated rig.
- **Luma gain reads about 18 % low:** a TBC regenerates its own sync but
  passes the picture in proportion to its under-level input.
- **Timing figures are biased:** with full-size sync, the TBC-3000 corrected
  more (head-switch skew left 77 → 57 ns, correction bandwidth 424 → 523 Hz).
- **Output jitter and noise read lower** than a terminated rig (twice the
  volts against the same scope noise).

They're kept as a reference for anyone whose rig is set up the same way, and
as the record of each unit before re-measurement. The calibrated entries are
in `fingerprints/`.
