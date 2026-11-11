
"""Preload Amazon-tab Delivered shipments first, newest dates first in each group."""

import re
import threading
import time

from amazon_shipping_demo import snapshot
from amazon_shipping_live import serve_live, JOBS, JOBS_LOCK


_started = False
_start_lock = threading.Lock()


class _Collector:
    def send_json(self, status, payload):
        return status, payload


def _call(tracking_id, start=False):
    params = {"viewer": ["prefetch-worker"]}

    if start:
        params["refresh"] = ["1"]

    return serve_live(
        _Collector(),
        f"/api/amazon-shipping/live/{tracking_id}",
        params,
    )


def _ordered_ids():
    from delivery_data import connect

    with connect() as db:
        rows = db.execute("""
            SELECT
                COALESCE(
                    NULLIF(trim(json_extract(payload, '$.owTrackingNo')), ''),
                    json_extract(payload, '$.trk')
                ) AS tracking,
                COALESCE(
                    NULLIF(json_extract(payload, '$.date'), ''),
                    NULLIF(json_extract(payload, '$.dispatchDate'), ''),
                    NULLIF(json_extract(payload, '$.orderDate'), ''),
                    ''
                ) AS scheduled,
                upper(trim(COALESCE(
                    NULLIF(trim(json_extract(payload, '$.amazonSheetStatus')), ''),
                    json_extract(payload, '$.amazonStatus'), ''
                ))) AS amazon_status
            FROM deliveries
            WHERE json_extract(payload, '$.carrier') = 'AMZ'
            ORDER BY CASE WHEN amazon_status='DELIVERED' THEN 0 ELSE 1 END,
                     CASE WHEN date(substr(scheduled, 1, 10)) IS NULL THEN 1 ELSE 0 END,
                     scheduled DESC, order_id DESC
        """).fetchall()

    seen = set()

    for tracking, scheduled, amazon_status in rows:
        tracking = str(tracking or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{1,64}", tracking):
            continue

        if tracking not in seen:
            seen.add(tracking)
            yield tracking


def _loop():
    failure_retry_at = {}

    while True:
        try:
            from delivery_data import cached_or_schedule_sync

            cached_or_schedule_sync()

            for tracking_id in _ordered_ids():
                # Saved shipments do not need Playwright.
                if snapshot(tracking_id):
                    continue

                # Avoid repeating failed lookups continuously.
                if time.monotonic() < failure_retry_at.get(
                    tracking_id, 0
                ):
                    continue

                # Never overwrite a queued, running, or ready
                # shipment with another background job.
                with JOBS_LOCK:
                    existing = JOBS.get(tracking_id)

                    if existing and existing.get("state") in (
                        "queued",
                        "loading",
                        "ready",
                    ):
                        continue

                print(
                    f"[Amazon prefetch] Starting {tracking_id}",
                    flush=True,
                )

                status, result = _call(tracking_id, start=True)
                deadline = time.monotonic() + 180

                while (
                    status == 200
                    and result.get("state") in ("queued", "loading")
                ):
                    if time.monotonic() >= deadline:
                        break

                    time.sleep(2)
                    status, result = _call(tracking_id)

                if status == 200 and result.get("state") == "ready":
                    if snapshot(tracking_id):
                        print(
                            f"[Amazon prefetch] Delivered, permanently saved: {tracking_id}",
                            flush=True,
                        )
                    else:
                        failure_retry_at[tracking_id] = (
                            time.monotonic() + 1800
                        )

                        print(
                            f"[Amazon prefetch] Not delivered, temporary only: {tracking_id}",
                            flush=True,
                        )
                else:
                    failure_retry_at[tracking_id] = (
                        time.monotonic() + 1800
                    )

                    print(
                        f"[Amazon prefetch] Deferred {tracking_id}: "
                        f"{result.get('error') or result.get('state')}",
                        flush=True,
                    )

                # Keep requests controlled.
                time.sleep(2)

        except Exception as exc:
            print(
                f"[Amazon prefetch] Scan error: {exc}",
                flush=True,
            )

        # Each new pass starts with uncached Amazon-tab Delivered shipments.
        time.sleep(60)


def start_amazon_prefetch():
    global _started

    with _start_lock:
        if _started:
            return

        _started = True

        threading.Thread(
            target=_loop,
            daemon=True,
            name="AmazonShippingPrefetch",
        ).start()
