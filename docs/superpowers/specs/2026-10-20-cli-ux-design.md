# BlockProbe — CLI UX Design

**Date:** 20 Oct 2026
**Status:** Draft for approval
**Scope:** Terminal output design for every user-facing surface of `blockprobe`.
**Source:** PRD.md v0.1 (19 Oct 2026), ROADMAP.md (19 Oct 2026)

**Language:** every user-facing string is English. The tool is submitted to an
international hackathon, and the issue drafts it produces get filed against the
OpenMinion repository, whose templates and existing issues are in English.

---

## Intent and the why

BlockProbe is a CLI tool, so the terminal *is* the product's UI. There is no web
frontend, no dashboard, no separate design system. Everything the hackathon
reviewer sees — the run, the results, the diff, the issue draft, the refusal to
publish — is rendered as text in a terminal window.

This document fixes what that text looks like. It exists because the demo is a
4:30 video: the whole product has to read clearly at a glance, on one screen,
with no scrolling back to explain what happened.

The secondary why: BlockProbe's whole subject matter is *failure*. Probes fail,
providers time out, credentials expire. A tool whose subject is failure cannot
afford to fail confusingly. That drives most of the decisions below.

This document does not change the product scope in PRD.md. It only describes how
the existing surfaces look.

---

## Goals

1. A reviewer watching the demo understands what happened without narration.
2. A failure is never ambiguous: status, cause, and next action are all visible.
3. Every output is copy-pasteable into a report, a bug, or a CI log.
4. Terminal output degrades cleanly — piped to a file, no colour, narrow width,
   Windows PowerShell.
5. The look is deliberate and restrained. No decoration that carries no meaning.

## Non-goals

- A web frontend, HTML report, dashboard, or hosted service (already a PRD
  non-goal; FR-17 stays a "Could").
- A reusable design system, component library, or theme.
- Themeable colour schemes beyond the two required palettes (status, severity).
- Any change to the probe set, the SDK surface, the agent design, or the report
  file formats. Those are fixed by PRD.md.

## Anti-goals

- Emoji as status or decoration. Emoji render inconsistently across terminals
  and read as generic. Status is a word plus colour.
- Heavy box-drawing frames. Box characters break column alignment the moment
  one cell wraps.
- Spinners as the primary progress signal. A spinner says "something is
  happening" but never says what finished.
- Colour as the only carrier of meaning. Everything coloured is also a word.
- Tracebacks for ordinary mistakes.

---

## Constraints

- Windows PowerShell and Linux are both first-class (PRD §13). Unicode box and
  arrow characters must be verified on both before being adopted; anything that
  misaligns gets replaced with ASCII.
- Output must be pipeable. When stdout is not a TTY, or `NO_COLOR` is set, or
  `--no-color` is passed, all ANSI colour is dropped.
- The tool runs on the echo provider during harness tests, where model-dependent
  probes are SKIPped.
- Width: assume 80 columns. Layouts must not require more.
- The probe set, building-block names, status vocabulary, and issue template
  come from PRD §8 and PRD §12. This document does not rename them.

---

## Decisions

### D1 — Run output: live-first streaming

Chosen over "quiet until the end" and over "live plus a framed panel".

Every probe prints one line the moment it finishes:

```
  ▸ P01 contract        PASS    0.4s
  ▸ P02 agent_run      PASS    1.8s
  ▸ P03 tool_call      FLAKY   3.4s   2/3
  ▸ P06 errors         FAIL    0.9s   0/3
```

Why: the run is the beat where the tool proves it is calling a real model.
A table of results could be fabricated; six lines appearing one at a time with
real latencies cannot. Live output also means a 10-minute run is not 10 minutes
of nothing.

The full result table still renders at the end, so nothing is lost.

The probe id (`P01`) and building-block name are canonical from PRD §8. The
short label (`contract`) is a display name owned by the probe definition, not
by the render layer, so it cannot drift as probes are added.

### D2 — Reports render in the terminal, not only as files

`building-blocks-tested.md` and `what-we-learned.md` exist as files (PRD
requirement). The same content is also rendered to the terminal, so the demo
never leaves the terminal. Opening an editor mid-video costs time and breaks
the flow.

The `.md` files remain the canonical artifact for submission.

### D3 — Stream separation: progress on stderr, data on stdout

Progress and status lines (D1, the analyst phase line, the publish preview
prompt) go to **stderr**. The machine-readable payload (`--json`) and the
final report rendering go to **stdout**.

This is what makes `--json` pipeable: `blockprobe run --analyze --json > out.json`
produces a valid file, because the live probe lines went to stderr and did not
mix into it.

