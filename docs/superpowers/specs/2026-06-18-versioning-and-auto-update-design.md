# Design: Versioning, GitHub Builds & In-App Update Nudge

**Date:** 2026-06-18
**Status:** Approved (design phase)
**Author:** Chris (with Claude)

## Problem

Abstract Tools ships to Windows staff as a single double-clickable `Abstract Tools.exe`,
built in GitHub Actions (the developer is on Linux and cannot compile Windows binaries
locally). Three gaps exist today:

1. **Distribution is awkward.** The build workflow uploads the `.exe` as a GitHub
   *artifact*, which is buried in the Actions UI and requires a login and several clicks
   to retrieve — unworkable for non-technical staff.
2. **No visible version.** The version (`0.1.0`) lives only in `pyproject.toml` and is
   shown nowhere in the GUI. When a teammate reports a problem, neither they nor Chris
   can tell which version they are running.
3. **No update mechanism.** Every release requires Chris to manually email the team. There
   is no way for the app to tell a user a newer version exists.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Repository visibility | **Public, single repo.** Code has no secrets; real lease data in `example/` is already git-ignored and was never committed. |
| Where the `.exe` is hosted | **GitHub Releases** on the public repo (permanent public download links; latest-release queryable via the public API — no tokens). |
| Update delivery | **Download-for-them:** the app downloads the new `.exe` to the user's Downloads folder; the user does the final swap. No self-replace, no browser steps. |
| Update nudge style | **Dismissible banner.** User can close it and keep working on the current version. |
| Version source of truth | **The git tag** (`vX.Y.Z`). No version typed in two places. |

## Goals

- Pushing a `vX.Y.Z` tag produces a public GitHub Release with `Abstract Tools.exe` attached.
- The app displays its own version in the GUI.
- On launch, the app checks (in the background, non-blocking) whether a newer release exists
  and, if so, shows a dismissible banner with a one-click download.
- Everything degrades gracefully offline and when run from source.

## Non-goals (YAGNI)

- Self-replacing/auto-restarting updater (explicitly rejected as fragile on Windows).
- Forced/blocking updates.
- A second repo, embedded tokens, or any authenticated GitHub access.
- Delta updates, update channels (beta/stable), or rollback.
- Code signing / SmartScreen handling (can be revisited later; out of scope here).

## Architecture

Four small, independently understandable units.

### Unit A — Version source of truth (`abstract_tools/version.py`)

- Exposes `__version__: str` and a helper `current_version() -> Version`.
- Default value in source is a dev sentinel, e.g. `"0.0.0+dev"`.
- At CI build time, the workflow overwrites a generated value (see Unit D) so the bundled
  `.exe` carries the real tag version. When the sentinel is present, the app treats itself
  as a "dev build".
- Depends on: nothing. Pure data + a tiny semver parse/compare (reuse `packaging.version`
  if already available transitively, otherwise a minimal local comparator — chosen during
  planning to avoid adding a dependency just for this).

### Unit B — Update checker (`abstract_tools/update_check.py`)

- One function: `check_for_update(current: Version, *, repo: str, http_get=...) -> UpdateInfo | None`.
- Calls the public endpoint `https://api.github.com/repos/{repo}/releases/latest`,
  reads `tag_name` (→ latest version) and the `.exe` asset's `browser_download_url`.
- Returns an `UpdateInfo(latest_version, download_url, release_notes)` when
  `latest > current`, else `None`. Returns `None` (never raises) on any network/parse error.
- The HTTP call is injected (`http_get`) so tests stub it — **no real network in tests**.
- `repo` is a single module-level constant (e.g. `"landmaninnovations/abstract-tools"`),
  set once. (Exact owner/name to confirm before first release.)
- Depends on: Unit A (for comparison), Python stdlib `urllib` (no new dependency).

### Unit C — GUI surface

1. **Version label.** A small, grey `vX.Y.Z` (or `dev`) shown on the `HomeBoard` corner and
   appended to the window title (`Abstract Tools vX.Y.Z`). Styled via existing `objectName`
   theme hooks. Dev builds show `dev`.
