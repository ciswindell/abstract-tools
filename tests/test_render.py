from aa_tool.render import render_page_png


def test_render_returns_png_bytes(make_pdf):
    path = make_pdf("368481.pdf", 1)
    data = render_page_png(path, 0)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature
    assert len(data) > 100
