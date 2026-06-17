import fitz


def test_make_pdf_creates_pdf_with_page_count(make_pdf):
    path = make_pdf("368481.pdf", 3)
    assert path.exists()
    with fitz.open(path) as doc:
        assert doc.page_count == 3
