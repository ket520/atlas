"""On-demand Amazon Shipping browser capture for an authorised local demo.

GET /api/amazon-shipping/live/<UK tracking ID> starts a single-host Playwright job;
subsequent GETs return its status. Credentials never leave the Windows server.
Requires: py -m pip install playwright && py -m playwright install chromium
"""

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from amazon_shipping_demo import (
    CAPTURES,
    snapshot,
    is_confirmed_amazon_delivery,
)

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "amazon_poc_profile"
AMAZON_URL = "https://ship.amazon.co.uk/"
JOBS = {}
JOBS_LOCK = threading.Lock()
BROWSER_LOCK = threading.Lock()  # One persistent Chrome profile cannot run concurrently.
BROWSER_STATE = threading.local()  # Browser belongs to its worker thread.
BROWSER_IDLE_SECONDS = 120
REFRESH_AFTER_SECONDS = 180
MAX_JOBS = 20


def _secret(name):
    value = os.getenv(name)
    if value:
        return value
    for namefile in (".env.local", ".env"):
        path = ROOT / namefile
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            if key.strip() == name:
                raw = raw.strip()
                return raw[1:-1] if len(raw) > 1 and raw[0] == raw[-1] and raw[0] in "\"'" else raw
    return ""


def _locate(page, patterns, timeout=3000):
    for selector in patterns:
        item = page.locator(selector).first
        try:
            if item.count() and item.is_visible(timeout=timeout):
                return item
        except Exception:
            pass
    return None


def _first_text(page, label, timeout=7000):
    from playwright.sync_api import TimeoutError as PWTimeout
    names = [page.get_by_role("button", name=re.compile(label, re.I)), page.get_by_text(re.compile(label, re.I))]
    for locator in names:
        try:
            found = locator.first
            found.wait_for(state="visible", timeout=timeout)
            return found
        except PWTimeout:
            pass
    raise RuntimeError(f"Amazon action not found: {label}")


def _maybe_login(page):
    """Sign in with host-only credentials if Amazon presents an email/password form."""
    search = page.get_by_role("textbox", name=re.compile(r"Search by tracking", re.I))
    try:
        search.wait_for(state="visible", timeout=9000)
        return search
    except Exception:
        pass

    email_box = _locate(page, ['#ap_email', 'input[name="email"]', 'input[type="email"]'])
    if email_box is not None:
        email = _secret("AMAZON_SHIPPING_EMAIL")
        if not email:
            raise RuntimeError("Amazon login required: set AMAZON_SHIPPING_EMAIL in .env.local on the Windows host.")
        email_box.fill(email)
        continue_button = _locate(page, ['#continue', 'input[type="submit"]', 'button[type="submit"]'])
        if continue_button is not None:
            continue_button.click()

    # Amazon can navigate between separate email and password pages.
    # Wait for the password page instead of checking too early.
    password_box = page.locator('#ap_password, input[name="password"], input[type="password"]').first
    try:
        password_box.wait_for(state="visible", timeout=18000)
    except Exception:
        password_box = None
    if password_box is not None:
        password = _secret("AMAZON_SHIPPING_PASSWORD")
        if not password:
            raise RuntimeError("Amazon password required: set AMAZON_SHIPPING_PASSWORD in .env.local on the Windows host.")
        password_box.fill(password)
        sign_in = _locate(page, ['#signInSubmit', 'input[type="submit"]', 'button[type="submit"]'])
        if sign_in is None:
            raise RuntimeError("Amazon sign-in submit button not found.")
        sign_in.click()

    try:
        search.wait_for(state="visible", timeout=60000)
    except Exception as exc:
        raise RuntimeError("Amazon login did not reach the shipment search. Check MFA/OTP, session, and selectors on the Windows host.") from exc
    return search


