# src/abstract_tools/srp/config.py
"""Static layout/formatting config for the SRP Case Actions sheet.

Shared by the transform step (column order, date columns) and the Excel
build step (widths, date number-format, sheet name).
"""

# Source SRP column name -> exported column name.
COLUMN_RENAMES: dict[str, str] = {
    "Action Date": "Action Date",
    "Date Filed": "Received Date",
    "Action Name": "Document Type",
    "Action Status": "Action Status",
    "Action Information": "Runsheet Remarks",
}

# Final column order of the exported "SRP Case Actions" sheet.
COLUMN_ORDER: list[str] = [
    "Document Type",
    "Received Date",
    "Document Date",
    "Effective Date",
    "Action Date",
    "Grantor",
    "Grantee",
    "Legal Description",
    "Runsheet Remarks",
    "Abstract Remarks",
    "Internal Remarks",
    "Action Status",
]

COLUMN_WIDTHS: dict[str, int] = {
    "Document Type": 35,
    "Received Date": 12,
    "Document Date": 12,
    "Effective Date": 12,
    "Action Date": 12,
    "Grantor": 10,
    "Grantee": 10,
    "Legal Description": 10,
    "Runsheet Remarks": 45,
    "Abstract Remarks": 10,
    "Internal Remarks": 10,
    "Action Status": 20,
}

DATE_COLUMNS: list[str] = [
    "Received Date",
    "Document Date",
    "Effective Date",
    "Action Date",
]

DATE_FORMAT: str = "m/d/yyyy"
SHEET_NAME: str = "SRP Case Actions"

# Section markers found in a raw SRP sheet, used as table boundaries.
TABLE_HEADERS: list[str] = [
    "Serial Register Page",
    "CASE CUSTOMERS",
    "RECORD TITLE ",
    "OPERATING RIGHTS ",
    "LAND RECORDS",
    "CASE ACTIONS",
    "CASE TRANSACTIONS",
    "ASSOCIATED AGREEMENT OR LEASE (RECAPITULATION TABLE) INFO",
    "ASSOCIATED BONDS",
    "LEGACY CASE REMARKS",
]
