from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass(frozen=True)
class SourcePdf:
    path: Path
    file_number: str
    assignment: str
    page_count: int


@dataclass
class IngestResult:
    lease_number: str
    sources: list[SourcePdf]
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _numeric_key(name: str):
    """Sort numerically when possible, else case-insensitive alphabetical.

    Returns (is_non_numeric, numeric_value, lowercased_name) so all-numeric
    names sort ahead of and independently from non-numeric ones.
    """
    try:
        return (0, int(name), "")
    except ValueError:
        return (1, 0, name.lower())


def scan_lease_folder(folder: Path) -> IngestResult:
    folder = Path(folder)
    sources: list[SourcePdf] = []
    skipped: list[tuple[Path, str]] = []

    subfolders = sorted(
        (p for p in folder.iterdir() if p.is_dir()),
        key=lambda p: _numeric_key(p.name),
    )
    for sub in subfolders:
        files = sorted(
            (p for p in sub.iterdir() if p.is_file()),
            key=lambda p: _numeric_key(p.stem),
        )
        for f in files:
            if f.suffix.lower() != ".pdf":
                skipped.append((f, "not a PDF"))
                continue
            try:
                with fitz.open(f) as doc:
                    page_count = doc.page_count
            except Exception as exc:  # noqa: BLE001 - report any unreadable file
                skipped.append((f, f"unreadable: {exc}"))
                continue
            sources.append(
                SourcePdf(
                    path=f,
                    file_number=f.stem,
                    assignment=sub.name,
                    page_count=page_count,
                )
            )

    return IngestResult(lease_number=folder.name, sources=sources, skipped=skipped)
