from dataclasses import dataclass

from aa_tool.ingest import SourcePdf


@dataclass(frozen=True)
class MergedPage:
    global_index: int
    source: SourcePdf
    source_page_index: int


@dataclass
class Document:
    index: int
    pages: list[MergedPage]

    @property
    def source(self) -> str:
        return self.pages[0].source.file_number

    @property
    def assignment(self) -> str:
        return self.pages[0].source.assignment

    @property
    def first_global_index(self) -> int:
        return self.pages[0].global_index


class SegmentationModel:
    def __init__(self, sources: list[SourcePdf]):
        self.pages: list[MergedPage] = []
        self._is_first: list[bool] = []
        gi = 0
        for source in sources:
            for spi in range(source.page_count):
                self.pages.append(MergedPage(gi, source, spi))
                self._is_first.append(spi == 0)
                gi += 1
        if self._is_first:
            self._is_first[0] = True  # first page is always a boundary

    def is_first_page(self, global_index: int) -> bool:
        return self._is_first[global_index]

    def set_first_page(self, global_index: int) -> None:
        self._is_first[global_index] = True

    def set_continuation(self, global_index: int) -> None:
        if global_index == 0:
            raise ValueError("The first page cannot be a continuation page")
        self._is_first[global_index] = False

    def documents(self) -> list[Document]:
        docs: list[Document] = []
        for page, first in zip(self.pages, self._is_first):
            if first:
                docs.append(Document(index=len(docs) + 1, pages=[page]))
            else:
                docs[-1].pages.append(page)
        return docs
