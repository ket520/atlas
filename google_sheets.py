from pathlib import Path
from datetime import datetime, timezone
import base64
import hashlib
import json
import time
import threading
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None


ROOT = Path(__file__).resolve().parent

CREDENTIALS_FILE = ROOT / "credentials" / "google_service_account.json"

SHEET_ID = "1F2DnKdPEm-LdxM1Ag6hTcvP7a8glhnESl9m7-UlvNcs"
COURIER_ISSUES_SHEET_ID = "1jJZhSATvxE8P1p75mSVIH0ooTVASapc2qmO6IKTVQZE"
COURIER_ISSUE_TABS = ("Van", "Palletways", "XDP", "Cancelled Orders", "COMPLETED VAN DELIVERIES")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_sheets_local = threading.local()


def get_spreadsheet(spreadsheet_id=SHEET_ID):
    if gspread is None:
        return _DirectSpreadsheet(spreadsheet_id)
    # Reuse authentication and workbook metadata across a sync's source reads.
    # Keep each requests session on its own worker thread.
    now = time.monotonic()
    stamp = CREDENTIALS_FILE.stat().st_mtime_ns
    books = getattr(_sheets_local, 'books', {})
    saved = books.get(spreadsheet_id)
    if saved and saved[0] == stamp and now - saved[1] < 300:
        return saved[2]
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)

    client = gspread.authorize(credentials)

    book = client.open_by_key(spreadsheet_id)
    books[spreadsheet_id] = (stamp, now, book)
    _sheets_local.books = books
    return book


_TOKEN = {"value": "", "expires": 0}


def _der_item(data, offset=0):
    tag = data[offset]
    length = data[offset + 1]
    index = offset + 2
    if length & 0x80:
        size = length & 0x7F
        length = int.from_bytes(data[index : index + size], "big")
        index += size
    return tag, data[index : index + length], index + length


def _rsa_sign(message, pem):
    """Sign a Google service-account JWT using PKCS#1 v1.5 and SHA-256."""
    lines = [line for line in pem.splitlines() if not line.startswith("-----")]
    encoded = base64.b64decode("".join(lines))
    tag, outer, _ = _der_item(encoded)
    if tag != 0x30:
        raise ValueError("Invalid service-account private key.")
    _, _, offset = _der_item(outer)  # PKCS#8 version
    _, _, offset = _der_item(outer, offset)  # Algorithm identifier
    tag, rsa_bytes, _ = _der_item(outer, offset)
    if tag != 0x04:
        raise ValueError("Unsupported service-account private key.")
    tag, rsa, _ = _der_item(rsa_bytes)
    if tag != 0x30:
        raise ValueError("Invalid RSA private key.")
    integers = []
    offset = 0
    for _ in range(4):
        tag, value, offset = _der_item(rsa, offset)
        if tag != 0x02:
            raise ValueError("Invalid RSA private key.")
        integers.append(int.from_bytes(value, "big"))
    _, modulus, _, private_exponent = integers
    digest_info = (
        bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(message).digest()
    )
    width = (modulus.bit_length() + 7) // 8
    padding_length = width - len(digest_info) - 3
    if padding_length < 8:
        raise ValueError("Service-account key is too short.")
    encoded_message = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded_message, "big"), private_exponent, modulus)
    return signature.to_bytes(width, "big")


