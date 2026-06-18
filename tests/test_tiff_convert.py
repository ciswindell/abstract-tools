from pathlib import Path

from PIL import Image

from abstract_tools.tiff_convert import (
    Action,
    PlanSummary,
    RunSummary,
    count_pdf_pages,
    count_tiff_pages,
    default_output,
    plan_actions,
    run_conversion,
    should_skip,
    summarize_plan,
)


def _make_tiff(path: Path, pages: int = 1, size=(120, 160)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [Image.new("RGB", size, "white") for _ in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


def test_default_output_is_sibling_named_converted(tmp_path):
    src = tmp_path / "lease scans"
    assert default_output(src) == tmp_path / "lease scans converted"


def test_plan_actions_classifies_tree(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "sub" / "b.TIFF")
    (src / "sub").mkdir(parents=True, exist_ok=True)
    (src / "notes.txt").write_text("hi")

    out = default_output(src)
    actions = plan_actions(src, out, force=False)
    kinds = sorted(a.kind for a in actions)
    convert = [a for a in actions if a.kind == "Convert"]
    copy = [a for a in actions if a.kind == "Copy"]

    assert len(convert) == 2
    assert all(a.dst.suffix == ".pdf" for a in convert)
    assert len(copy) == 1 and copy[0].dst.name == "notes.txt"
    assert "MakeDir" in kinds


def test_summarize_plan_counts(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    (src / "notes.txt").write_text("hi")
    actions = plan_actions(src, default_output(src), force=False)

    summary = summarize_plan(actions)
    assert isinstance(summary, PlanSummary)
    assert summary.tiff_count == 1
    assert summary.copy_count == 1
    assert summary.total_bytes > 0


def test_run_conversion_round_trips_pages(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "two.tif", pages=2)
    (src / "keep.txt").write_text("hi")
    out = default_output(src)

    result = run_conversion(src, out, standardize=True)
    assert isinstance(result, RunSummary)
    assert result.converted == 1
    assert result.copied == 1
    assert not result.failures

    pdf = out / "two.pdf"
    assert pdf.exists()
    assert count_pdf_pages(pdf) == count_tiff_pages(src / "two.tif") == 2
    assert (out / "keep.txt").exists()


def test_run_conversion_no_standardize(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif", pages=1)
    out = default_output(src)
    result = run_conversion(src, out, standardize=False)
    assert result.converted == 1
    assert count_pdf_pages(out / "a.pdf") == 1


def test_should_skip_only_when_pages_match(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif", pages=2)
    out = default_output(src)
    run_conversion(src, out, standardize=True)

    assert should_skip(src / "a.tif", out / "a.pdf") is True
    assert should_skip(src / "a.tif", out / "missing.pdf") is False


def test_progress_callback_reports_total(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "b.tif")
    out = default_output(src)

    seen = []
    run_conversion(src, out, progress_cb=lambda done, total, label: seen.append((done, total)))
    assert seen, "progress_cb was never called"
    assert seen[-1] == (2, 2)


def test_run_conversion_records_failure(tmp_path):
    src = tmp_path / "src"
    bad = src / "bad.tif"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not a real tiff")
    out = default_output(src)

    result = run_conversion(src, out)
    assert result.converted == 0
    assert len(result.failures) == 1
    assert result.failures[0][0] == bad