### D4 — The written notes are human-owned once generated

`blockprobe report` writes `building-blocks-tested.md` and `what-we-learned.md`
**only if the file does not already exist**. It never overwrites a file that has
been hand-edited, unless `--force` is passed. PRD §14 and ROADMAP Phase 4 both
expect these notes to be edited by hand before submission, and regenerating
them would destroy that work.

Consequence: the terminal view of the analyst note renders the **current
contents of `what-we-learned.md`**, not a fresh re-serialisation of the
findings. What the reviewer sees on screen is exactly what gets submitted. The
structured findings written by the analyst remain available in
`runs/<id>/findings.json` for the evidence-ref validator and for re-rendering
the results table.

### D5 — Analyst note: flat list, evidence inline

Findings render as a flat numbered list. Each finding carries its building
block, severity, evidence reference, summary, and suggested improvement on
consecutive lines:

```
  1  Tool argument types are not enforced
     Tools · severity medium · E-P03-2
     A @tool function received an int for a str field in 1 of 3 runs ...
     → coerce or raise before invoking the tool function
```

Chosen over footnote-with-evidence-index (too long in a terminal, forces the
eye to jump) and over severity badges (adds a second colour axis and makes the
block busier without adding information).

The note ends with the "what worked well" list, as PRD §12 requires.

### D6 — Diff: delta-first, grouped

The diff groups changes into three sections and prints only what changed:

```
  0.1.3 → 0.1.4      pass rate 83% → 92% (+8)     p50 2.4s → 2.1s (-0.3s)

  regressions
  ▸ P06 errors        FAIL  →  FLAKY   0/3 → 2/3

  fixes
  ▸ P03 tool_call     FLAKY →  PASS    2/3 → 3/3

  unchanged · P01 P02 P04
```

Chosen over a full two-column table (the reviewer has to scan for the story)
and over side-by-side panels (columns get too wide, changes get missed).

Status transitions are classified explicitly:

| From | To | Classified as |
|---|---|---|
| FAIL | FLAKY | regression |
| FAIL | PASS | fix |
| FLAKY | PASS | fix |
| PASS | FAIL | regression |
| PASS | FLAKY | flaky (not worse, but no longer stable) |

Latency changes are labelled `faster` / `slower` only when the delta is at
least 20%.

Cases outside that table:

- **Probe present in only one run** — listed under `added` or `removed`, never
  silently dropped. This happens when comparing a `quick` suite against a `full`
  suite, or across SDK versions that add a probe.
- **Status unchanged, pass-rate changed** (`PASS 3/3` → `PASS 2/3`) — listed
  under `unstable`, with both rates shown.
- **Runs differ by provider rather than by version** — the header names the
  provider axis instead of the version axis: `default → portal`. If the runs
  differ on both axes, the header is two lines, one per axis.

### D7 — Publish gate: full preview plus typed confirmation

```
  ISSUE-01  [P06] Provider errors surface as answer text
  severity high · openminion 0.1.3, 0.1.4 · python 3.11.9 · windows

  ──────────────────────────────────────────────────────────
  Title:  [P06] Provider errors surface as answer text
  Affected version / environment: ...
  ──────────────────────────────────────────────────────────

  target: github.com/anomalyco/openminion · will create a public issue

  Type PUBLISH to confirm, anything else to cancel:
  ▸ no
  Cancelled. Nothing was published.
```

The whole draft is shown, then the literal word `PUBLISH` must be typed. This
is what PRD FR-13 specifies ("needs typed confirmation"), and it means the
refusal is visible on screen — which is a demo beat in its own right.

Chosen over an interactive TUI picker (needs a fullscreen TTY, will not run in
CI, and costs implementation time in the tightest phase of the schedule) and
over a dry-run/`--yes` pair (removes the refusal moment entirely).

Rules around the gate:

- **The match is exact and case-sensitive.** After trimming surrounding
  whitespace, the input must equal `PUBLISH`. Anything else, including
  `publish` or `yes`, cancels. A safety gate that accepts a near-miss is not a
  gate.
- **Without a TTY** (CI, piped stdin) `publish` refuses with a usage error
  rather than reading stdin and comparing. There is no non-interactive
  confirmation path; publishing is a deliberate human action.
- **`gh` availability and authentication are checked before the prompt.** The
  user is never asked to type `PUBLISH` and then told it cannot work.
- **The target repository** comes from configuration, not from a hardcoded
  default in the render layer.
- Every publish attempt, including cancellations, is recorded in
  `runs/<id>/publish-log.json`.

### D8 — Security-sensitive drafts fail closed