def _token():
    if _TOKEN["value"] and _TOKEN["expires"] > time.time() + 60:
        return _TOKEN["value"]
    credentials = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    now = int(time.time())
    encode = (
        lambda value: base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    message = ".".join(
        (
            encode({"alg": "RS256", "typ": "JWT"}),
            encode(
                {
                    "iss": credentials["client_email"],
                    "scope": SCOPES[0],
                    "aud": credentials["token_uri"],
                    "iat": now,
                    "exp": now + 3600,
                }
            ),
        )
    )
    signature = _rsa_sign(message.encode(), credentials["private_key"])
    assertion = message + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    body = urlencode(
        {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    ).encode()
    request = Request(
        credentials["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    _TOKEN.update(value=payload["access_token"], expires=now + int(payload.get("expires_in", 3600)))
    return _TOKEN["value"]


class _DirectWorksheet:
    def __init__(self, title, spreadsheet_id=SHEET_ID):
        self.title = title
        self.spreadsheet_id = spreadsheet_id

    def get_all_values(self):
        cell_range = quote("'" + self.title.replace("'", "''") + "'", safe="")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}/values/{cell_range}"
        request = Request(url, headers={"Authorization": "Bearer " + _token()})
        with urlopen(request, timeout=60) as response:
            return json.load(response).get("values", [])


class _DirectSpreadsheet:
    def __init__(self, spreadsheet_id=SHEET_ID):
        self.spreadsheet_id = spreadsheet_id

    def worksheet(self, title):
        return _DirectWorksheet(title, self.spreadsheet_id)

    def fetch_sheet_metadata(self, params=None):
        query = urlencode(params or {}, doseq=True)
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}?{query}'
        request = Request(url, headers={'Authorization': 'Bearer ' + _token()})
        with urlopen(request, timeout=60) as response:
            return json.load(response)


def worksheet_to_records(worksheet):
    values = worksheet.get_all_values()

    if not values:
        return []

    raw_headers = values[0] + [""] * (max(map(len, values)) - len(values[0]))

    headers = []
    used = set()

    for index, header in enumerate(raw_headers, start=1):
        header = header.strip()

        if not header:
            header = f"Column_{index}"

        original = header
        suffix = 2
        while header in used:
            header = f"{original}_{suffix}"
            suffix += 1
        used.add(header)

        headers.append(header)

    rows = []

    for row in values[1:]:
        row = row + [""] * (len(headers) - len(row))

        rows.append(dict(zip(headers, row)))

    return rows


def read_sales_activity():
    spreadsheet = get_spreadsheet()

    worksheet = spreadsheet.worksheet("Sales Activity")

    return worksheet_to_records(worksheet)


def read_stopstart():
    """Read order A, activity J (legacy H), status I, fetch result N and trackability O."""
    values = get_spreadsheet().worksheet("STOPSTART").get_all_values()
    if not values:
        return []
    modern = len(values[0]) > 9 and values[0][9].strip().casefold() == 'delivery activity'
    return [{"order": row[0].strip(), "details": row[7].strip() if len(row) > 7 else "",
             **({'details': row[9].strip() if len(row) > 9 else ''} if modern else {}),
             "status": row[8] if len(row) > 8 else "",
             "fetchResult": row[13].strip() if len(row) > 13 else '',
             "trackability": row[14].strip() if len(row) > 14 else ''}
            for row in values[1:] if row and row[0].strip()]


def read_xdp_statuses():
    """Read XDP status I, latest detail J, document links T and parcel barcode U."""
    values = get_spreadsheet().worksheet("XDP").get_all_values()
    if not values:
        return []
    headers = ["".join(char for char in name.casefold() if char.isalnum()) for name in values[0]]
    order_names = {"orderno", "ordernumber", "orderid", "oworderno", "owordernumber", "customerref", "customerreference"}
    tracking_names = {"trackingid", "trackingno", "trackingnumber", "consignmentno", "consignmentnumber"}
    order_columns = [index for index, name in enumerate(headers) if name in order_names]
    tracking_columns = [index for index, name in enumerate(headers) if name in tracking_names]
    consignment_columns = ([index for index, name in enumerate(headers) if name == 'xdpconsignments']
                           or [index for index, name in enumerate(headers)
                               if name in {'consignment', 'consignmentno', 'consignmentnumber'}]
                           or tracking_columns)
    if len(order_columns) != 1 and len(tracking_columns) != 1:
        raise ValueError("XDP tab needs a unique order number or tracking number column.")
    def cell(row, columns):
        return row[columns[0]].strip() if len(columns) == 1 and len(row) > columns[0] else ""
    return [{"order": cell(row, order_columns), "trackingId": cell(row, tracking_columns),
             "consignmentOrder": row[0].strip() if row else "",
             "consignmentNo": cell(row, consignment_columns),
             "status": row[8].strip() if len(row) > 8 else "",
             "latestDetail": row[9].strip() if len(row) > 9 else "",
             "documents": row[19].strip() if len(row) > 19 else "",
             "parcelBarcode": row[20].strip() if len(row) > 20 else ""} for row in values[1:]]


def read_xdp_activity():
    """XDP Activity has fixed columns: order B, status type I and XML history M."""
    values = get_spreadsheet().worksheet('XDP Activity').get_all_values()
    return [{'order': row[1].strip(),
             'statusType': row[8].strip() if len(row) > 8 else '',
             'activityXml': row[12].strip() if len(row) > 12 else ''}
            for row in values[1:] if len(row) > 1 and row[1].strip()]


def read_palletways_tracking():
    """Read order A, tracking B, consignment C, status F, booking Z/AA and BT/BU."""
    values = get_spreadsheet().worksheet("Palletways").get_all_values()
    return [{"order": row[0].strip(), "trackingId": row[1].strip() if len(row) > 1 else "",
             "consignmentNumber": row[2].strip() if len(row) > 2 else "",
             "status": row[5] if len(row) > 5 else "",
             "bookedIn": row[25] if len(row) > 25 else "",
             "bookInRequest": row[26] if len(row) > 26 else "",
             "bookInDate": row[71].strip() if len(row) > 71 else "",
             "bookInTime": row[72].strip() if len(row) > 72 else ""}
            for row in values[1:] if row and row[0].strip()]


def read_palletways():
    spreadsheet = get_spreadsheet()

    worksheet = spreadsheet.worksheet("Palletways")

    return worksheet_to_records(worksheet)


def read_amazon_shipping():
    """Read tracking ID, status and scheduled UTC time from columns B, G and M."""
    spreadsheet = get_spreadsheet()
    try:
        worksheet = spreadsheet.worksheet("Amazon Shipping")
    except Exception as error:
        if gspread is None or not isinstance(error, gspread.WorksheetNotFound):
            raise
        matches = [sheet for sheet in spreadsheet.worksheets()
                   if " ".join(sheet.title.split()).casefold() == "amazon shipping"]
        if len(matches) != 1:
            raise RuntimeError("Amazon Shipping tab was not found in the Sales Activity workbook.") from None
        worksheet = matches[0]
    values = worksheet.get_all_values()
    return [
        {"trackingId": row[1].strip(), "status": row[6].strip() if len(row) > 6 else "",
         "scheduledAt": row[12].strip() if len(row) > 12 else ""}
        for row in values[1:] if len(row) > 1 and row[1].strip()
    ]


def read_courier_issues():
    """Read only the five operational tabs used by Delivery Desk."""
    spreadsheet = get_spreadsheet(COURIER_ISSUES_SHEET_ID)
    return {
        title: worksheet_to_records(spreadsheet.worksheet(title)) for title in COURIER_ISSUE_TABS
    }


def read_google_sheet():
    spreadsheet = get_spreadsheet()

    sales_activity = worksheet_to_records(spreadsheet.worksheet("Sales Activity"))

    palletways = worksheet_to_records(spreadsheet.worksheet("Palletways"))

    return {"sales_activity": sales_activity, "palletways": palletways}


def read_sheet_data(tab=None):
    """Return complete formatted cell values without collapsing duplicate headers."""
    names = {"sales_activity": "Sales Activity", "palletways": "Palletways"}
    if tab is None:
        return read_google_sheet()
    if tab not in names:
        raise ValueError("Unknown spreadsheet tab.")
    worksheet = get_spreadsheet().worksheet(names[tab])
    values = worksheet.get_all_values()
    width = max(map(len, values), default=0)
    return {
        "tab": worksheet.title,
        "values": [row + [""] * (width - len(row)) for row in values],
        "syncedAt": datetime.now(timezone.utc).isoformat(),
    }
