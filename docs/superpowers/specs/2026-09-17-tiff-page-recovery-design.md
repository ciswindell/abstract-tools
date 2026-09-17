# Design: TIFF Damage Recovery (no silently dropped pages)

**Date:** 2026-09-17
**Status:** Built
**Author:** Chris (with Claude)

## Problem

Converting a lease delivery printed:

```
PIL/TiffImagePlugin.py:900: UserWarning: Truncated File Read
```

and then reported a clean `✓ N converted · 0 failed`. Nothing said which file it
came from, and in the packaged `.exe` — which has no console — staff would never
see it at all. Tracing it turned up two separate faults: the one that fired here,
and a worse one it could have been.

### Fault 1 — what actually fired: Pillow reads the wrong bytes after libtiff

For a compressed TIFF, Pillow hands the raw file **descriptor** to libtiff.
libtiff moves the OS file offset; Pillow's own buffered reads afterwards land
somewhere else entirely. When `TiffImageFile.load_end()` then re-reads the tag
directory for EXIF, it parses JPEG image data as if it were tags, invents a
gigantic offset, and `ImageFile._safe_read` raises
`OSError("Truncated File Read")` — which `ImageFileDirectory_v2.load` downgrades
to the warning above.

Traced on `K05001/0/686776.tiff` from the delivery: Pillow asked to read 5 GB at
offset 3.4 GB of a 1.8 MB file. Reading that same file through a file object with
no `fileno()` produces no warning and 19 EXIF tags instead of none.

**This is Pillow's bug, not damage in the scans**, and in this delivery it cost
nothing: all 190 files decode at full size, every strip's byte count lands exactly
on the end of its file, and the pixels are identical to decoding the embedded JPEG
by hand. The latent cost is EXIF: the orientation tag lives there, and
`exif_transpose` silently does nothing when the parse fails, so a page that should
be rotated would be written upright.

### Fault 2 — the one that would have been expensive: a severed page chain

A TIFF is a chain of directories (IFDs), one per page, each ending in the offset
of the next. A tag whose value exceeds 4 bytes stores an offset to its data; when
that offset points past the end of the file — a truncated scan, or a bad writer —
`ImageFileDirectory_v2.load` warns and **returns before reading the next-page
pointer** (`TiffImagePlugin.py:898-900`). The chain is severed and every page
after the damaged one becomes invisible.

Reproduced with a hand-built 3-page TIFF: `n_frames` reports 1, `convert_one`
writes a 1-page PDF and reports success. The old page-count check could not catch
it, because `count_tiff_pages` and the output both derived from the same broken
read. Where the bad tag sorts decides the blast radius: after the tags needed to
decode (XMP, EXIF — the blobs at the end of a file that a cut transfer loses
first) the page still renders and the rest vanish silently; before them
(ImageDescription) Pillow refuses the file outright.

None of the 190 files in this delivery had this damage. The guard exists so that
"all the pages made it" is something the tool verifies rather than assumes.

## Goals

1. **Never drop a page silently.** The page count is established independently of
   Pillow's tag parsing; any shortfall in the output fails the file loudly.
2. **Recover the pages, don't just report them.** A TIFF with a damaged tag
   converts completely — all pages, right order.
3. **Recover a damaged page's content** as far as the file physically allows,
   rather than failing a whole file over one bad page.
4. **No spurious warnings**, and EXIF (so orientation) read correctly.
5. **Name the files that needed repair** in the GUI, so those PDFs get checked.

## Non-goals (YAGNI)

- Rebuilding a TIFF with no readable directory at all (a transfer cut off before
  the directory was written). Nothing says where the pages are; these fail loudly
  and stay that way.
- Repairing the source TIFF on disk. Read-only; originals are never modified.
- A new dependency (`tifffile`, libtiff bindings, ImageMagick).
- Patching Pillow globally (e.g. `ImageFile.LOAD_TRUNCATED_IMAGES`, monkeypatching
  `_safe_read`) — process-wide mutation is unsafe under the thread-pool runner,
  and the reader below makes it unnecessary.

## Design

### Unit A — `_TiffReader`: the file object every TIFF is opened through

An `io.RawIOBase` wrapper over the file, with two deliberate differences from
`open(path, "rb")`:

