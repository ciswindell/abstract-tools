from aa_tool.tools import Tool, tools_by_category


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
