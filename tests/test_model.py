import pytest

from aa_tool.ingest import SourcePdf
from aa_tool.model import SegmentationModel
from pathlib import Path


def _src(num, assignment, pages):
    return SourcePdf(Path(f"{num}.pdf"), num, assignment, pages)


def test_preseeds_boundary_at_each_source_start():
    sources = [_src("368481", "0", 2), _src("368495", "0", 3)]
    model = SegmentationModel(sources)

    assert len(model.pages) == 5
    # First page of each source is a boundary; interior pages are not.
    assert [model.is_first_page(i) for i in range(5)] == [True, False, True, False, False]

    docs = model.documents()
    assert [(d.index, d.source, d.assignment, d.first_global_index) for d in docs] == [
        (1, "368481", "0", 0),
        (2, "368495", "0", 2),
    ]


def test_split_inside_source_and_merge_across_sources():
    sources = [SourcePdf(Path("368495.pdf"), "368495", "0", 4),
               SourcePdf(Path("368521.pdf"), "368521", "1", 1)]
    model = SegmentationModel(sources)

    # Split 368495 into two documents at its page index 2 (global 2).
    model.set_first_page(2)
    # Merge 368521 into the previous document (document spans two sources).
    model.set_continuation(4)

    docs = model.documents()
    assert [(d.index, d.source, d.assignment, [p.global_index for p in d.pages]) for d in docs] == [
        (1, "368495", "0", [0, 1]),
        (2, "368495", "0", [2, 3, 4]),
    ]


def test_first_page_cannot_be_continuation():
    sources = [SourcePdf(Path("368495.pdf"), "368495", "0", 2)]
    model = SegmentationModel(sources)
    with pytest.raises(ValueError):
        model.set_continuation(0)
