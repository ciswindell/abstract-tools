<!--
SYNC IMPACT REPORT
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR — added a new core principle (VI. Versioned, CI-Published Releases)
  and a release gate under Development Workflow & Quality Gates. No principle removed or
  redefined; existing guidance materially expanded with release/versioning discipline.
Modified principles: none renamed or redefined
Added sections:
  - Core Principle VI (Versioned, CI-Published Releases)
  - Development Workflow & Quality Gates: release gate bullet (tag → CI builds, stamps,
    publishes the GitHub Release; no locally-distributed binaries)
Removed sections: none
Templates reviewed:
  - .specify/templates/plan-template.md ✅ (Constitution Check gate reads principles
    dynamically; no hardcoded principle edits required)
  - .specify/templates/spec-template.md ✅ (no constitution references)
  - .specify/templates/tasks-template.md ✅ (no constitution references)
Runtime guidance:
  - CLAUDE.md points here rather than restating rules; the versioning/release process is
    now codified by Principle VI and reflected in docs/superpowers/plans/
    2026-06-18-versioning-and-auto-update.md.
Deferred TODOs: none

---
PRIOR REPORT (1.0.0, initial ratification)
Version change: (template, unversioned) → 1.0.0
Bump rationale: Initial ratification — all placeholder tokens replaced with concrete,
  project-specific principles and governance. MAJOR baseline for a new constitution.
Added sections: Core Principles I–V; Technology & Environment Constraints; Development
  Workflow & Quality Gates; Governance.
Removed sections: none
Deferred TODOs: none
-->

# Abstract Tools Constitution

Abstract Tools is a Windows desktop suite of focused tools for land/title abstracting
work (e.g. the NMSLO Segmentor and the Batch TIFF to PDF Converter). This constitution
defines the non-negotiable rules for building and changing it. It binds every
contributor — human or AI agent.

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

Every feature and bugfix MUST be built test-first: write a failing test, run it to
confirm it fails for the right reason (RED), write the minimal code to pass (GREEN),
then commit. Tests MUST assert real, observable behavior — a test that asserts nothing,
or that passes regardless of the code under test, is a defect and MUST be rejected in
review. UI work that cannot be asserted headlessly (pixel-level appearance) is the only
exception, and MUST instead be verified per Principle IV.

Rationale: TDD is what has caught real defects in this project before merge (including a
crash that no after-the-fact glance would have found). Red-before-green is the only proof
a test can actually fail.

### II. Spec → Plan → Build

No implementation begins without (1) an approved design spec and (2) a written
implementation plan. Creative or behavior-changing work MUST start from brainstorming
into a spec under `docs/superpowers/specs/`, then a task-decomposed plan under
`docs/superpowers/plans/` (or the equivalent Spec Kit `spec.md` / `plan.md` /
`tasks.md`). Work is executed task-by-task, each task ending in an independently testable,
committed deliverable.

Rationale: "Simple" changes are where unexamined assumptions cause the most waste. A spec
and plan make scope explicit and reviewable before code exists.

### III. Multi-Tool Isolation

The app is a suite of independent tools. Each tool MUST be a self-contained package under
`src/abstract_tools/ui/<tool>/`, registered through the `Tool` dataclass in `tools.py`,
mirroring the established package template. Shared chrome — `Header`, `theme.py`,
`MainWindow`, icons, resources — MUST stay tool-agnostic and parameterized; it MUST NOT
carry any single tool's assumptions. Any tool that performs work on a background thread
MUST implement `shutdown()` (quit and wait) so it can be torn down safely; `MainWindow`
invokes `shutdown()` before disposing a tool.

Rationale: Tools must be understandable and changeable in isolation. Shared components
that hardcode one tool's flow break the next tool and invite regressions.

### IV. Verify the Real Artifact