def _history_from_page(text, tracking_id):
    """Parse the visible Shipping history and five shipment fields only."""
    from datetime import timezone, timedelta
    lines = [" ".join(part.split()) for part in text.splitlines() if part.strip()]
    shipping_id = re.search(r"\bTracking ID\s*:?\s*([A-Z0-9-]{1,64})\b", text, re.I)
    if not shipping_id or shipping_id.group(1).upper() != tracking_id:
        raise RuntimeError("Amazon returned a different Tracking ID; nothing was saved.")

    def field(label):
        for i, line in enumerate(lines):
            if line.casefold() == label.casefold() and i + 1 < len(lines):
                return lines[i + 1]
            if line.lower().startswith(label.lower() + ":"):
                return line.split(":", 1)[1].strip()
        return ""

    index = next((i for i in range(len(lines) - 1, -1, -1)
                  if lines[i].lower() == "delivery history"), -1)
    if index == -1:
        raise RuntimeError("Amazon's Delivery history did not appear.")

    year_match = re.search(r"\b20\d{2}\b", text)
    year = int(year_match.group()) if year_match else datetime.now().year
    date_header = re.compile(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s*"
                             r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*"
                             r"(\d{1,2})(?:,?\s*(20\d{2}))?$", re.I)
    hour = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*([+-]\d{1,2}(?::?\d{2})?))?$")
    months = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
    day = None
    events = []
    current = None
    rest = []

    def finish():
        nonlocal current, rest
        if current is None:
            return
        if rest and "," in rest[0] and not rest[0].lower().startswith("package "):
            current["location"] = rest.pop(0)
        current["note"] = " ".join(rest)[:500]
        if current["description"]:
            events.append(current)
        current = None
        rest = []

    for line in lines[index + 1:]:
        matched = date_header.fullmatch(line)
        if matched:
            finish()
            day = (int(matched.group(3) or year), months[matched.group(1)[:3].title()], int(matched.group(2)))
            continue
        clock = hour.fullmatch(line)
        if clock and day:
            finish()
            offset = clock.group(3) or ""
            normalized = ""
            tz = None
            if offset:
                tz_m = re.fullmatch(r"([+-])(\d{1,2})(?::?(\d{2}))?", offset)
                if tz_m:
                    hh, mm = int(tz_m.group(2)), int(tz_m.group(3) or "0")
                    if hh <= 23 and mm <= 59:
                        delta = timedelta(hours=hh, minutes=mm)
                        tz = timezone(delta if tz_m.group(1) == "+" else -delta)
                        normalized = f"{tz_m.group(1)}{hh:02}:{mm:02}"
            dt = datetime(*day, int(clock.group(1)), int(clock.group(2)), tzinfo=tz)
            current = {
                "date": dt.date().isoformat(), "time": dt.strftime("%H:%M"),
                "timezone_offset": normalized, "timestamp": dt.isoformat(),
                "description": "", "location": "", "note": "",
            }
            continue
        if current is not None:
            if not current["description"]:
                current["description"] = line
            else:
                rest.append(line)
    finish()
    if not events:
        raise RuntimeError("No Amazon tracking events parsed; nothing was overwritten.")
    texts = [e["description"].lower() for e in events]

    status = (
        "Delivered"
        if is_confirmed_amazon_delivery({"events": events})
        else "Out for delivery"
        if any("out for delivery" in value for value in texts)
        else "In transit"
    )
    return {
        "source": "amazon_shipping_live_browser_capture",
        "tracking_id": tracking_id,
        "shipment_status": status,
        "reference": field("Reference #"),
        "shipping_speed": field("Shipping speed"),
        "package_size": field("Package size"),
        "package_weight": field("Package weight"),
        "total_charge": field("Total Charge"),
        "events_count": len(events),
        "events": events,
    }


def _save_pod(page, context, tracking_id):
    """Try popup/download and PDF response capture; missing PDF is nonfatal."""
    from playwright.sync_api import TimeoutError as PWTimeout
    path = CAPTURES / f"{tracking_id}_pod.pdf"
    responses = []
    downloads = []
    popups = []

    def on_response(response):
        ctype = response.headers.get("content-type", "").lower()
        if ("application/pdf" in ctype or ".pdf" in response.headers.get("content-disposition", "").lower()):
            responses.append(response)

    def on_download(download):
        downloads.append(download)

    def on_page(new_page):
        popups.append(new_page)

    context.on("response", on_response)
    page.on("download", on_download)
    context.on("page", on_page)
    try:
        control = _first_text(page, r"Download Proof of Delivery", timeout=4000)
        control.click(timeout=10000)
        page.wait_for_timeout(2500)
        for download in downloads:
            if download.suggested_filename.lower().endswith(".pdf"):
                download.save_as(str(path))
                if path.read_bytes().startswith(b"%PDF-"):
                    return True
                path.unlink(missing_ok=True)
        for response in reversed(responses):
            try:
                data = response.body()
                if data.startswith(b"%PDF-") and len(data) <= 20 * 1024 * 1024:
                    path.write_bytes(data)
                    return True
            except Exception:
                pass
        # A page with an HTTPS PDF URL can be fetched within this authorised session.
        for popup in reversed(popups):
            url = popup.url
            if not re.match(r"^https://[^/]*(?:amazon\.co\.uk|amazon\.com|amazonaws\.com)(?:[:/]|$)", url, re.I):
                continue
            try:
                response = context.request.get(url, timeout=12000)
                data = response.body()
                if response.ok and data.startswith(b"%PDF-") and len(data) <= 20 * 1024 * 1024:
                    path.write_bytes(data)
                    return True
            except Exception:
                pass
    except (PWTimeout, RuntimeError):
        pass
    finally:
        context.remove_listener("response", on_response)
        page.remove_listener("download", on_download)
        context.remove_listener("page", on_page)
    return path.is_file() and path.read_bytes()[:5] == b"%PDF-"





