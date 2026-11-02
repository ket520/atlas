from unittest.mock import Mock
from google_sheets import worksheet_to_records


def address_row(**columns):
    """A full source row with arbitrary headers at the explicitly mapped positions."""
    headers = [f"Column {index + 1}" for index in range(33)]
    headers[0], headers[15], headers[16] = "Order no", "Address", "Delivery postcode"
    headers[29] = "Street 3"
    values = [""] * len(headers)
    values[0], values[15], values[16] = "655497", "Old, combined, address", "CW8 3LQ"
    positions = {"AB": 27, "AC": 28, "AD": 29, "AE": 30, "AF": 31, "AG": 32}
    for column, value in columns.items():
        values[positions[column]] = value
    worksheet = Mock()
    worksheet.get_all_values.return_value = [headers, values]
    return worksheet_to_records(worksheet)[0]
