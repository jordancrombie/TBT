# Validation: what to run before a merge

TBT measures other people's hardware, so its own results have to be
trustworthy. The rule: **we don't gamble, we don't guess, we test.** A
change is merged once the checks its reach calls for have been run, and
their results are in the pull request.

## What to run, by what a change touches

| A change touches | Run before merging |
|---|---|
| Docs only | Nothing |
| Analysis or grading only (Python in `tools/`) | **Re-grade saved field trials** (`grade.py reports/<trial>.json`) and compare with their earlier grades. No capture needed, and every difference is explained in the PR |
| A firmware test definition or rendering | Build; **`verify_timing.py`, full pass**; a **smoke run** of the affected tests through a TBC on the bench |
| The firmware core (DMA ring, frame task, locking, line pool) or the catalog | All of the above, plus a **regression field trial** on the reference unit (below) |

When in doubt, take the heavier row. A change is only "isolated" if
there's evidence that it is: the code paths other tests use are
unchanged, not just believed to be.

## The reference unit

**Datavideo TBC-3000, input A, controls at baseline**
(`fingerprints/datavideo-tbc-3000-input-a.json`): the best-characterised
unit, with 6 trials, no heat fault, and it's normally on the bench. If it's
unavailable, use another unit whose fingerprint has 3 or more trials, and
say which in the PR.

Its baseline was re-measured on the calibrated rig on 2026-10-24 (3 trials,
scores 61.7–62.4); the old-rig entry is in `fingerprints/old-rig/`.
Rig-dependent traits (CH1 termination, the input level, sync depth, output
jitter and noise) are never compared; luma gain only between trials at the
same input level.

## A regression field trial passes when

Run `run_suite.py full --grade` on the reference unit, then compare with
its fingerprint:

1. **Every model trait matches** (timing class, output lock, lost-field
   tolerance, colour killer, and so on).
2. **Unit traits fall within the fingerprint's range:** gain, hue,
   head-switch skew left, and the clock offset within about ±0.5 ppm (a
   crystal drifts that much over a day). Rig-dependent traits aren't
   compared.
3. **No test verdict changes,** except tests the fingerprint lists as
   variable for that unit.
4. **The rig stays clean:** 0 generator DMA restarts during captures, and the
   CH2 input check is ok on every run.
5. **New or changed tests behave as described** in their docs.

A new test group changes the weighting, so the overall score isn't
comparable across catalog versions. Compare per-test verdicts and traits
instead.

## Results

- A trial that passes is reported in the PR in a few lines. Its files
  needn't be kept.
- A trial that shows something unexpected is kept (`reports/`, plus
  `--keep` runs if the raw captures matter). The finding goes in
  [bench-notes.md](bench-notes.md), and the cause is found before merging:
  either the change or the device.

## Closing issues

Never close an issue without a comment saying what was decided:

- **Done:** what was built (tests, tools, docs), how it was validated, what
  it found, anything deferred, and the PR. Close it with that comment, or
  have the PR close it and then comment.
- **Not done:** why (out of scope, covered by existing tests, not feasible),
  what covers it instead if anything, and what would make us revisit it.
- **Deferred:** a comment with the assessment and where it sits in TODO.md;
  leave it open.

The requester should be able to read the issue alone and know what
happened, without reading the PR.

## Planned tooling

A tool that compares a trial with a fingerprint and lists every trait and
verdict that differs. It is the same comparison `identify.py` needs ("which
unit is this?"), turned round ("is this still the same unit?"), so one tool
can serve both.
