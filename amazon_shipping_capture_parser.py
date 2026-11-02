
import json
import re
from datetime import date, datetime
from pathlib import Path


# ==============================================
# CONFIGURATION
# ==============================================

BASE_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = BASE_DIR / "amazon_demo_captures"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

DAY_RE = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})$",
    re.IGNORECASE,
)

TIME_RE = re.compile(
    r"^(\d{1,2}:\d{2})(?:\s*([+-]\d{1,2}(?::?\d{2})?))?$"
)


# ==============================================
# EXTRACT SHIPMENT DETAILS
# ==============================================

def extract_field(text, label):
    pattern = (
        rf"(?im)^\s*{re.escape(label)}"
        rf"\s*(?:\n\s*)+([^\n]+)"
    )

    match = re.search(pattern, text)

    return match.group(1).strip() if match else ""


def extract_year(text):
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s*(20\d{2})\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"\b(20\d{2})-\d{2}-\d{2}\b",
        text,
    )

    if match:
        return int(match.group(1))

    return datetime.now().year


def normalize_timezone(raw):
    if not raw:
        return None

    sign = raw[0]
    numbers = raw[1:].replace(":", "")

    if len(numbers) <= 2:
        hours = int(numbers)
        minutes = 0
    else:
        hours = int(numbers[:-2])
        minutes = int(numbers[-2:])

    if hours > 23 or minutes > 59:
        return None

    return f"{sign}{hours:02d}:{minutes:02d}"


# ==============================================
# PARSE AMAZON DELIVERY HISTORY
# ==============================================

def parse_history(text):
    sections = list(
        re.finditer(
            r"(?im)^\s*Delivery history\s*$",
            text,
        )
    )

    if not sections:
        raise ValueError(
            "Delivery history was not found in the capture."
        )

    history_text = text[sections[-1].end():]

    lines = [
        line.strip()
        for line in history_text.splitlines()
        if line.strip()
    ]

    year = extract_year(text)
    current_date = None
    previous_month = None

    events = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ----------------------------------
        # DATE GROUP: Monday, Oct 12
        # ----------------------------------

        day_match = DAY_RE.fullmatch(line)

        if day_match:
            month = MONTHS[day_match.group(1).title()]
            day = int(day_match.group(2))

            # Handle year boundaries where needed.
            if (
                previous_month is not None
                and month > previous_month + 6
            ):
                year -= 1

            previous_month = month

            try:
                current_date = date(
                    year, month, day
                ).isoformat()
            except ValueError:
                current_date = None

            i += 1
            continue

        # ----------------------------------
        # EVENT TIME: 18:50 +08
        # ----------------------------------

        time_match = TIME_RE.fullmatch(line)

        if not time_match or current_date is None:
            i += 1
            continue

        clock, raw_timezone = time_match.groups()
        timezone_offset = normalize_timezone(
            raw_timezone
        )

        i += 1

        if i >= len(lines):
            break

        if (
            DAY_RE.fullmatch(lines[i])
            or TIME_RE.fullmatch(lines[i])
        ):
            continue

        # ----------------------------------
        # EVENT DESCRIPTION
        # ----------------------------------

        description = lines[i]
        i += 1

        extra_lines = []

        while i < len(lines):
            next_line = lines[i]

            if (
                DAY_RE.fullmatch(next_line)
                or TIME_RE.fullmatch(next_line)
            ):
                break

            extra_lines.append(next_line)
            i += 1

        # ----------------------------------
        # LOCATION AND DELIVERY NOTE
        # ----------------------------------

        location = ""
        note = ""

        if extra_lines:
            first = extra_lines[0]

            if re.search(
                r",\s*(UK|GB|United Kingdom)\s*$",
                first,
                re.IGNORECASE,
            ):
                location = first
                note = " ".join(extra_lines[1:])
            else:
                note = " ".join(extra_lines)

        # ----------------------------------
        # STRUCTURED TRACKING EVENT
        # ----------------------------------

        timestamp = (
            f"{current_date}T{clock}:00"
            f"{timezone_offset or ''}"
        )

        events.append({
            "date": current_date,
            "time": clock,
            "timezone_offset": timezone_offset,
            "timestamp": timestamp,
            "description": description,
            "location": location,
            "note": note,
        })

    if not events:
        raise ValueError(
            "Delivery history found, but no events parsed."
        )

    return events


# ==============================================
# DETERMINE SHIPMENT STATUS
# ==============================================

def determine_status(events):
    descriptions = [
        event["description"].lower()
        for event in events
    ]

    if any(
        "package delivered" in item
        for item in descriptions
    ):
        return "Delivered"

    if any(
        "out for delivery" in item
        for item in descriptions
    ):
        return "Out for Delivery"

    if any(
        "picked up" in item
        or "carrier facility" in item
        for item in descriptions
    ):
        return "In Transit"

    return "Label Created"


# ==============================================
# MAIN PROCESS
# ==============================================