- **No `fileno()`.** Pillow then feeds libtiff from Python-side reads and its own
  reads stay in sync — Fault 1 cannot happen. Cost measured at zero (below).
- **Reads past EOF are zero-padded** instead of returning short. Pillow's
  directory parse no longer aborts on a tag pointing past the end, so it reaches
  the next-page pointer and the chain survives — Fault 2, at the source. The
  damaged tag's value is garbage, which is the correct trade: a lost
  ImageDescription costs nothing, a lost page costs a document.

### Unit B — `scan_tiff_ifds()`: the page count, without Pillow

Walks the chain using only each directory's fixed-size structure — entry count,
`count × 12` bytes of entries (`× 20` for BigTIFF), then the next-page offset. It
never follows an out-of-line tag offset, so the failure that breaks Pillow cannot
break it. Guards against cycles (an offset already seen), absurd entry counts, and
offsets past EOF; a file with no readable directory raises `ConversionError`.

Returns a frozen `TiffScan`: `offsets` (one per page, in order) plus the damage it
saw, by 1-based page — `damaged_tag_pages` (a tag pointing past EOF),
`partial_pages` (pixel data running past EOF, from the strip/tile offsets and byte
counts), and `truncated` (the chain itself ran off the end).

### Unit C — `_restore_lost_pages()`

`TiffImageFile._seek` walks a list of directory offsets and only consults the
chain when that list is short. When the scan found more pages than Pillow did,
filling that list in is enough to reach them; Pillow still does all the decoding.
Guarded by `hasattr`, so an unexpected Pillow degrades to previous behavior rather
than crashing.

### Unit D — honest verification and reporting

- `count_tiff_pages` returns the scan's page count, so `convert_one`'s check
  compares the output against a number Pillow's tag parsing cannot influence. A
  short PDF now fails instead of being reported as converted.
- `convert_one` returns notes describing what was worked around; `RunSummary`
  gains `repaired: list[tuple[Path, str]]`, filled only for files that converted
  **completely** (anything else is still a failure).
- `PlanScreen` shows an amber line under the failures line: *"Repaired, all pages
  kept — worth checking: 686776.tiff (repaired damaged tag on page 1)"*, styled
  with the existing `warn` object name.

## Testing

Fixtures are built byte-by-byte in `tests/tiff_builders.py` — no customer scan
enters the repository (Technology Constraints) — but carry the delivery's exact
damage signature, including the old-style JPEG-in-TIFF layout (tag 513, YCbCr)
that reproduces Fault 1's warning in a 120 KB synthetic file.

RED first: every behavior below was run against the pre-change engine, which
reported `count_tiff_pages = 1` for a 3-page file, wrote a 1-page PDF and called
it a success, failed outright on the two other damaged fixtures, and emitted
`Truncated File Read` on the JPEG fixture.

- `scan_tiff_ifds` finds 3 pages where `Image.n_frames` reports 1.
- A damaged TIFF converts to a 3-page PDF, pages in the right order (checked by
  rendering each page and comparing its shade).
- A TIFF Pillow cannot open at all still converts, in full.
- A page with incomplete scan data converts and is named in the notes.
- The JPEG-in-TIFF fixture converts with **no** warning and its EXIF intact.
- A healthy TIFF reports nothing; an unreadable file still fails loudly.
- BigTIFF chains, and a chain pointing back at itself, are walked safely.
- GUI: the repaired line appears naming only the damaged file, and stays hidden
  for a healthy folder.

## Verification (Principle IV)

- Full suite: 104 passed.
- The real 190-file delivery, converted end to end: 190 converted, 0 failures,
  **no warnings emitted at all**, and every output PDF's page count checked
  against the source's directory chain — all match.
- Old engine vs new over the same 190 files: rendered output pixel-identical
  (page-by-page hashes at 36 dpi), 27.4 s vs 27.3 s — the reader costs nothing.
- The app driven to the result screen and screenshotted: the amber repaired line
  renders in-theme and names the two damaged files.
- No new dependency and no new bundled resource, so `abstract_tools.spec` needs no
  change — still to be confirmed by clicking through the packaged `.exe` before
  release.
