import html
import re
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote

from playwright.sync_api import sync_playwright
from palletways_portal_details import extract_consignment_details


ROOT = Path(__file__).resolve().parent

PROFILE_DIR = (
    ROOT
    / "data"
    / "palletways-portal-profile"
)

PORTAL_BASE = (
    "https://portal.palletways.com"
)

CACHE = {}
CACHE_TTL = 120
_browser_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="palletways-portal")
_browser_playwright = None
_browser_context = None


def _shared_context():
    global _browser_playwright, _browser_context
    if _browser_context is not None:
        try:
            if _browser_context.browser.is_connected():
                if not _browser_context.pages:
                    _browser_context.new_page()
                return _browser_context
        except Exception:
            pass
        try:
            _browser_context.close()
        except Exception:
            pass
        _browser_context = None
    if _browser_playwright is not None:
        try:
            _browser_playwright.stop()
        except Exception:
            pass
        _browser_playwright = None
    _browser_playwright = sync_playwright().start()
    try:
        _browser_context = _open_context(_browser_playwright, headless=False)
        return _browser_context
    except Exception:
        _browser_playwright.stop()
        _browser_playwright = None
        raise


def _browser_call(operation):
    # Sync Playwright objects cannot move between the server's request threads.
    def run():
        context = _shared_context()
        try:
            return operation(context)
        except Exception:
            if not context.browser.is_connected():
                return operation(_shared_context())
            raise
    return _browser_worker.submit(run).result()


def _clean(value):
    value = re.sub(
        r"<br\s*/?>",
        "\n",
        str(value or ""),
        flags=re.I,
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    return html.unescape(
        value
    ).strip()


def _yes_no(source, label):
    match = re.search(
        re.escape(label)
        + r":\s*"
        + r"<i[^>]+fa-"
        + r"(check-square|square)",
        source,
        flags=re.I,
    )

    if not match:
        return ""

    return (
        "yes"
        if match.group(1).lower()
        == "check-square"
        else "no"
    )


def _extract_notes(source):
    notes = []

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        source,
        flags=re.I | re.S,
    )

    for row in rows:
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row,
            flags=re.I | re.S,
        )

        if len(cells) != 6:
            continue

        note_type = _clean(cells[0])

        if not note_type:
            continue

        comment_html = cells[3]
        comment = _clean(comment_html)

        filenames = re.findall(
            r"file=([^&\"']+"
            r"\.(?:jpg|jpeg|png|tif|tiff))",
            comment_html,
            flags=re.I,
        )

        if not filenames:
            filenames = re.findall(
                r"([A-Za-z0-9_.-]+"
                r"\.(?:jpg|jpeg|png|tif|tiff))",
                comment,
                flags=re.I,
            )

        notes.append({
            "type": note_type,
            "number": _clean(cells[1]),
            "barcode": _clean(cells[2]),
            "comment": comment,
            "date": _clean(cells[4]),
            "time": _clean(cells[5]),
            "files": list(
                dict.fromkeys(
                    filenames
                )
            ),
        })

    return notes


def _extract_invoice(source):
    invoices = []

    pattern = re.compile(
        r"view_invoice\.php\?inv="
        r"([^&\"']+)"
        r"&type=([^\"']+)"
        r"[^>]*>"
        r"([^<]+)</a>"
        r".*?</td>"
        r"<td[^>]*>(.*?)</td>"
        r"<td[^>]*>(.*?)</td>"
        r"<td[^>]*>(.*?)</td>",
        flags=re.I | re.S,
    )

    for match in pattern.finditer(source):
        invoices.append({
            "number": _clean(
                match.group(3)
            ),
            "date": _clean(
                match.group(4)
            ),
            "type": _clean(
                match.group(5)
            ),
            "value": _clean(
                match.group(6)
            ),
        })

    return invoices


def _extract_media(notes, source=""):
    media = []

    for note in notes:
        note_type = str(
            note.get("type") or ""
        ).strip()

        for filename in (
            note.get("files") or []
        ):
            media.append({
                "type": note_type,
                "filename": filename,
                "date": note.get("date") or "",
                "time": note.get("time") or "",
                "noteNumber":
                    note.get("number") or "",
            })

    # Portal layouts can expose photos outside the six-cell consignment-note table.
    # Decode URL/HTML escaping and discover those file links for any tracking ID.
    decoded = html.unescape(source)
    for match in re.finditer(r"\bfile=([^&\"'<>\s)]+)", decoded, re.I):
        filename = unquote(match[1])
        if re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|tif|tiff)", filename, re.I):
            media.append({"type": "Image", "filename": filename, "date": "", "time": "", "noteNumber": ""})
    unique = {}
    for item in media:
        filename = unquote(item["filename"])
        if re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|tif|tiff)", filename, re.I):
            unique.setdefault(filename, {**item, "filename": filename})
    return list(unique.values())


def _open_context(
    playwright,
    headless=True,
):
    PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        playwright.chromium
        .launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
        )
    )


def _is_tracking_page(source):
    return "Consignment Notes" in source or "Palletways Tracking ID" in source