A draft may be flagged security-sensitive (PRD §3, §12). Such a draft must
never reach the public publish path; it is routed to a private note instead.

The flag lives in the **front matter of the draft `.md` file itself**, not in a
sidecar manifest. Front matter travels with the file when a draft is moved,
copied, or hand-edited, and PRD §14 expects hand-editing of these drafts.

The `publish` command **fails closed**: if the front matter is missing,
unparseable, or has no explicit security field, the draft is treated as
security-sensitive and refused for public publishing, with a message saying so.
A hand-edited draft can therefore never accidentally strip the protection and
become publishable.

The terminal preview renders the draft body verbatim, so what is shown is
exactly what would be posted.

### D9 — Help grouped by task; errors in three parts

`blockprobe --help` is grouped by what the user is trying to do. The command
set is the one PRD §11 defines — `doctor`, `run`, `analyze`, `matrix`, `diff`,
`report`, `publish`:

```
  probe
    run       run the probe suite, write results to runs/<id>/
    doctor    check environment, provider and budget
    matrix    run the same suite across several openminion versions
  report
    report    render results.json, tables and notes
    diff      compare two runs (versions or providers)
    analyze   run the analyst over an existing run
  ship
    publish   publish an issue draft after a typed confirmation
```

An error always has three parts, in this order: what happened, what was
available, what to do next.

```
  error: unknown profile "quik"

  available profiles
    quick   6 probes, ~20-40 model calls
    full    11 probes, ~60-120 model calls

  → did you mean: --profile quick
```

Chosen over a short one-line help (leaves the user to hunt through docs) and
over man-page-plus-traceback (a typo should not cost a stack trace).

**`--profile` and `--provider` are different namespaces.** `--profile` selects
the probe suite (`quick`, `full`) and is fixed by PRD §6. `--provider` selects
the provider/model profile (`default`, `portal`) per PRD FR-14 and
PRD §11 `config/profiles/`. The D9 error block above is therefore about suite
profiles; a mistyped provider name produces the same three-part shape, listing
the available provider profiles and the flag to use.

### D10 — Colour and symbol vocabulary

| Meaning | Word | Colour | Note |
|---|---|---|---|
| Pass | `PASS` | green | |
| Unstable | `FLAKY` | yellow | always paired with pass-rate `n/N` |
| Fail | `FAIL` | red | |
| Skipped | `SKIP` | dim | feature absent in this version |
| Harness error | `ERROR` | dim | never drafted as a bug (PRD §8) |
| Severity high | `severity high` | red | |
| Severity medium | `severity medium` | yellow | |
| Severity low | `severity low` | dim | |

Rules:

- Colour is never the only signal. Every status is a word.
- Symbols are limited to `▸` (probe), `→` (transition, suggestion), `·`
  (separator), `─` (rule). Each must be verified on Windows PowerShell; if a
  glyph misaligns, fall back to ASCII.
- No emoji anywhere.
- Colour is dropped when stdout is not a TTY, when `NO_COLOR` is set, or when
  `--no-color` is passed.
- Rules (`─`) are 60 columns wide and use the dim colour, so they read as
  structure rather than content.

### D11 — Every surface ends with the next action

The last line of every command's output is a pointer to the next useful
command:

```
  run:  runs/2026-10-20-1432
  next: blockprobe diff runs/<a> runs/<b>
```

This keeps the tool teachable from its own output, and gives the demo a
natural way to move between beats without narration.

### D12 — Exit codes

| Code | Meaning |
|---|---|
| 0 | success — every probe was PASS, SKIP or FLAKY |
| 1 | product failure — at least one probe FAIL or ERROR |
| 2 | usage error (bad flag, bad profile, unknown command) |
| 3 | budget exhausted |
| 4 | provider or environment unavailable |

**FLAKY exits 0.** A flaky probe is a finding worth printing loudly, but it is
not a regression. PRD §16 names model nondeterminism as a high-likelihood
source of false failures; if FLAKY exited non-zero, most runs would be red and
the canary would be ignored. The gate is FAIL and ERROR.

Usage errors exit 2 so CI can distinguish "your command was wrong" from "the
product misbehaved". Exit 4 is separate from 1 because a missing credential is
an operator problem, not a product finding, and must not be reported as a bug.

Precedence when several apply: usage error (2) first, then provider or
environment unavailable (4), then budget exhausted (3), then probe failures
(1). A cancelled publish exits 2 — the operator declined, so the command was
not successfully performed.

### D13 — Machine-readable output

Every command that produces data supports `--json`, emitting the same data with
no ANSI and no human formatting, on stdout (D3).