def capture_amazon_documents(page, context, safe_id):
    """Capture Amazon's real PoD PDF and Package details Excel."""

    pdf_responses = []
    new_pages = []
    downloads = []

    def observe_response(response):
        content_type = response.headers.get(
            "content-type", ""
        ).lower()

        if (
            "application/pdf" in content_type
            or re.search(r"\.pdf(?:[?#]|$)", response.url, re.I)
        ):
            pdf_responses.append(response)

    def observe_new_page(new_page):
        new_pages.append(new_page)
        new_page.on("download", downloads.append)

    def observe_download(download):
        downloads.append(download)

    context.on("response", observe_response)
    context.on("page", observe_new_page)
    page.on("download", observe_download)

    try:
        print("\n[PoD] Opening Amazon Proof of Delivery...")

        page.get_by_text(
            "Download Proof of Delivery",
            exact=True,
        ).click(timeout=15000)

        page.wait_for_timeout(4500)

        pdf_content = None

        # Amazon may return the PDF as a browser response.
        for response in reversed(pdf_responses):
            try:
                content = response.body()

                if (
                    content.startswith(b"%PDF-")
                    and len(content) <= 25 * 1024 * 1024
                ):
                    pdf_content = content
                    break

            except Exception:
                continue

        # If Amazon opens a new PDF tab, try its URL.
        if pdf_content is None:
            for opened in reversed(new_pages):
                url = opened.url

                if not url.startswith("https://"):
                    continue

                try:
                    response = context.request.get(
                        url,
                        timeout=20000,
                        headers={"Referer": page.url},
                    )

                    content = response.body()

                    if (
                        response.ok
                        and content.startswith(b"%PDF-")
                        and len(content) <= 25 * 1024 * 1024
                    ):
                        pdf_content = content
                        break

                except Exception:
                    continue

        # Some portals trigger a browser download instead.
        if pdf_content is None:
            for download in downloads:
                if not download.suggested_filename.lower().endswith(".pdf"):
                    continue

                candidate = OUTPUT_DIR / f"{safe_id}_pod.pdf"
                download.save_as(str(candidate))

                content = candidate.read_bytes()

                if content.startswith(b"%PDF-"):
                    pdf_content = content
                    break

                candidate.unlink(missing_ok=True)

        if pdf_content:
            pdf_path = OUTPUT_DIR / f"{safe_id}_pod.pdf"
            pdf_path.write_bytes(pdf_content)

            print(f"[PoD] Saved: {pdf_path}")
        else:
            print(
                "[PoD] PDF opened, but its bytes could not "
                "be captured automatically."
            )

    except Exception as error:
        print(f"[PoD] Capture failed: {error}")

    finally:
        context.remove_listener("response", observe_response)
        context.remove_listener("page", observe_new_page)
        page.remove_listener("download", observe_download)

    # Only the Package details option is selected.
    try:
        print("\n[Excel] Opening Export to Excel...")

        page.get_by_text(
            "Export to Excel",
            exact=True,
        ).click(timeout=15000)

        print("[Excel] Selecting Package details...")

        with page.expect_download(timeout=45000) as download_info:
            page.get_by_text(
                "Package details",
                exact=True,
            ).last.click(timeout=15000)

        download = download_info.value

        extension = Path(
            download.suggested_filename
        ).suffix.lower()

        if extension not in {".xlsx", ".xls", ".csv"}:
            print(
                "[Excel] Unexpected file type: "
                + download.suggested_filename
            )
            return

        excel_path = (
            OUTPUT_DIR
            / f"{safe_id}_package_details{extension}"
        )

        download.save_as(str(excel_path))

        print(f"[Excel] Saved: {excel_path}")

    except Exception as error:
        print(f"[Excel] Capture failed: {error}")





def main():
    print()
    print("======================================")
    print(" AMAZON SHIPPING CAPTURE PARSER")
    print("======================================")
    print()

    if not CAPTURE_DIR.exists():
        print("ERROR: Capture folder not found.")
        print(CAPTURE_DIR)
        return

    capture_files = sorted(
        CAPTURE_DIR.glob("*_shipment_page.txt"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )

    if not capture_files:
        print("ERROR: No Amazon capture found.")
        print("Capture a shipment first.")
        return

    # Latest captured shipment
    source_file = capture_files[0]

    print(f"Reading: {source_file.name}")

    text = source_file.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    # ----------------------------------
    # TRACKING ID
    # ----------------------------------

    tracking_match = re.search(
        r"\bUK\d{8,}\b",
        source_file.stem,
        re.IGNORECASE,
    )

    if not tracking_match:
        tracking_match = re.search(
            r"\bUK\d{8,}\b",
            text,
            re.IGNORECASE,
        )

    if not tracking_match:
        print("ERROR: Tracking ID not found.")
        return

    tracking_id = tracking_match.group(0).upper()

    # ----------------------------------
    # PARSE HISTORY
    # ----------------------------------

    try:
        events = parse_history(text)
    except ValueError as error:
        print(f"ERROR: {error}")
        return

    status = determine_status(events)

    # ----------------------------------
    # JSON DATA STRUCTURE
    # ----------------------------------

    data = {
        "source": "Amazon Shipping",
        "capture_type": "manual_browser_capture",
        "tracking_id": tracking_id,
        "shipment_status": status,

        "reference": extract_field(
            text, "Reference #"
        ),

        "shipping_speed": extract_field(
            text, "Shipping speed"
        ),

        "package_size": extract_field(
            text, "Package size"
        ),

        "package_weight": extract_field(
            text, "Package weight"
        ),

        "total_charge": extract_field(
            text, "Total Charge"
        ),

        "events_count": len(events),
        "events": events,
    }

    # ----------------------------------
    # SAVE JSON
    # ----------------------------------

    output_file = (
        CAPTURE_DIR /
        f"{tracking_id}_amazon_history.json"
    )

    output_file.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("SUCCESS!")
    print(f"Tracking ID: {tracking_id}")
    print(f"Status: {status}")
    print(f"Events found: {len(events)}")
    print()
    print(f"JSON saved to: {output_file}")
    print()
    print("This JSON is from a saved capture.")
    print("It does not fetch live Amazon updates.")


if __name__ == "__main__":
    main()
