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
- **Luma gain reads about 18 % low** on units that pass the picture in
  proportion to their under-level input (the Datavideos: TBC-3000 ×0.79 →
  ×0.94, TBC-1000 ×0.63 → ×0.83). The AVT-8710 scales the picture to its
  input's sync, so it wasn't affected (×0.99 both).
- **Some early entries (2026-10-13 to 10-15) captured H3 for 0.39 s,** which
  can miss its 0.5 s step, so their H3 passes and "slow timing corrects"
  traits may be untested (the AVT's was).
- **Timing figures are biased:** with full-size sync, the TBC-3000 corrected
  more (head-switch skew left 77 → 57 ns, correction bandwidth 424 → 523 Hz).
- **Output jitter and noise read lower** than a terminated rig (twice the
  volts against the same scope noise).

They're kept as a reference for anyone whose rig is set up the same way, and
as the record of each unit before re-measurement. The calibrated entries are
in `fingerprints/`.