| Command | JSON shape |
|---|---|
| `run` | the run summary — probes, statuses, latencies, pass-rates, evidence paths |
| `analyze` | the findings list — title, building block, severity, summary, evidence refs, suggested improvement |
| `diff` | the classification from D6 — regressions, fixes, unstable, added, removed, unchanged, plus pass-rate and latency deltas |
| `report` | the rendered table rows and the note body |
| `doctor` | the environment capture fields from PRD FR-01 |
| `publish` | the publish attempt record — draft, target, confirmation result, outcome |

The terminal renderings are a presentation layer over that JSON, never a
separate source of truth.

### D14 — The analyze phase is never silent

`run --analyze` and `analyze` call a real model and can take minutes. A silent
terminal for several minutes is exactly the failure this document's goals
forbid, and it is invisible in a design that only describes per-probe lines.

So the analyze phase prints its own progress:

```
  ───────────────────────────────────────────
  analyzing · analyst agent is reading 6 probe results
  · finding 1 of 2 written
  · finding 2 of 2 written
  note written: runs/2026-10-20-1432/what-we-learned.md
```

The phase is announced before it starts, each written finding is reported as it
lands, and the phase ends by naming the file it produced.

**Dependency, and the fallback if it does not hold.** Whether findings can be
reported one at a time depends on the OpenMinion SDK's streaming and
structured-output surfaces, which are not verified yet (PRD §17, open question
2). If the SDK cannot emit partial results, D14 degrades to:

```
  ───────────────────────────────────────────
  analyzing · analyst agent is reading 6 probe results
  · still analysing · 42s elapsed
  note written: runs/2026-10-20-1432/what-we-learned.md
```

The phase still announces itself, still shows elapsed time, and still names the
file it produced. A silent gap is never acceptable. Verify the capability in
Phase 0 (D18) and build whichever variant the SDK actually supports.

### D15 — `doctor` output

`doctor` is the first command a new user runs, and PRD FR-01 names exactly what
it must capture. It renders as a labelled list of `name  value` rows, with a
green or red marker per row, and a single closing verdict line:

```
  os              windows 10.0.19045
  python          3.11.9
  openminion      0.1.4  (pip)
  provider        portal/gemma-4
  budget          40 calls
  check-turn      ok

  6 checks passed · provider reachable · budget set
  next: blockprobe run --profile quick
```

Secrets never appear. `openminion doctor --check-turn --json` output is
captured and summarised, not dumped verbatim.

### D16 — `matrix` output

`matrix` runs the suite across several OpenMinion versions and then diffs the
results. It renders one line per version, then the D6 diff view for the pair
the user asks to compare:

```
  0.1.3   6 probes   4 pass · 1 flaky · 1 fail   9.8s
  0.1.4   6 probes   5 pass · 1 flaky            8.1s

  next: blockprobe diff runs/2026-10-27-0912 runs/2026-11-03-1044
```

### D17 — The demo uses one command per beat

The demo script (PRD Appendix A) has a beat for the results table and a beat
for the analyst note. `blockprobe run --profile quick --analyze` prints the
probe lines, the results table, and the note, in that order, so the demo needs
one invocation for the first three beats. `blockprobe report` re-renders a
saved run for the notes and the table without re-running the probes.

The D11 next-action chain therefore reads `run → diff → publish` for the demo
path, with `report` available as a re-render of an existing run.

### D18 — Three checks that belong in Phase 0

Each of these is cheap to check in Phase 0 and expensive to discover in
Phase 2, because each one invalidates work already done.

1. **Terminal glyphs.** `▸` `·` `─` `→` must render and align in Windows
   PowerShell, not only in Windows Terminal. If any of them misalign, fall back
   to ASCII and correct the mockups once, here, instead of in every surface
   later.
2. **Finding-level progress.** Whether the SDK can report findings as they are
   produced (D14).
3. **TTY detection.** That stdout is correctly detected as a TTY on both
   platforms, so colour suppression and the stderr/stdout split (D3) behave.

### D19 — `blockprobe report --md` prints the raw deliverable

The Building Blocks Tested table has six columns in the `.md` (PRD §12) and
five in the terminal rendering. In the demo beat for that table, the reviewer
should see the actual graded deliverable, not a narrower rendering of it.

`blockprobe report --md` prints the raw markdown of the generated files to
stdout — no colour, no table layout, no wrapping. It lets the demo show the
real submitted artifact without leaving the terminal and without opening an
editor.

The terminal rendering (five columns) remains the tool's working view for
day-to-day use.

---

## Delivery order

This document describes 19 decisions. The schedule has two months at 10–15 hours
a week, so each decision is assigned to the phase that needs it. Nothing in a
later phase blocks a phase that needs to ship.

