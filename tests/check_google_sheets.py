"""Manual live-sheet check: python tests/check_google_sheets.py."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_sheets import read_google_sheet

data = read_google_sheet()

sales_activity = data["sales_activity"]

palletways = data["palletways"]


print("Sales Activity rows:", len(sales_activity))

print("Palletways rows:", len(palletways))


print("\nFirst Sales Activity row:")

if sales_activity:
    print(sales_activity[0])


print("\nFirst Palletways row:")

if palletways:
    print(palletways[0])