A green test suite is necessary but NOT sufficient evidence that work is done. Before a
feature is called complete, its real-world behavior MUST be verified: run the actual app,
and for anything touching packaging, bundled resources (`sys._MEIPASS` paths), new
dependencies, or visual output, build and click through the packaged Windows `.exe`. Any
dependency that loads components dynamically (e.g. Pillow's format plugins) MUST be added
to `abstract_tools.spec` as explicit `hiddenimports`. Success MUST be reported only with
evidence; if a step was skipped or a check failed, say so plainly.

Rationale: The packaged `.exe` and all visual behavior live entirely outside pytest.
"Tests pass" has repeatedly not meant "the shipped app works."

### V. Cohesive, On-Theme UX

All tools MUST share one visual language — the paper/pine theme defined in `theme.py` and
the bundled fonts — so the suite reads as one product. Introducing a new Qt widget type
MUST include theme styling for it; an unstyled widget under the global stylesheet is a
defect. The interface MUST honor the project's UX principles: minimize eye and mouse
travel, use color to signal state, support keyboard-first operation, and avoid surprise —
show destinations and results inline rather than in modal dialogs.

Rationale: Consistency and predictability are the product's quality signal to a
non-technical user; a tool that looks or behaves like a different app erodes trust.

### VI. Versioned, CI-Published Releases

Every change that ships to staff MUST advance the version. The version is single-sourced
from a Git tag of the form `vMAJOR.MINOR.PATCH` (PATCH for fixes, MINOR for new
features/tools, MAJOR for breaking overhauls); no version is hand-edited in two places.
Distributable Windows `.exe` builds MUST be produced by the CI release workflow triggered
by pushing that tag — never built locally for distribution. Each tagged build MUST publish
a public GitHub Release with the `.exe` attached. The running app MUST display its version
in the GUI (so a user can report it) and check the public Release feed for updates,
degrading silently when offline.

Rationale: Staff run an opaque double-clickable `.exe`. Without a visible, monotonically
advancing version and a single canonical published download, support is guesswork and users
drift onto stale builds.

## Technology & Environment Constraints

- Python MUST run inside the project virtual environment (`./venv`); never install
  packages at the system level.
- The GUI stack is PySide6; long-running work MUST use threads
  (`concurrent.futures.ThreadPoolExecutor` / `QThread`), never `multiprocessing`, because
  multiprocessing is unsafe inside a packaged Windows `.exe`.
- New bundled resources go under `src/abstract_tools/resources/` and MUST be resolved
  through `resource_path()` so they work both from source and from the bundle.
- Real customer data (e.g. lease files under `example/`) MUST NOT be committed or used in
  automated tests; secrets and credentials MUST NOT enter the repository.
- Target Python is ≥ 3.12. Code MUST use modern typing (`X | None`, `list[...]`) and
  frozen dataclasses for value objects.

## Development Workflow & Quality Gates

- Feature work branches off `dev` (never `master`); commits use Conventional Commit
  prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `build:`).
- Each task is reviewed for BOTH spec compliance and code quality before it is accepted;
  Critical and Important findings MUST be fixed and re-reviewed, not deferred silently.
- A whole-branch review MUST pass before merge to `dev`.
- Shipping a release: advance the version by pushing a `vX.Y.Z` tag; CI runs the tests,
  stamps the version from the tag, and publishes the GitHub Release with the `.exe`. Do
  NOT distribute locally-built binaries.
- Destructive or hard-to-reverse actions (deletions, force operations, publishing) MUST be
  confirmed before execution unless explicitly pre-authorized.

## Governance

This constitution is the authoritative source of guidance for this repository. It
supersedes ad-hoc practice and supersedes `CLAUDE.md` and any other guidance document —
those files point here rather than restating rules, and where they conflict with this
constitution, this constitution wins. The sole exception is an explicit instruction from
the user, which overrides this constitution.

Amendments are made by updating this file and bumping the version per semantic versioning:
MAJOR for removing or redefining a principle, MINOR for adding a principle or section or
materially expanding guidance, PATCH for clarifications and wording. Every amendment
records the new version and the amendment date, and reviews any dependent Spec Kit
templates for alignment.

Compliance is verified at the plan stage (the plan template's Constitution Check gate) and
at code review. Deviations MUST be justified in writing or corrected.

**Version**: 1.1.0 | **Ratified**: 2026-06-17 | **Last Amended**: 2026-06-18
