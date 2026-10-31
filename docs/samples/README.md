# Sample field trials

One field trial of every device in the fingerprint library, one per input
for the units that have several. Each sample is the trial with the median
score of the 3 that built that device's fingerprint, so it is a typical
run, not the best one.

<!-- samples:start -->
| Device (input) | Score | Trial | Runs | Full report |
|---|---|---|---|---|
| [AVT-8710 (green)](avt-8710-green/README.md) | 40 | 2026-10-25 | 83 | [open](https://jordancrombie.github.io/TBT/samples/avt-8710-green/report.html) |
| [Datavideo TBC-1000](datavideo-tbc-1000/README.md) | 50 | 2026-10-25 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-1000/report.html) |
| [Datavideo TBC-3000 (input A)](datavideo-tbc-3000-input-a/README.md) | 62 | 2026-10-24 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-3000-input-a/report.html) |
| [Datavideo TBC-3000 (input B)](datavideo-tbc-3000-input-b/README.md) | 54 | 2026-10-24 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-3000-input-b/report.html) |
| [Datavideo TBC-4000 input A](datavideo-tbc-4000-input-a/README.md) | 49 | 2026-10-28 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-4000-input-a/report.html) |
| [Datavideo TBC-4000 input B](datavideo-tbc-4000-input-b/README.md) | 50 | 2026-10-31 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-4000-input-b/report.html) |
| [Datavideo TBC-4000 input C](datavideo-tbc-4000-input-c/README.md) | 53 | 2026-10-31 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-4000-input-c/report.html) |
| [Datavideo TBC-4000 input D](datavideo-tbc-4000-input-d/README.md) | 52 | 2026-10-31 | 83 | [open](https://jordancrombie.github.io/TBT/samples/datavideo-tbc-4000-input-d/report.html) |
| [Panasonic DMR-ES10](panasonic-dmr-es10/README.md) | 60 | 2026-10-24 | 83 | [open](https://jordancrombie.github.io/TBT/samples/panasonic-dmr-es10/report.html) |
| [Pioneer DVR-220](pioneer-dvr-220/README.md) | 37 | 2026-10-24 | 83 | [open](https://jordancrombie.github.io/TBT/samples/pioneer-dvr-220/report.html) |
<!-- samples:end -->

## How these are laid out for GitHub

A field trial's report (`run_suite.py --html`) is one self-contained HTML
page: no external files, about 2 MB, with around 160 inline SVG charts that
take their colours from the page's stylesheet, so they follow the viewer's
light or dark setting. That works in a browser and nowhere else on GitHub:
github.com shows an `.html` file as source, and its Markdown viewer strips
inline `<svg>`. So each sample comes in two forms.

- **`README.md`, the summary, renders on github.com.** It has the trial's
  setup and score, a grade for every test with one mark per rung (✅ 🟡 ❌),
  the fault-test findings, and the charts:
  - every output field on V0, the clean signal;
  - every output field on the hardest S10 rung, while input fields are lost;
  - one line of the output on V0, when the trial kept its waveforms (see
    below; none of these did).

  The charts are the report's own SVGs written out as separate files and
  linked as images. Each file carries the report's palette in a `<style>`,
  with a `prefers-color-scheme` block. An image follows the viewer's
  system light or dark setting, not GitHub's theme setting; every cell
  carries its own text colour, so the charts read on either GitHub theme. The legends that sit beside the charts in
  the report are written as captions in their place.
- **`report.html`, the full report, opens through GitHub Pages.** Every run
  has its card: measurements, checks against limits, field strips and
  waveform. Pages serves `docs/` from `main` as
  `https://jordancrombie.github.io/TBT/`; `docs/.nojekyll` makes it serve the
  files exactly as committed. Where the trial was run with `--html`, this
  is its own report, copied (the TBC-4000 samples). The older trials were
  run without it, so theirs is re-written from the saved trial: the same
  page, dated with the trial's time, but without the per-run waveforms,
  which the trial's JSON doesn't keep. Each summary says which it is.

### Making or refreshing a sample

```
python3 tools/sample_report.py reports/<time>_suite_<dut>.json
```

This re-grades the saved trial (so its score matches what the trial
printed), writes `docs/samples/<device>/`, and refreshes the table above.
Every trial in the library was graded against frame-TBC ideals (the
default), the DMR-ES10's included, so the samples are too; `--class line`
exists for line-TBC ideals but would change the scores. A sample needs
the trial's `reports/<time>_suite_<dut>.json`, which isn't committed
(`reports/` is ignored), so samples are made on the bench machine.

When the grader or the report changes, regenerate every sample from the
same trials so they stay comparable.
