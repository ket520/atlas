"""Read the local Routine Dashboard workbook without modifying it."""

import os
from pathlib import Path

from openpyxl import load_workbook


def workbook_path():
    return Path(
        os.environ.get("ROUTINE_DASHBOARD_XLSX")
        or Path.home() / "Downloads" / "ROUTINE DASHBOARD V2.xlsx"
    )


def read_booking_rows():
    workbook = load_workbook(workbook_path(), read_only=True, data_only=True)
    try:
        sheet = workbook["DASHBOARD"]
        headers = next(sheet.iter_rows(min_row=2, max_row=2, max_col=8, values_only=True))
        if headers[0] != "Order ID" or headers[4] != "Status":
            raise ValueError("Routine DASHBOARD Order ID / Status headers were not found")
        return [
            {"Order ID": row[0], "Status": row[4]}
            for row in sheet.iter_rows(min_row=3, max_col=8, values_only=True)
        ]
    finally:
        workbook.close()
