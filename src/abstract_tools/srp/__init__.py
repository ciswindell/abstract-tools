# src/abstract_tools/srp/__init__.py
"""SRP Parser engine: read a BLM Serial Register Page export and merge a
cleaned Case Actions sheet plus a verbatim SRP copy into an Abstract Worksheet.
"""

from abstract_tools.srp.excel_build import run_srp_merge

__all__ = ["run_srp_merge"]
