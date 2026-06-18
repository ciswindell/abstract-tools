from abstract_tools.tools import Tool, tools_by_category


def _tool(id, category):
    return Tool(id=id, name=id, description="", category=category, icon="", build=lambda cb: None)


def test_groups_by_category_preserving_order():
    tools = [
        _tool("a", "NM State Land Office"),
        _tool("b", "BLM"),
        _tool("c", "NM State Land Office"),
    ]
    grouped = tools_by_category(tools)
    assert list(grouped.keys()) == ["NM State Land Office", "BLM"]
    assert [t.id for t in grouped["NM State Land Office"]] == ["a", "c"]
    assert [t.id for t in grouped["BLM"]] == ["b"]


def test_tiff_converter_registered_under_nmslo():
    from abstract_tools.tools import TOOLS

    by_id = {t.id: t for t in TOOLS}
    tool = by_id["tiff_converter"]
    assert tool.name == "Batch TIFF to PDF Converter"
    assert tool.category == "NM State Land Office"
    assert tool.icon == "icons/tiff_converter.svg"


def test_srp_parser_registered_under_blm():
    from abstract_tools.tools import TOOLS

    by_id = {t.id: t for t in TOOLS}
    tool = by_id["srp_parser"]
    assert tool.name == "SRP Parser"
    assert tool.category == "Bureau of Land Management"
    assert tool.icon == "icons/srp_parser.svg"
