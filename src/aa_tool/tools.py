from collections.abc import Callable
from dataclasses import dataclass

from PySide6 import QtWidgets


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    description: str
    category: str  # source agency, e.g. "NM State Land Office"
    icon: str      # bundled resource name, e.g. "icons/segmentor.svg"
    # build(on_back_to_tools) -> the tool's root widget
    build: Callable[[Callable[[], None]], QtWidgets.QWidget]


def tools_by_category(tools: list[Tool]) -> dict[str, list[Tool]]:
    grouped: dict[str, list[Tool]] = {}
    for tool in tools:
        grouped.setdefault(tool.category, []).append(tool)
    return grouped
