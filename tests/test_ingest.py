from pathlib import Path

from aa_tool.ingest import scan_lease_folder


def test_scan_orders_by_assignment_then_file_number(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368495.pdf", 6, parent=lease / "0")
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368521.pdf", 1, parent=lease / "1")

    result = scan_lease_folder(lease)

    assert result.lease_number == "B11294"
    ordered = [(s.assignment, s.file_number, s.page_count) for s in result.sources]
    assert ordered == [
        ("0", "368481", 1),
        ("0", "368495", 6),
        ("1", "368521", 1),
    ]


def test_scan_skips_non_pdf_and_unreadable(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    (lease / "0" / "notes.txt").write_text("hello")
    (lease / "0" / "broken.pdf").write_bytes(b"not really a pdf")

    result = scan_lease_folder(lease)

    assert [s.file_number for s in result.sources] == ["368481"]
    skipped_names = sorted(p.name for p, _ in result.skipped)
    assert skipped_names == ["broken.pdf", "notes.txt"]


def test_scan_orders_numeric_before_nonnumeric_alphabetical(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    # Numeric subfolders out of natural order, plus non-numeric names with
    # mixed case to exercise the case-insensitive alphabetical fallback.
    make_pdf("100.pdf", 1, parent=lease / "10")
    make_pdf("200.pdf", 1, parent=lease / "0")
    make_pdf("alpha.pdf", 1, parent=lease / "alpha")
    make_pdf("beta.pdf", 1, parent=lease / "Beta")

    result = scan_lease_folder(lease)

    # All-numeric subfolders first in numeric order (0 before 10, not string
    # order), then non-numeric in case-insensitive alphabetical order
    # (alpha before Beta).
    assert [s.assignment for s in result.sources] == ["0", "10", "alpha", "Beta"]


def test_scan_orders_file_stems_numeric_before_nonnumeric(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    sub = lease / "0"
    make_pdf("100.pdf", 1, parent=sub)
    make_pdf("9.pdf", 1, parent=sub)
    make_pdf("apple.pdf", 1, parent=sub)
    make_pdf("Banana.pdf", 1, parent=sub)

    result = scan_lease_folder(lease)

    # Numeric stems first in numeric order (9 before 100), then non-numeric
    # in case-insensitive alphabetical order (apple before Banana).
    assert [s.file_number for s in result.sources] == ["9", "100", "apple", "Banana"]