2. **Update banner.** A dismissible bar at the top of the main window:
   *"Version X.Y.Z is available — Download update"* with a close (×) button.
   - Shown only when Unit B returns an `UpdateInfo`.
   - Closing it hides it for the session (dismissible; reappears next launch if still behind).
   - The check runs on a background `QThread`/worker (mirrors the existing
     `ConversionWorker` pattern) so the UI never blocks; the banner is added on the main
     thread when a result arrives.
3. **Download action.** Clicking "Download update":
   - Downloads the release `.exe` to the user's Downloads folder as
     `Abstract Tools {version}.exe`, showing simple progress.
   - On success: *"Done — saved to your Downloads. Close this app and open the new file."*
     (optionally reveal the file in Explorer).
   - On failure: a quiet inline message; never crashes the app.
- Depends on: Units A & B.

### Unit D — Build & release workflow (`.github/workflows/build-windows.yml`)

Changes to the existing workflow (keep tests-before-build):

1. **Stamp the version.** Before PyInstaller runs, write the tag (stripped of the leading
   `v`) into the generated version value Unit A reads. Source: `github.ref_name` for tag
   pushes. For manual `workflow_dispatch` runs without a tag, fall back to the dev sentinel
   (no Release is published in that case).
2. **Publish a Release** instead of (or in addition to) the artifact upload: create a
   GitHub Release for the tag and attach `dist/Abstract Tools.exe`
   (e.g. `softprops/action-gh-release` or `gh release create`). The release page is public,
   giving a permanent download URL and the API entry Unit B reads. Needs
   `permissions: contents: write` on the job.

## Data flow

```
You: git tag v1.3.0 && git push --tags
        │
        ▼
GitHub Actions ── run tests ── stamp version 1.3.0 ── pyinstaller ── create public Release (exe attached)
        │
        ▼  (public api.github.com/.../releases/latest now reports 1.3.0)
Teammate opens app (running 1.2.0)
        │  background check
        ▼
update_check sees 1.3.0 > 1.2.0  ──►  dismissible banner: "1.3.0 available — Download"
        │ click
        ▼
downloads "Abstract Tools 1.3.0.exe" to Downloads ──► "Close this & open the new file"
```

## Error handling

- **Offline / GitHub unreachable / rate-limited (60/hr per IP, unauthenticated):** check
  returns `None`; no banner, no error dialog; app fully usable.
- **Malformed API response / no `.exe` asset:** treated as "no update"; logged quietly.
- **Download fails midway:** inline failure message; partial file is cleaned up; app continues.
- **Dev/source build (sentinel version):** version label shows `dev`; update check is skipped
  (a dev version never compares as "behind" a release in a confusing way).

## Testing strategy

Headless-friendly (`QT_QPA_PLATFORM=offscreen`), no network.

- **Version comparison:** `1.10.0 > 1.9.0`, `2.0.0 > 1.9.9`, equal versions, dev sentinel
  behaviour. Guards the classic string-vs-numeric ordering trap.
- **Update checker:** with a stubbed `http_get` returning canned GitHub JSON — newer,
  same, older, missing-asset, malformed, and network-error cases all produce the right
  `UpdateInfo | None` and never raise.
- **GUI (light):** banner appears only when an `UpdateInfo` is present; dismiss hides it;
  label renders the version / `dev`. Heavy download is exercised via the injected layer,
  not a real file fetch.

## One-time / rollout tasks

1. Create the public GitHub repo; push code. Confirm `.gitignore` keeps `example/` out
   (already verified) and `.exe`/build output stays ignored.
2. Set the `repo` constant in Unit B to the final `owner/name`.
3. Land Units A–D.
4. Cut the first real tag (e.g. `v1.0.0`) and confirm: Release appears with the `.exe`,
   the app shows `v1.0.0`, and a deliberately-older local build sees the update banner.
5. Update `pyproject.toml` version handling so it does not contradict the tag-driven version
   (single source of truth).

## Packaging note

`abstract_tools.spec` must include any new bundled/generated files (e.g. the stamped
version file) per constitution principle IV (Verify the Real Artifact). If `urllib`-based
networking pulls in nothing new, no `hiddenimports` change is needed — confirm during
planning.

## Open items to confirm during planning

- Final repo `owner/name`.
- Whether `packaging` is already importable in the bundle, or a tiny local semver comparator
  is preferable (avoid adding a dependency solely for comparison).