def _close_worker_browser():
    session = getattr(BROWSER_STATE, "session", None)
    if session is None:
        return

    del BROWSER_STATE.session
    playwright, context = session

    try:
        context.close()
    except Exception:
        pass

    try:
        playwright.stop()
    except Exception:
        pass


@contextmanager
def _borrow_browser():
    session = getattr(BROWSER_STATE, "session", None)

    if session is None:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()

        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE),
                headless=True,
                accept_downloads=True,
                viewport={"width": 1450, "height": 950},
            )
        except Exception:
            playwright.stop()
            raise

        session = (playwright, context)
        BROWSER_STATE.session = session

    try:
        yield session[1]

    except LookupSuperseded:
        raise

    except Exception:
        _close_worker_browser()
        raise


def _capture(tracking_id, should_cancel=None, on_progress=None):
    def progress(completed, label):
        if on_progress:
            on_progress(completed, label)

    def check_cancel():
        if should_cancel and should_cancel():
            raise LookupSuperseded()

    CAPTURES.mkdir(parents=True, exist_ok=True)

    with BROWSER_LOCK:
        with _borrow_browser() as context:
            page = None

            try:
                page = context.pages[0] if context.pages else context.new_page()

                page.goto(
                    AMAZON_URL,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                check_cancel()
                progress(1, "Signing in to Amazon")

                search = _maybe_login(page)

                check_cancel()
                progress(2, "Finding shipment")

                search.fill(tracking_id)


                check_cancel()

                print(
                    f"[Amazon] Searching for {tracking_id}...",
                    flush=True,
                )

                opened = False
                deadline = time.monotonic() + 30

                while time.monotonic() < deadline and not opened:
                    check_cancel()

                    candidates = [
                        page.locator("tr").filter(has_text=tracking_id),
                        page.get_by_role("row").filter(has_text=tracking_id),
                        page.get_by_role("link").filter(has_text=tracking_id),
                        page.get_by_text(tracking_id, exact=True),
                    ]

                    for matches in candidates:
                        try:
                            for index in range(min(matches.count(), 12)):
                                result = matches.nth(index)

                                if result.is_visible():
                                    result.click(timeout=4000)
                                    opened = True
                                    break

                        except Exception:
                            pass

                        if opened:
                            break

                    if not opened:
                        page.wait_for_timeout(750)

                if not opened:
                    debug_path = (
                        CAPTURES / f"{tracking_id}_search_debug.png"
                    )

                    try:
                        page.screenshot(
                            path=str(debug_path),
                            full_page=True,
                        )

                        print(
                            f"[Amazon] Screenshot saved: {debug_path}",
                            flush=True,
                        )

                    except Exception as exc:
                        print(
                            f"[Amazon] Screenshot failed: {exc}",
                            flush=True,
                        )

                    check_cancel()

                    raise RuntimeError(
                        f"Amazon search has no selectable "
                        f"shipment matching {tracking_id}."
                    )

                progress(3, "Reading delivery history")

                _first_text(
                    page,
                    r"See all updates",
                    timeout=12000,
                ).click(timeout=10000)

                page.get_by_text(
                    "Delivery history",
                    exact=True,
                ).first.wait_for(
                    state="visible",
                    timeout=15000,
                )

                body = page.locator("body").inner_text(timeout=15000)

                result = _history_from_page(body, tracking_id)

                check_cancel()

                # Save only confirmed delivered shipment history.
                # Undelivered history remains in memory.
                out = CAPTURES / f"{tracking_id}_amazon_history.json"

                if is_confirmed_amazon_delivery(result):
                    temporary = (
                        CAPTURES
                        / f"{tracking_id}_amazon_history.json.tmp"
                    )

                    temporary.write_text(
                        json.dumps(
                            result,
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                    temporary.replace(out)

                progress(4, "Checking proof of delivery")

                has_pdf = False

                if is_confirmed_amazon_delivery(result):
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(400)

                    check_cancel()

                    has_pdf = _save_pod(
                        page,
                        context,
                        tracking_id,
                    )

                check_cancel()

                progress(5, "Finalizing Amazon tracking data")
                progress(6, "Preparing shipment updates")

                return {
                    "pdf": has_pdf,
                    "raw": result,
                }

            finally:
                # Keep Chromium alive for the next shipment.
                # Close only extra tabs opened during POD capture.
                if page is not None:
                    try:
                        for extra_page in list(context.pages):
                            if (
                                extra_page is not page
                                and not extra_page.is_closed()
                            ):
                                extra_page.close()

                    except Exception:
                        pass


# One browser worker for the authenticated Amazon profile.
# Newest requested shipment is processed first.
VIEWER_LATEST = {}
SCHEDULER_ACTIVE = False


class LookupSuperseded(Exception):
    """The viewer switched away from this shipment."""


def _set_progress(tracking_id, job, completed, label):
    with JOBS_LOCK:
        if JOBS.get(tracking_id) is job:
            job["progress"] = {
                "completed": completed,
                "total": 7,
                "percent": round(completed * 100 / 7),
                "label": label,
            }


def _no_viewers_left(tracking_id, job):
    with JOBS_LOCK:
        viewers = job.get("viewers", set())

        only_prefetch = viewers == {"prefetch-worker"}

        foreground_waiting = any(
            other is not job
            and other["state"] == "queued"
            and any(
                v != "prefetch-worker"
                for v in other.get("viewers", set())
            )
            for other in JOBS.values()
        )

        return (
            JOBS.get(tracking_id) is not job
            or not viewers
            or (only_prefetch and foreground_waiting)
        )


def _queue_loop():
    global SCHEDULER_ACTIVE

    idle_since = None

    while True:
        with JOBS_LOCK:
            candidates = [
                (tracking_id, job)
                for tracking_id, job in JOBS.items()
                if job["state"] == "queued" and job.get("viewers")
            ]

            if candidates:
                tracking_id, job = max(
                    candidates,
                    key=lambda item: item[1]["requested"],
                )

                job["state"] = "loading"
                job["progress"] = {
                    "completed": 0,
                    "total": 7,
                    "percent": 0,
                    "label": "Opening Amazon",
                }

        if not candidates:
            if idle_since is None:
                idle_since = time.monotonic()

            elif time.monotonic() - idle_since >= BROWSER_IDLE_SECONDS:
                _close_worker_browser()

                with JOBS_LOCK:
                    new_requests = any(
                        j["state"] == "queued" and j.get("viewers")
                        for j in JOBS.values()
                    )

                    if not new_requests:
                        SCHEDULER_ACTIVE = False
                        return

                idle_since = None
                continue

            time.sleep(0.25)
            continue

        idle_since = None

        try:
            assets = _capture(
                tracking_id,
                lambda: _no_viewers_left(tracking_id, job),
                lambda completed, label: _set_progress(tracking_id, job, completed, label),
            )

            data = snapshot(
                tracking_id,
                raw_override=assets.pop("raw")
            )

            if not data:
                raise RuntimeError(
                    "Amazon capture finished but shipment data "
                    "was unavailable."
                )

            with JOBS_LOCK:
                if JOBS.get(tracking_id) is job:
                    job.update(
                        state="ready",
                        data=data,
                        assets=assets,
                        progress={"completed": 7, "total": 7, "percent": 100, "label": "Shipment updates ready"},
                        finished=time.monotonic(),
                    )

        except LookupSuperseded:
            with JOBS_LOCK:
                if JOBS.get(tracking_id) is job:
                    job.update(
                        state="cancelled",
                        finished=time.monotonic(),
                    )

        except Exception as error:
            message = str(error)

            for secret in (
                _secret("AMAZON_SHIPPING_EMAIL"),
                _secret("AMAZON_SHIPPING_PASSWORD"),
            ):
                if secret:
                    message = message.replace(secret, "[redacted]")

            with JOBS_LOCK:
                if JOBS.get(tracking_id) is job:
                    job.update(
                        state="error",
                        message=message[:400],
                        finished=time.monotonic(),
                    )

def session_snapshot(tracking_id, viewer):
    """Read a temporary result only for its browser session."""
    if not viewer:
        return None

    with JOBS_LOCK:
        job = JOBS.get(tracking_id)

        if (
            job
            and job.get("state") == "ready"
            and viewer in job.get("sessions", set())
        ):
            return job.get("data")

    return None

def serve_live(handler, path, params):
    global SCHEDULER_ACTIVE

    match = re.fullmatch(
        r"/api/amazon-shipping/live/([A-Z0-9-]{1,64})/?",
        path,
        re.I,
    )

    if not match:
        return handler.send_json(
            400,
            {"error": "Invalid Amazon tracking ID."},
        )

    tracking_id = match.group(1).upper()
    force = params.get("refresh", [""])[0] == "1"
    viewer = params.get("viewer", [""])[0]

    if viewer and not re.fullmatch(
        r"[A-Za-z0-9_-]{8,64}",
        viewer,
    ):
        return handler.send_json(
            400,
            {"error": "Invalid viewer token."},
        )

    viewer = viewer or "manual-request"
    now = time.monotonic()

    with JOBS_LOCK:
        if force or VIEWER_LATEST.get(viewer) != tracking_id:
            previous = VIEWER_LATEST.get(viewer)
            VIEWER_LATEST[viewer] = tracking_id

            if previous and previous != tracking_id:
                old_job = JOBS.get(previous)

                if old_job:
                    old_job.setdefault(
                        "viewers", set()
                    ).discard(viewer)

                    if (
                        old_job["state"] == "queued"
                        and not old_job["viewers"]
                    ):
                        old_job.update(
                            state="cancelled",
                            finished=now,
                        )

        job = JOBS.get(tracking_id)

        active = (
            job is not None
            and job["state"] in ("queued", "loading")
        )

        stale = job is None or (
            job["state"] in ("error", "cancelled")
            and now - job.get("finished", 0)
            >= REFRESH_AFTER_SECONDS
        )

        if job and job["state"] == "cancelled":
            stale = True


        # Undelivered results belong to one browser session.
        if (
            job
            and job["state"] == "ready"
            and not is_confirmed_amazon_delivery(job.get("data"))
            and viewer not in job.get("sessions", set())
        ):
            if (
                job.get("foreground_owner") is None
                and "prefetch-worker" in job.get("sessions", set())
            ):
                # First browser session claims the prefetched result.
                job["foreground_owner"] = viewer
                job["sessions"].add(viewer)
            else:
                # Another browser session, including a page refresh,
                # must get a fresh lookup.
                stale = True

        if not active and (force or stale):
            # Confirmed delivered shipments remain permanently cached.
            # Do not start Playwright again for a saved delivery.
            saved = snapshot(tracking_id)

            if saved:
                return handler.send_json(200, {
                    "tracking_id": tracking_id,
                    "state": "ready",
                    "data": saved,
                    "assets": {},
                    "progress": {
                        "completed": 7,
                        "total": 7,
                        "percent": 100,
                        "label": "Saved delivered shipment ready",
                    },
                })

            queued_count = sum(
                1 for item in JOBS.values()
                if item["state"] == "queued"
            )

            if queued_count >= MAX_JOBS:
                return handler.send_json(
                    429,
                    {
                        "error": (
                            "Amazon queue is full; retry shortly."
                        )
                    },
                )

            job = {
                "state": "queued",
                "progress": {"completed": 0, "total": 7, "percent": 0, "label": "Waiting for Amazon lookup"},
                "requested": now,
                "viewers": {viewer},
                "sessions": {viewer},
            }

            JOBS[tracking_id] = job

            if not SCHEDULER_ACTIVE:
                SCHEDULER_ACTIVE = True

                threading.Thread(
                    target=_queue_loop,
                    daemon=True,
                    name="AmazonShippingWorker",
                ).start()

        elif active and (
            force or VIEWER_LATEST.get(viewer) == tracking_id
        ):
            job.setdefault("viewers", set()).add(viewer)
            job.setdefault("sessions", set()).add(viewer)

            if viewer != "prefetch-worker":
                job.setdefault("foreground_owner", viewer)

        response = {
            "tracking_id": tracking_id,
            "state": job["state"],
            "progress": job.get("progress", {"completed": 0, "total": 7, "percent": 0, "label": "Opening Amazon"}),
        }

        if job["state"] == "ready":
            data = job["data"]

            if is_confirmed_amazon_delivery(data):
                response["data"] = data
            else:
                response["data"] = dict(data)

                documents = dict(data.get("documents") or {})

                for key in (
                    "pod_view_url",
                    "pod_download_url",
                ):
                    link = documents.get(key)

                    if link:
                        separator = "&" if "?" in link else "?"
                        documents[key] = (
                            f"{link}{separator}viewer={viewer}"
                        )

                response["data"]["documents"] = documents

            response["assets"] = job.get("assets", {})

        elif job["state"] == "error":
            response["error"] = job.get(
                "message",
                "Amazon lookup failed",
            )

    return handler.send_json(200, response)