| Phase | Decisions to implement | Deliberately not yet |
|---|---|---|
| 0 · Kickoff and setup | D15 (`doctor`), D18 (the three checks) | everything else |
| 1 · MVP harness | D1, D2, D3, D10, D11, D12, D13 | D4, D5, D6, D7, D8, D9, D14, D16, D17, D19 |
| 2 · Analyst and full probes | D4, D5, D9, D14, D17 | D6, D7, D8, D16, D19 |
| 3 · Issues, gate, providers | D6, D7, D8, D16 | — |
| 4 · Polish and demo | D19 | — |

The MVP in Phase 1 needs only: probes running live (D1), the results table
(D2), correct stream separation (D3), the colour and symbol vocabulary (D10),
the next-action line (D11), exit codes (D12), and `--json` (D13). The diff,
the publish gate, and the analyst note come later, and the demo cannot be
assembled until Phase 4 anyway.

D18 sits in Phase 0 on purpose: each of its three checks can invalidate work
that would otherwise be built in Phase 1 and 2.

---

## Surfaces covered

| Surface | Decision | Rendered to |
|---|---|---|
| `blockprobe run` progress | D1, D3 | stderr |
| `blockprobe run` results table | D1, D2 | stdout |
| `building-blocks-tested.md` | D1 table shape, PRD §12 columns | file + stdout |
| `what-we-learned.md` | D4, D5 | file + stdout |
| `blockprobe analyze` progress | D14 | stderr |
| `blockprobe diff` | D6 | stdout |
| Issue draft and publish gate | D7, D8 | stderr (prompt) |
| `blockprobe --help` | D9 | stdout |
| Error messages | D9, D12 | stderr |
| `blockprobe doctor` | D15 | stdout |
| `blockprobe matrix` | D16 | stdout |
| `blockprobe report` | D4 | stdout |

### The results table columns

PRD §12 defines six columns for the Building Blocks Tested table: Building
block, Probe, Result, Pass rate, p50 latency, Evidence/note. The `.md` file
carries all six, because it is a graded deliverable.

At 80 columns the terminal rendering cannot fit all six, so it drops the
Evidence/note column (the evidence reference is still reachable from the
finding text in the analyst note) and keeps the other five. This is the one
place where the terminal view and the file differ in shape, and the file is
the fuller one.

---

## Left to the builder

These are implementation choices, not product decisions. The builder picks:

- The library used for ANSI colour and terminal width detection (must work on
  Windows PowerShell and Linux, and must support colour suppression).
- The exact character used for the `▸` probe marker after Windows verification.
- Table column widths and the padding rules that produce them.
- Whether the terminal renderers share code with the `.md` renderer or are
  separate.
- The module and function names for the render layer.
- Where the render layer sits in the `src/blockprobe/` tree, consistent with
  PRD §11's existing `report/` directory.
- The front-matter dialect used for the security flag in issue drafts.

---

## Verification

The design is done when:

- `blockprobe run --profile quick` produces output matching D1 in shape: one
  line per probe, live, with status, latency and pass-rate.
- `blockprobe run --analyze --json > out.json` produces a parseable JSON file
  containing no progress lines (D3).
- `blockprobe report` does not overwrite an existing, hand-edited
  `what-we-learned.md`, and does with `--force` (D4).
- `blockprobe --help` lists every PRD §11 command in the D9 grouping.
- A typo in a profile name produces the D9 three-part error and exit code 2.
- A run whose probes are all PASS, SKIP or FLAKY exits 0; a run with one FAIL
  exits 1; a run with one ERROR exits 1 (D12).
- `blockprobe diff` on two runs with a status change shows the change under
  `regressions` or `fixes`, shows a probe present in only one run under
  `added` or `removed`, and lists unchanged probes only as names.
- `blockprobe publish` on a draft, with anything other than `PUBLISH` typed,
  creates nothing, prints `Cancelled. Nothing was published.`, and exits 2.
  Typing `publish` in lower case also cancels (D7).
- A draft with no front matter, or with front matter that fails to parse, is
  refused for public publishing (D8).
- A security-flagged draft is routed to a private note and is not offered for
  public publish.
- `blockprobe analyze` prints a phase line before the model call and a line per
  finding written, with no silent gap (D14).
- `blockprobe doctor` shows every PRD FR-01 field and no secret.
- `blockprobe report --md` prints the raw markdown of the generated files, with
  no colour and no table layout (D19).
- The three Phase 0 checks in D18 have been run and their results recorded in
  `FINDINGS.md`.
- All of the above render correctly at 80 columns, with and without colour, on
  Windows PowerShell and on Linux.