def _submit_saved_login(page):
    """Submit an already-filled login form without reading credentials into Python."""
    try:
        password = page.locator('input[type="password"]:visible').first
        if not password.count():
            return False
        form = password.locator('xpath=ancestor::form[1]')
        if not form.count():
            return False
        ready = form.evaluate("""form => {
            const visible = field => field.getClientRects().length > 0;
            const password = [...form.querySelectorAll('input[type="password"]')].find(visible);
            const username = [...form.querySelectorAll('input')].find(field =>
                visible(field) && ['text', 'email'].includes(field.type));
            return Boolean(username?.value.trim() && password?.value);
        }""")
        if ready is not True:
            return False
        button = form.get_by_role('button', name=re.compile(r'log\s*in|sign\s*in', re.I)).first
        if not button.count():
            button = form.locator('button[type="submit"], input[type="submit"], button:not([type])').first
        if not button.count() or not button.is_visible() or not button.is_enabled():
            return False
        button.click(timeout=5000)
        return True
    except Exception:
        # Manual sign-in remains available if the portal uses a different form.
        return False


def _tracking_source(context, url, login_timeout=180):
    # Show the shipment in the visible browser, including on saved sessions.
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        response = context.request.get(url, timeout=30000)
        source = response.text()
        if response.ok and _is_tracking_page(source):
            return source
        deadline = time.monotonic() + login_timeout
        login_submitted = False
        while time.monotonic() < deadline:
            if page.is_closed():
                raise RuntimeError("Palletways login browser was closed before sign-in completed. Click Refresh photos to try again.")
            if _is_tracking_page(page.content()):
                return page.content()
            if not login_submitted:
                login_submitted = _submit_saved_login(page)
            page.wait_for_timeout(1500)
            response = context.request.get(url, timeout=15000)
            source = response.text()
            if response.ok and _is_tracking_page(source):
                return source
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("Palletways login could not finish. Sign in using the open Palletways window, then click Refresh photos.") from None
    raise RuntimeError("Palletways sign-in timed out after three minutes. Sign in using the open Palletways window, then click Refresh photos.")


def portal_details(tracking_id, force=False):
    tracking_id = str(
        tracking_id or ""
    ).strip()

    if not re.fullmatch(
        r"\d{11}",
        tracking_id,
    ):
        raise ValueError(
            "Invalid Palletways tracking ID."
        )

    cached = CACHE.get(
        tracking_id
    )

    if (
        not force
        and cached
        and time.time()
        - cached["time"]
        < CACHE_TTL
    ):
        return cached["data"]

    url = (
        PORTAL_BASE
        + "/cwp/tt.php"
        + "?dc_syscon="
        + quote(
            tracking_id,
            safe="",
        )
        + "&basic=false"
    )

    source = _browser_call(lambda context: _tracking_source(context, url))

    if (
        "Consignment Notes"
        not in source
        and "Palletways Tracking ID"
        not in source
    ):
        raise RuntimeError(
            "Palletways portal session is not "
            "logged in. Run palletways_portal.py "
            "once and sign in."
        )

    notes = _extract_notes(
        source
    )

    result = {
        "ok": True,
        "trackingId": tracking_id,
        "details": extract_consignment_details(source),
        "readAt": datetime.now(timezone.utc).isoformat(),

        "bookInRequested":
            _yes_no(
                source,
                "Book-in requested",
            ),

        "tailLiftRequested":
            _yes_no(
                source,
                "Tail-lift requested",
            ),

        "handBallRequested":
            _yes_no(
                source,
                "Hand-ball requested",
            ),

        "notes": notes,

        "media":
            _extract_media(
                notes, source
            ),

        "invoices":
            _extract_invoice(
                source
            ),
    }

    CACHE[tracking_id] = {
        "time": time.time(),
        "data": result,
    }

    return result


def portal_media(filename):
    filename = str(
        filename or ""
    ).strip()

    if not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,255}",
        filename,
    ):
        raise ValueError(
            "Invalid Palletways media filename."
        )

    url = (
        PORTAL_BASE
        + "/show_pod.php"
        + "?fullsize=true"
        + "&file="
        + quote(
            filename,
            safe="",
        )
    )

    def read_media(context):
        response = context.request.get(url, timeout=30000)
        if not response.ok:
            raise RuntimeError(f"Palletways media returned HTTP {response.status}.")
        return response.body(), response.headers.get("content-type", "application/octet-stream")

    content, content_type = _browser_call(read_media)

    if (
        "text/html"
        in content_type.lower()
        and b"<html" in content[:1000].lower()
    ):
        raise RuntimeError(
            "Palletways portal session expired."
        )

    return (
        content,
        content_type,
    )


def login():
    PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sync_playwright() as p:
        context = _open_context(
            p,
            headless=False,
        )

        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )

        page.goto(
            PORTAL_BASE,
            wait_until="domcontentloaded",
        )

        print()
        print(
            "Log into Palletways in the browser."
        )
        print(
            "When the portal is fully open, "
            "return here and press Enter."
        )

        input()

        context.close()


if __name__ == "__main__":
    login()
