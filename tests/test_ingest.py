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
