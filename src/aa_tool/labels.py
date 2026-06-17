from datetime import date


def build_bookmark_label(
    index: int, doc_type: str = "Unknown", received_date: date | None = None
) -> str:
    if received_date is None:
        received = "NA"
    else:
        received = f"{received_date.month}/{received_date.day}/{received_date.year}"
    return f"{index}-{doc_type}-{received}"
