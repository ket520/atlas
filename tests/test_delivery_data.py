import tempfile
import json
import threading
import unittest
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

import delivery_data
import server


class DeliveryDataTests(unittest.TestCase):
    def test_amazon_courier_filters_preserve_raw_states_and_ow_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            delivery_data.archive([
                {"Order no": str(index), "Delivery method": "AMA XL", "Tracking No": tracking, "Status": "C"}
                for index, tracking in enumerate(["READY", "TRANSIT", "NEW", "MISSING"], 1)
            ])
            delivery_data.archive_amazon_shipping([
                {"trackingId": "READY", "status": "READY_FOR_RECEIVE"},
                {"trackingId": "TRANSIT", "status": "IN_TRANSIT"},
                {"trackingId": "NEW", "status": "CUSTOM_NEW_STATUS"},
            ])
            def orders(status, **options):
                return [item["order"] for item in delivery_data.query_records(carrier="AMZ", status=status, **options)["deliveries"]]
            self.assertEqual(orders("amazon:READY_FOR_RECEIVE", courier_status=True), ["1"])
            self.assertEqual(orders("amazon:IN_TRANSIT", courier_status=True), ["2"])
            self.assertEqual(orders("amazon:CUSTOM_NEW_STATUS", courier_status=True), ["3"])
            self.assertEqual(orders("Delivered", courier_status=True), ["4"])
            self.assertEqual(set(orders("Scheduled")), {"1", "2"})
            facets = delivery_data.summary()["filterFacets"]
            self.assertTrue(any(item["amazonStatus"] == "CUSTOM_NEW_STATUS" for item in facets))
            delivery_data.archive([{"Order no": "3", "Delivery method": "AMA XL", "Tracking No": "NEW", "Status": "C"}])
            self.assertEqual(orders("amazon:CUSTOM_NEW_STATUS", courier_status=True), ["3"])
            delivery_data.archive_amazon_shipping([])
            self.assertEqual(set(orders("Delivered", courier_status=True)), {"1", "2", "3", "4"})

    def test_tracking_filter_levels_and_counts_cover_all_pages(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            delivery_data.archive([
                {"Order no": str(index), "Delivery method": method, "Status": status,
                 "Tracking No": "UK1234567890"}
                for index, method, status in [
                    (1, "AMA Standard", "S"), (2, "AMA Standard", "C"),
                    (3, "XDP", "S"), (4, "XDP", "X"),
                    (5, "To be cancelled", "W"), (6, "On hold - TBC", "W"),
                ]
            ])
            with delivery_data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload, '$.date', ?) WHERE order_id IN ('1','2','3','4')",
                           (delivery_data.date.today().isoformat(),))
                db.commit()
            page = delivery_data.query_records(general_scope="today", carrier="AMZ", status="Delivered", limit=1)
            self.assertEqual([item["order"] for item in page["deliveries"]], ["2"])
            self.assertEqual(delivery_data.query_records(general_scope="Cancelled")["total"], 2)
            self.assertEqual(delivery_data.query_records(general_scope="Cancelled", carrier="XDP")["total"], 1)
            self.assertEqual(delivery_data.query_records(general_scope="On Hold")["total"], 1)
            facets = delivery_data.summary()["filterFacets"]
            self.assertEqual(sum(item["count"] for item in facets), 6)
            self.assertEqual(sum(item["count"] for item in facets if item["today"]), 3)
            self.assertEqual(sum(item["count"] for item in facets if item["today"] and item["carrier"] == "AMZ"), 2)

    def test_amazon_missing_tracking_is_unscheduled_but_missing_sheet_match_uses_ow(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            rows = [
                {"Order no": "NO-ID", "Delivery method": "AMA XL", "Tracking No": " ", "Status": "Completed"},
                {"Order no": "UNMATCHED-ID", "Delivery method": "AMA Letter", "Tracking No": "UK1234567890", "Status": "Completed"},
                {"Order no": "OTHER-COURIER", "Delivery method": "XDP", "Tracking No": "", "Status": "Completed"},
            ]
            delivery_data.archive(rows)
            delivery_data.archive_amazon_shipping([])
            self.assertEqual(delivery_data.detail("NO-ID")["st"], "Unscheduled")
            self.assertEqual(delivery_data.detail("UNMATCHED-ID")["st"], "Delivered")
            self.assertEqual(delivery_data.detail("OTHER-COURIER")["st"], "Delivered")
            with delivery_data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload, '$.st', 'Delivered') WHERE order_id='NO-ID'")
                db.commit()
            with patch.object(delivery_data, "_statuses_refreshed", False), patch.object(delivery_data, "sync", return_value={}):
                delivery_data.current_or_sync()
            self.assertEqual(delivery_data.query_records(carrier="AMZ", status="Unscheduled")["total"], 1)
            self.assertEqual(delivery_data.detail("NO-ID")["rawStatus"], "Completed")

    def test_amazon_ready_for_receive_overrides_ow_completed_and_filters_as_scheduled(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            row = {"Order no": "655347", "Delivery method": "AMA Standard", "Tracking No": "UK4958383629", "Status": "Completed"}
            delivery_data.archive([row])
            delivery_data.archive_amazon_shipping([{"trackingId": row["Tracking No"], "status": "READY_FOR_RECEIVE"}])
            delivery_data.archive([row])
            with patch.object(delivery_data, "_statuses_refreshed", False), patch.object(delivery_data, "sync", return_value={}):
                delivery_data.current_or_sync()
            result = delivery_data.query_records(search=row["Tracking No"], status="Scheduled")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["deliveries"][0]["statusSource"], "Amazon Shipping")
            self.assertEqual(result["deliveries"][0]["amazonStatus"], "READY_FOR_RECEIVE")
            self.assertEqual(delivery_data.summary()["statuses"]["Scheduled"], 1)
            self.assertEqual(delivery_data.query_records(status="Delivered")["total"], 0)

    def test_amazon_undeliverable_drives_failed_list_counts_and_survives_ow_refresh(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            row = {"Order no": "FAILED-AMZ", "Delivery method": "AMA Letter", "Tracking No": "UK1234567890", "Status": "Completed"}
            delivery_data.archive([row])
            delivery_data.archive_amazon_shipping([{"trackingId": row["Tracking No"], "status": "UNDELIVERABLE"}])
            delivery_data.archive([row])
            with patch.object(delivery_data, "_statuses_refreshed", False), patch.object(delivery_data, "sync", return_value={}):
                delivery_data.current_or_sync()
            result = delivery_data.query_records(carrier="AMZ", status="Failed", issue_cases=True)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["deliveries"][0]["statusSource"], "Amazon Shipping")
            self.assertEqual(result["deliveries"][0]["amazonStatus"], "UNDELIVERABLE")
            summary = delivery_data.summary()
            self.assertEqual(summary["failedTotal"], 1)
            self.assertEqual(summary["failedCarriers"]["AMZ"], 1)
            self.assertEqual(delivery_data.query_records(status="Delivered")["total"], 0)

    def test_amazon_lost_overrides_ow_and_remains_filterable_after_refresh(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            row = {"Order no": "LOST-ORDER", "Delivery method": "AMA XL", "Tracking No": "UK1234567890", "Status": "Completed"}
            delivery_data.archive([row])
            delivery_data.archive_amazon_shipping([{"trackingId": row["Tracking No"], "status": "LOST"}])
            delivery_data.archive([row])
            with patch.object(delivery_data, "_statuses_refreshed", False), patch.object(delivery_data, "sync", return_value={}):
                delivery_data.current_or_sync()
            result = delivery_data.query_records(carrier="AMZ", status="Lost")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["deliveries"][0]["statusSource"], "Amazon Shipping")
            self.assertEqual(delivery_data.summary()["statuses"]["Lost"], 1)
            self.assertEqual(delivery_data.query_records(status="Delivered")["total"], 0)

    def test_amazon_schedule_uses_uk_time_and_product_sku_from_ow(self):
        self.assertEqual(delivery_data.amazon_scheduled_time("13/10/2026 19:00 (UTC)"), "2026-10-13T20:00:00+01:00")
        self.assertEqual(delivery_data.amazon_scheduled_time("13/12/2026 19:00 (UTC)"), "2026-12-13T19:00:00+00:00")
        self.assertEqual(delivery_data.amazon_scheduled_time("13/10/2026 23:30 (UTC)"), "2026-10-14T00:30:00+01:00")
        self.assertEqual(delivery_data.amazon_scheduled_time("invalid"), "")
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            row = {"Order no": "648771", "Delivery method": "AMA Standard", "Tracking No": "UK4954910337", "Status": "Completed", "Product SKU": "CS02SQBM"}
            delivery_data.archive([row])
            delivery_data.archive_amazon_shipping([{"trackingId": "UK4954910337", "status": "IN_TRANSIT", "scheduledAt": "13/10/2026 19:00 (UTC)"}])
            delivery_data.archive([row])
            saved = delivery_data.detail("648771")
            self.assertEqual(saved["skuItems"], "CS02SQBM")
            self.assertEqual(saved["date"], "2026-10-13")
            self.assertEqual(saved["amazonScheduledAt"], "2026-10-13T20:00:00+01:00")
            self.assertEqual(delivery_data.query_records(carrier="AMZ", scheduled_from="2026-10-13", scheduled_to="2026-10-13")["total"], 1)
            delivery_data.archive_amazon_shipping([])
            self.assertEqual(delivery_data.detail("648771")["date"], "")
        self.assertEqual(delivery_data.row_sku_items({"Parent SKU": "PARENT", "Product SKU": "PRODUCT"}), "PARENT")

    def test_uk4954910337_in_transit_overrides_ow_completed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            delivery_data.archive([{"Order no": "648771", "Delivery method": "AMA Standard", "Tracking No": "UK4954910337", "Status": "Completed"}])
            delivery_data.archive_amazon_shipping([{"trackingId": "UK4954910337", "status": "IN_TRANSIT"}])
            result = delivery_data.query_records(search="UK4954910337", status="Scheduled")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["deliveries"][0]["statusSource"], "Amazon Shipping")
            self.assertEqual(delivery_data.query_records(search="UK4954910337", status="Delivered")["total"], 0)

    def test_amazon_sheet_status_overrides_ow_and_drives_filters_for_all_sizes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            rows = [
                {"Order no": str(i), "Delivery method": method, "Tracking No": f"UK{i:010d}", "Status": "C"}
                for i, method in enumerate(["AMA Large", "AMA Letter", "AMA XL", "Amazon Shipping One-Day Tracked", "XDP"], 1)
            ]
            delivery_data.archive(rows)
            shipping = [
                {"trackingId": "uk0000000001", "status": "OUT_FOR_DELIVERY"},
                {"trackingId": "UK0000000002", "status": "IN_TRANSIT"},
                {"trackingId": "UK0000000003", "status": "DELIVERED"},
                {"trackingId": "UK0000000005", "status": "IN_TRANSIT"},
            ]
            self.assertEqual(delivery_data.archive_amazon_shipping(shipping), 3)
            delivery_data.archive(rows)  # OW refresh must not temporarily overwrite a matched status.
            saved = {item["order"]: item for item in delivery_data.snapshot()}
            self.assertEqual([saved[str(i)]["st"] for i in range(1, 6)], ["Out for Delivery", "Scheduled", "Delivered", "Delivered", "Delivered"])
            self.assertEqual(saved["1"]["statusSource"], "Amazon Shipping")
            self.assertEqual(saved["4"]["statusSource"], "OW")
            self.assertEqual(saved["5"]["statusSource"], "OW")
            self.assertEqual(delivery_data.query_records(carrier="AMZ", status="Scheduled")["total"], 1)
            self.assertEqual(delivery_data.summary()["statuses"]["Out for Delivery"], 1)
            with patch.object(delivery_data, "_statuses_refreshed", False), patch.object(delivery_data, "sync", return_value={}):
                delivery_data.current_or_sync()
            self.assertEqual(delivery_data.query_records(carrier="AMZ", status="Scheduled")["total"], 1)
            delivery_data.archive_amazon_shipping([])  # Missing rows return to OW.
            self.assertEqual(delivery_data.query_records(carrier="AMZ", status="Delivered")["total"], 4)
            self.assertNotIn("amazonStatus", delivery_data.detail("1"))

    def test_amazon_changed_tracking_and_unknown_or_conflicting_status_use_ow(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            row = {"Order no": "1", "Delivery method": "AMA Standard", "Tracking No": "UK1111111111", "Status": "C"}
            delivery_data.archive([row])
            delivery_data.archive_amazon_shipping([{"trackingId": row["Tracking No"], "status": "IN_TRANSIT"}])
            row["Tracking No"] = "UK2222222222"
            delivery_data.archive([row])
            self.assertEqual(delivery_data.detail("1")["statusSource"], "OW")
            for statuses in (["UNKNOWN"], ["IN_TRANSIT", "DELIVERED"]):
                delivery_data.archive_amazon_shipping([{"trackingId": row["Tracking No"], "status": status} for status in statuses])
                self.assertEqual(delivery_data.detail("1")["st"], "Delivered")
                self.assertEqual(delivery_data.detail("1")["statusSource"], "OW")

    def test_saved_hold_orders_migrate_and_filter_without_live_sheet(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
            patch.object(delivery_data, "_statuses_refreshed", False),
            patch.object(delivery_data, "sync", side_effect=RuntimeError("Offline")),
        ):
            delivery_data.archive([
                {"Order no": "HOLD-1", "Delivery method": "ON HOLD - TBC", "Status": "C"},
                {"Order no": "CANCEL-1", "Delivery method": "TO BE CANCELLED", "Status": "C"},
            ])
            with delivery_data.connect() as db:
                db.execute(
                    "UPDATE deliveries SET payload=json_set(payload, '$.carrier', 'Unassigned', '$.st', 'Unscheduled') WHERE order_id='HOLD-1'"
                )
                db.commit()
            delivery_data.current_or_sync()
            held = delivery_data.query_records(carrier="On Hold", status="Unassigned")
            self.assertEqual(held["total"], 1)
            self.assertEqual(held["deliveries"][0]["rawStatus"], "C")
            self.assertEqual(delivery_data.query_records(carrier="Unassigned")["total"], 0)
            self.assertEqual(delivery_data.query_records(issue_cases=True)["total"], 0)
            self.assertEqual(delivery_data.summary()["carriers"]["On Hold"], 1)

    def test_ow_completion_status_aliases_are_all_accepted(self):
        for status in ("Delivered", "Complete", "Completed", "C"):
            with self.subTest(status=status):
                self.assertEqual(delivery_data.ow_status_name(status), "Delivered")

    def test_completed_ow_order_and_parent_sku_reach_table_fields(self):
        for header in ("Parent SKU", "Parent sku", "Parent_SKU", "Parent SKUs"):
            with self.subTest(header=header):
                delivery = delivery_data.row_to_delivery({
                    "Order no": "653756", "Delivery method": "AMA Standard",
                    "Tracking No": "UK1234567890",
                    "Status": "Completed", header: "ITEM-123",
                })
                self.assertEqual(delivery["st"], "Delivered")
                self.assertEqual(delivery["skuItems"], "ITEM-123")

    def test_all_ow_delivery_methods_are_grouped_and_retained(self):
        groups = {
            "AMZ": ["AMA Large", "AMA Letter", "AMA Medium", "AMA Standard", "AMA XL", "Amazon Shipping One-Day Tracked"],
            "Own van": ["Next Day Van Delivery", "Standard Van Delivery"],
            "Palletways": ["Next Day (Pallet)", "Palletways", "Palletways BQ", "Palletways Next Day"],
            "Self Delivery": ["Self Delivery", "Self Delivery BQ"],
            "Stopstart": ["STOPSTART", "Stopstart BQ"],
            "XDP": ["XDP", "XDP (Next Day)", "XDP BQ"],
            "Yodel": ["Yodel - XPECT 48 XL POD", "Yodel - XPECT MON - SAT 24", "Yodel - XPRESS MINI 48 NON POD"],
            "Charge Pending (Remote Postcode)": ["Charge Pending (Remote Postcode)"],
            "Collect in Person": ["Collect in Person"],
            "Do Not Pick Yet": ["Do Not Pick Yet"],
            "LOCAL MULTIDROP": ["LOCAL MULTIDROP"],
            "On Hold": ["ON HOLD - TBC"],
            "Cancelled": ["TO BE CANCELLED"],
            "UK Next Day": ["UK Next Day Delivery"],
            "Wayfair": ["Wayfair UPS"],
        }
        self.assertEqual(sum(map(len, groups.values())), 30)
        for expected, methods in groups.items():
            for method in methods:
                with self.subTest(method=method):
                    delivery = delivery_data.row_to_delivery(
                        {"Order no": "123", "Delivery method": method, "Status": "S"}
                    )
                    self.assertEqual(delivery["carrier"], expected)
                    self.assertEqual(delivery["deliveryMethodRaw"], method)
        self.assertEqual(delivery_data.delivery_status("S", "ON HOLD - TBC"), "Unassigned")
        self.assertEqual(delivery_data.delivery_status("S", "TO BE CANCELLED"), "Cancelled")

    def test_combined_van_and_self_delivery_filter_preserves_paging_and_failed_scope(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive([
                {"Order no": "101", "Delivery method": "Own van", "Status": "Failed Delivery"},
                {"Order no": "102", "Delivery method": "Self Delivery", "Status": "Failed Delivery"},
                {"Order no": "103", "Delivery method": "Self Delivery BQ", "Status": "Delivered"},
                {"Order no": "104", "Delivery method": "Palletways", "Status": "Failed Delivery"},
                {"Order no": "105", "Delivery method": "LOCAL MULTIDROP", "Status": "Failed Delivery"},
            ])
            first = delivery_data.query_records(carrier="Own van / Self Delivery", limit=2)
            second = delivery_data.query_records(carrier="Own van / Self Delivery", limit=2, offset=2)
            self.assertEqual(first["total"], 3)
            self.assertTrue(first["hasMore"])
            self.assertFalse(second["hasMore"])
            self.assertEqual(
                {item["order"] for item in first["deliveries"] + second["deliveries"]},
                {"101", "102", "103"},
            )
            failed = delivery_data.query_records(carrier="Own van / Self Delivery", issue_cases=True)
            self.assertEqual(failed["total"], 2)
            self.assertEqual({item["order"] for item in failed["deliveries"]}, {"101", "102"})
            self.assertEqual(delivery_data.query_records(carrier="Own van")["total"], 1)
            self.assertEqual(delivery_data.query_records(carrier="Self Delivery")["total"], 2)

    def test_delivery_classifications_are_scoped_to_courier_and_paged_on_server(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive([
                {"Order no": "101", "Delivery method": "XDP", "Status": "Scheduled"},
                {"Order no": "102", "Delivery method": "XDP (Next Day)", "Status": "Scheduled"},
                {"Order no": "103", "Delivery method": "XDP BQ", "Status": "Scheduled"},
                {"Order no": "104", "Delivery method": "XDP BQ", "Status": "Failed Delivery"},
                {"Order no": "105", "Delivery method": "AMA Letter", "Status": "Scheduled"},
                {"Order no": "106", "Delivery method": "Amazon Shipping One-Day Tracked", "Status": "Scheduled"},
            ])
            first = delivery_data.query_records(carrier="XDP", classification="XDP BQ", limit=1)
            second = delivery_data.query_records(carrier="XDP", classification="XDP BQ", limit=1, offset=1)
            self.assertEqual(first["total"], 2)
            self.assertTrue(first["hasMore"])
            self.assertFalse(second["hasMore"])
            self.assertEqual(
                {item["order"] for item in first["deliveries"] + second["deliveries"]},
                {"103", "104"},
            )
            self.assertEqual(delivery_data.query_records(carrier="XDP", classification="AMA Letter")["total"], 0)
            self.assertEqual(delivery_data.query_records(carrier="XDP")["total"], 4)
            self.assertEqual(delivery_data.query_records(carrier="XDP", classification="XDP BQ", status="Scheduled")["total"], 1)
            methods = delivery_data.summary()["deliveryMethodClassifications"]
            self.assertEqual(set(methods["XDP"]), {"XDP", "XDP (Next Day)", "XDP BQ"})
            self.assertEqual(set(methods["AMZ"]), {"AMA Letter", "Amazon Shipping One-Day Tracked"})

            http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(delivery_data, "cached_or_schedule_sync", return_value={}):
                    with urlopen(f"http://127.0.0.1:{http.server_port}/api/deliveries?carrier=XDP&delivery_method=XDP%20BQ&limit=1") as response:
                        result = json.load(response)
                    self.assertEqual(result["total"], 2)
                    self.assertEqual(result["deliveries"][0]["deliveryMethodRaw"], "XDP BQ")
            finally:
                http.shutdown()
                http.server_close()
                thread.join(timeout=2)

    def test_ow_long_date_and_optimo_status(self):
        self.assertEqual(
            delivery_data.date_value("Wednesday, 7 October, 2026 3:21:08 AM"), "2026-10-07"
        )
        ow = delivery_data.row_to_delivery(
            {
                "Order no": "101",
                "Delivery method": "Palletways",
                "Order date": "2026-10-06T20:21:08+01:00",
                "Tracking No": "OW123",
                "Status": "W",
            }
        )
        self.assertEqual(ow["orderDateTime"], "2026-10-06T20:21:08+01:00")
        self.assertEqual(ow["owTrackingNo"], "OW123")
        self.assertEqual(delivery_data.optimoroute_status_name("scheduled"), "Out for Delivery")
        planned = server.normalize({"data": {}, "scheduleInformation": {"driverName": "Driver"}})
        self.assertEqual(delivery_data.optimoroute_status_name(planned["status"]), "Out for Delivery")
        self.assertEqual(delivery_data.optimoroute_status_name("success"), "Delivered")
        self.assertEqual(delivery_data.optimoroute_status_name("on_route"), "Out for Delivery")
        self.assertEqual(delivery_data.optimoroute_status_name("failed"), "Failed")
        self.assertEqual(delivery_data.palletways_status_name("DELETED"), "Rejected")
        self.assertEqual(delivery_data.ow_status_name("X"), "Cancelled")
        for code in ("W", "K", "H", "I", "A", "U", "Y"):
            self.assertEqual(delivery_data.ow_status_name(code), "Unscheduled")
        for code in ("P", "S"):
            self.assertEqual(delivery_data.ow_status_name(code), "Scheduled")
        self.assertEqual(delivery_data.ow_status_name("C"), "Delivered")
        self.assertEqual(
            delivery_data.palletways_status_name("OUT FOR DELIVERY"), "Out for Delivery"
        )

    def test_ow_cancelled_order_is_not_a_failed_delivery(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "101", "Delivery method": "Own van", "Status": "X"}]
            )
            self.assertEqual(delivery_data.snapshot()[0]["st"], "Cancelled")
            self.assertEqual(delivery_data.query_records(issue_cases=True)["total"], 0)
            self.assertEqual(delivery_data.summary()["failedTotal"], 0)

    def test_xdp_fallback_is_awaiting_instead_of_ow_status(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "102", "Delivery method": "XDP", "Status": "S"}]
            )
            delivery = delivery_data.snapshot()[0]
            self.assertEqual((delivery["st"], delivery["statusSource"]), ("Awaiting", "XDP fallback"))
            self.assertEqual(delivery["rawStatus"], "S")

    def test_status_source_uses_carrier_when_mapped_and_ow_otherwise(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {
                        "Order no": "1",
                        "Order reference": "V-1",
                        "Delivery method": "Own van",
                        "Status": "W",
                    },
                    {"Order no": "2", "Delivery method": "Palletways", "Status": "I"},
                ]
            )
            delivery_data.archive_palletways([{"Customer Ref": "2", "Status": "DEPARTED HUB"}])
            records = {item["order"]: item for item in delivery_data.snapshot()}
            self.assertEqual(
                (records["1"]["st"], records["1"]["statusSource"]), ("Unscheduled", "OW")
            )
            self.assertEqual(
                (records["2"]["st"], records["2"]["statusSource"]), ("Scheduled", "Palletways")
            )
            delivery_data.archive(
                [{"Order no": "2", "Delivery method": "Palletways", "Status": "C"}]
            )
            saved = delivery_data.snapshot()[0]
            self.assertEqual((saved["st"], saved["statusSource"]), ("Scheduled", "Palletways"))

    def test_optimoroute_details_and_pod_note_survive_ow_refresh(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            row = {
                "Order no": "101",
                "Order reference": "REF-101",
                "Delivery method": "Own van",
                "Status": "W",
            }
            delivery_data.archive([row])
            with delivery_data.connect() as db:
                saved = json.loads(
                    db.execute("SELECT payload FROM deliveries WHERE order_id='101'").fetchone()[0]
                )
                delivery_data.apply_optimoroute_fields(
                    saved,
                    {
                        "id": "opt-101",
                        "providerOrderNo": "REF-101",
                        "customer": "Destination",
                        "address": "1 High Street",
                        "latitude": 51.5,
                        "longitude": -0.1,
                        "orderType": "D",
                        "driver": "Alex",
                        "stopNumber": 4,
                        "scheduledAt": "2026-10-08T09:00:00",
                        "completedAt": {
                            "unixTimestamp": 1791450000,
                            "localTime": "2026-10-08T10:00:00",
                        },
                        "completionPosition": {"latitude": 51.5001, "longitude": -0.1002},
                        "podNote": "Left with reception",
                        "photos": [{"url": "https://example.com/pod.jpg"}],
                    },
                )
                db.execute(
                    "UPDATE deliveries SET payload=? WHERE order_id='101'", (json.dumps(saved),)
                )
                db.commit()
            delivery_data.archive([row])
            refreshed = delivery_data.snapshot()[0]
            self.assertEqual(refreshed["providerPodNote"], "Left with reception")
            self.assertEqual(refreshed["providerCompletionPosition"]["latitude"], 51.5001)
            self.assertEqual(refreshed["providerScheduledAt"], "2026-10-08T09:00:00")
            self.assertEqual(refreshed["podPhotos"][0]["url"], "https://example.com/pod.jpg")

    def test_live_palletways_columns_match_ow_customer_ref(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "651709", "Delivery method": "Palletways", "Status": "C"}]
            )
            matched = delivery_data.archive_palletways(
                [
                    {
                        "Customer Ref": "651709",
                        "Tracking ID": "60050902387",
                        "Status": "JOB COMPLETE",
                        "Due Date": "07/10/2026",
                        "Date Completed": "07/10/2026 - 09:35",
                        "Date Entered": "06/10/2026",
                        "Consignment Number": "3178353-41",
                        "Type": "D",
                        "Delivery Address": "Example House, AB1 2CD",
                        "Col Postcode": "DY9 7DF",
                        "Del Postcode": "AB1 2CD",
                        "Del Service": "NEXT DAY BY 1700 (PREMIUM)",
                    }
                ]
            )
            self.assertEqual(matched, 1)
            delivery = delivery_data.snapshot()[0]
            self.assertEqual(delivery["st"], "Delivered")
            self.assertEqual(delivery["trk"], "60050902387")
            self.assertEqual(
                delivery["trackingUrl"], "https://track2.palletways.com/?dc_syscon=60050902387"
            )
            self.assertEqual(delivery["date"], "2026-10-07")
            self.assertEqual(delivery["completedAt"], "2026-10-07T09:35:00")
            self.assertEqual(delivery["palletwaysDetails"]["consignmentNumber"], "3178353-41")
            self.assertEqual(delivery["palletwaysDetails"]["deliveryPostcode"], "AB1 2CD")
            self.assertEqual(
                delivery["palletwaysDetails"]["deliveryService"], "NEXT DAY BY 1700 (PREMIUM)"
            )
            self.assertNotIn("billingUnits", delivery["palletwaysDetails"])
            delivery_data.archive(
                [{"Order no": "651709", "Delivery method": "Palletways", "Status": "C"}]
            )
            self.assertEqual(
                delivery_data.snapshot()[0]["palletwaysDetails"]["consignmentNumber"], "3178353-41"
            )

    def test_verified_palletways_tracking_corrects_stale_sheet(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "651768", "Delivery method": "Palletways", "Status": "C"}]
            )
            delivery_data.archive_palletways(
                [{"Customer Ref": "651768", "Tracking ID": "60050910409", "Status": "DEPARTED HUB"}]
            )
            delivery = delivery_data.snapshot()[0]
            self.assertEqual(delivery["date"], "2026-10-07")
            self.assertEqual(delivery["palletwaysDetails"]["dueAt"], "2026-10-07T17:00:00")
            self.assertEqual(delivery["completedAt"], "2026-10-08T08:26:00")
            self.assertEqual(delivery["st"], "Delivered")

    def test_palletways_tracking_link_requires_official_id_format(self):
        self.assertEqual(
            delivery_data.palletways_tracking_url("60050873030"),
            "https://track2.palletways.com/?dc_syscon=60050873030",
        )
        self.assertEqual(delivery_data.palletways_tracking_url("not-a-tracking-id"), "")

    def test_missing_palletways_match_does_not_mean_unscheduled(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "652198", "Delivery method": "Palletways", "Status": "W"}]
            )
            delivery_data.archive_palletways([])
            delivery = delivery_data.snapshot()[0]
            self.assertEqual(delivery["rawStatus"], "W")
            self.assertEqual(delivery["palletwaysLookup"], "not_found")
            self.assertEqual(delivery["st"], "Unscheduled")
            delivery_data.archive(
                [{"Order no": "652198", "Delivery method": "Palletways", "Status": "W"}]
            )
            self.assertEqual(delivery_data.snapshot()[0]["st"], "Unscheduled")

    def test_booking_status_comes_only_from_unique_routine_order(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {"Order no": "101", "Delivery method": "Palletways", "Status": "W"},
                    {"Order no": "102", "Delivery method": "Own van", "Status": "C"},
                ]
            )
            self.assertEqual(
                delivery_data.archive_routine_dashboard(
                    [
                        {"Order ID": "101", "Status": datetime(2026, 10, 9)},
                        {"Order ID": "102", "Status": "OnHold"},
                        {"Order ID": "102", "Status": "Open"},
                        {"Order ID": "101, 102", "Status": "ASAP"},
                    ]
                ),
                1,
            )
            statuses = {
                item["order"]: item.get("bookingStatus") for item in delivery_data.snapshot()
            }
            self.assertEqual(statuses, {"101": "09/10/2026", "102": None})
            delivery_data.archive(
                [{"Order no": "101", "Delivery method": "Palletways", "Status": "W"}]
            )
            self.assertEqual(
                next(item for item in delivery_data.snapshot() if item["order"] == "101")[
                    "bookingStatus"
                ],
                "09/10/2026",
            )

    def test_routine_dates_and_out_of_stock_codes(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {"Order no": "101", "Delivery method": "Own van"},
                    {"Order no": "102", "Delivery method": "Palletways"},
                ]
            )
            delivery_data.archive_routine_dashboard(
                [
                    {"Order ID": "101", "Status": datetime(2026, 10, 10)},
                    {"Order ID": "102", "Status": "o/s"},
                ]
            )
            self.assertEqual(
                {item["order"]: item["bookingStatus"] for item in delivery_data.snapshot()},
                {"101": "10/10/2026", "102": "Out of Stock"},
            )

    def test_routine_composite_order_ids_and_other_statuses(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {"Order no": "651825", "Delivery method": "Own van"},
                    {"Order no": "646871", "Delivery method": "Own van"},
                    {"Order no": "643159", "Delivery method": "Own van"},
                ]
            )
            matched = delivery_data.archive_routine_dashboard(
                [
                    {"Order ID": "651825 - 59768", "Status": "Del Thurs"},
                    {"Order ID": "CN643159/646871", "Status": datetime(2026, 10, 8)},
                ]
            )
            statuses = {
                item["order"]: item.get("bookingStatus")
                for item in delivery_data.snapshot()
            }
            self.assertEqual(matched, 3)
            self.assertEqual(
                statuses,
                {"651825": "Del Thurs", "643159": "08/10/2026", "646871": "08/10/2026"},
            )

    def test_ow_status_is_display_fallback(self):
        delivery = delivery_data.row_to_delivery(
            {
                "Order no": "102",
                "Delivery method": "Palletways",
                "Status": "C",
                "Tracking No": "PW456",
            }
        )
        self.assertEqual(delivery["st"], "Delivered")
        self.assertEqual(delivery["statusSource"], "OW")
        self.assertEqual(delivery["rawStatus"], "C")

    def test_ow_is_primary_and_palletways_followups_join_by_order_number(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            row = {
                "Order no": "651124",
                "Order date": "07/10/2026",
                "Delivery name": "Alex Smith",
                "Delivery telephone": "07700 900123",
                "Delivery postcode": "RG1 2AB",
                "Delivery method": "Palletways",
                "Status": "Scheduled",
                "Tracking No": "PW123",
            }
            self.assertEqual(delivery_data.archive([row], "2026-10-07T08:00:00+00:00"), 1)
            self.assertEqual(
                delivery_data.archive_palletways(
                    [
                        {
                            "Order number": "651124",
                            "Dispatch Date": "08/10/2026",
                            "Follow up": "Customer called",
                            "Follow up_2": "Depot contacted",
                        }
                    ],
                    "2026-10-08T09:00:00+00:00",
                ),
                1,
            )
            delivery = delivery_data.snapshot()[0]
            self.assertEqual(delivery["cust"], "Alex Smith")
            self.assertEqual(delivery["phone"], "07700 900123")
            self.assertEqual(delivery["dispatchDate"], "2026-10-08")
            self.assertEqual(len(delivery["logs"]), 3)
            self.assertEqual(delivery["st"], "Scheduled")
            delivery_data.archive([], "2026-10-09T08:00:00+00:00")
            self.assertEqual(len(delivery_data.snapshot()), 1)

    def test_unrelated_or_unsupported_rows_do_not_join(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive([{"Order no": "101", "Delivery method": "Standard Van Delivery"}])
            self.assertEqual(
                delivery_data.archive_palletways(
                    [{"Order number": "101", "Status": "Failed Delivery"}]
                ),
                0,
            )
            self.assertEqual(delivery_data.snapshot()[0]["st"], "Unscheduled")

    def test_ow_status_never_overrides_carrier_status(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {
                        "Order no": "101",
                        "Order reference": "V-101",
                        "Delivery method": "Own van",
                        "Status": "Delivered",
                    },
                    {
                        "Order no": "102",
                        "Delivery method": "Palletways",
                        "Status": "Failed Delivery",
                    },
                    {"Order no": "103", "Delivery method": "XDP", "Status": "Delivered"},
                ]
            )
            self.assertEqual(
                {item["st"] for item in delivery_data.snapshot()},
                {"Delivered", "Failed", "Delivered"},
            )
            delivery_data.archive_palletways(
                [
                    {
                        "Customer Ref": "102",
                        "Status": "JOB COMPLETE",
                        "Date Completed": "08/10/2026 - 10:15",
                    }
                ]
            )
            with delivery_data.connect() as db:
                row = db.execute(
                    "SELECT payload FROM deliveries WHERE order_id=?", ("101",)
                ).fetchone()
                saved = json.loads(row["payload"])
                saved["providerStatus"] = "scheduled"
                db.execute(
                    "UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(saved), "101")
                )
                db.commit()
            delivery_data.archive(
                [
                    {
                        "Order no": "101",
                        "Order reference": "V-101",
                        "Delivery method": "Own van",
                        "Status": "Failed Delivery",
                    },
                    {"Order no": "102", "Delivery method": "Palletways", "Status": "Scheduled"},
                    {"Order no": "103", "Delivery method": "XDP", "Status": "Scheduled"},
                ]
            )
            statuses = {item["order"]: item["st"] for item in delivery_data.snapshot()}
            self.assertEqual(statuses, {"101": "Scheduled", "102": "Delivered", "103": "Scheduled"})

    def test_visible_old_own_van_order_gets_optimo_status(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {
                        "Order no": "101",
                        "Order reference": "V-101",
                        "Delivery method": "Own van",
                        "Status": "C",
                    }
                ]
            )

            def fake_api(method, body):
                if method == "search_orders":
                    return {
                        "orders": [
                            {"id": "opt-1", "data": {"orderNo": "V-101", "date": "2026-10-01"}}
                        ]
                    }
                return {"orders": [{"id": "opt-1", "data": {"status": "success"}}]}

            with patch.object(server, "api", side_effect=fake_api) as provider:
                first = delivery_data.query_records(limit=25, refresh_provider=True)
                second = delivery_data.query_records(limit=25, refresh_provider=True)
            self.assertEqual(first["deliveries"][0]["st"], "Delivered")
            self.assertEqual(first["deliveries"][0]["statusSource"], "OptimoRoute")
            self.assertFalse(first["providerUnavailable"])
            self.assertEqual(provider.call_count, 2)
            self.assertEqual(second["deliveries"][0]["st"], "Delivered")

    def test_confirmed_missing_optimo_order_is_unscheduled(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            row = {
                "Order no": "101",
                "Order reference": "V-101",
                "Delivery method": "Own van",
                "Status": "Delivered",
            }
            delivery_data.archive([row])
            with patch.object(server, "api", return_value={"orders": []}):
                result = delivery_data.query_records(refresh_provider=True)
            self.assertEqual(result["deliveries"][0]["st"], "Delivered")
            self.assertEqual(result["deliveries"][0]["statusSource"], "OW")
            self.assertEqual(result["deliveries"][0]["providerLookup"], "not_found")
            delivery_data.archive([{**row, "Status": "C"}])
            self.assertEqual(delivery_data.snapshot()[0]["st"], "Delivered")

    def test_status_filter_rechecks_after_optimoroute_updates_a_row(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {
                        "Order no": "101",
                        "Order reference": "V-101",
                        "Delivery method": "Own van",
                        "Status": "W",
                    }
                ]
            )

            def fake_api(method, body):
                if method == "search_orders":
                    return {
                        "orders": [
                            {"id": "opt-1", "data": {"orderNo": "V-101", "date": "2026-10-08"}}
                        ]
                    }
                return {"orders": [{"id": "opt-1", "data": {"status": "scheduled"}}]}

            with patch.object(server, "api", side_effect=fake_api):
                unscheduled = delivery_data.query_records(
                    status="Unscheduled", refresh_provider=True
                )

            self.assertEqual(unscheduled["total"], 0)
            self.assertEqual(unscheduled["deliveries"], [])
            scheduled = delivery_data.query_records(status="Scheduled")
            self.assertEqual(scheduled["total"], 0)
            out_for_delivery = delivery_data.query_records(status="Out for Delivery")
            self.assertEqual([item["order"] for item in out_for_delivery["deliveries"]], ["101"])
            self.assertEqual(delivery_data.summary()["statuses"]["Out for Delivery"], 1)
            delivery_data.archive([{"Order no": "101", "Order reference": "V-101",
                                    "Delivery method": "Own van", "Status": "W"}])
            self.assertEqual(delivery_data.snapshot()[0]["st"], "Out for Delivery")

    def test_detail_preserves_every_pod_photo_and_signature(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [{"Order no": "101", "Order reference": "V-101", "Delivery method": "Own van"}]
            )

            def fake_api(method, body):
                if method == "search_orders":
                    return {"orders": [{"id": "opt-1", "data": {"orderNo": "V-101"}}]}
                return {
                    "orders": [
                        {
                            "id": "opt-1",
                            "data": {
                                "status": "success",
                                "form": {
                                    "images": [
                                        {"url": "https://example.com/1.jpg"},
                                        {"url": "https://example.com/2.jpg"},
                                    ],
                                    "signature": {"url": "https://example.com/signature.png"},
                                },
                            },
                        }
                    ]
                }

            with (
                patch.object(server, "api", side_effect=fake_api),
                patch("activity_log.archive_records"),
            ):
                delivery = delivery_data.detail("101")
            self.assertEqual(
                [item["url"] for item in delivery["podPhotos"]],
                [
                    "https://example.com/1.jpg",
                    "https://example.com/2.jpg",
                    "https://example.com/signature.png",
                ],
            )
            self.assertEqual(delivery["podUrl"], "https://example.com/1.jpg")

    def test_search_covers_orders_beyond_first_page(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            rows = [
                {
                    "Order no": str(number),
                    "Delivery method": "Palletways",
                    "Delivery name": "Customer " + str(number),
                }
                for number in range(40)
            ]
            delivery_data.archive(rows)
            first = delivery_data.query_records(limit=25)
            self.assertEqual(len(first["deliveries"]), 25)
            self.assertTrue(first["hasMore"])
            self.assertEqual(first["total"], 40)
            match = delivery_data.query_records(search="Customer 3", limit=25)
            self.assertGreaterEqual(match["total"], 1)
            self.assertTrue(any(item["order"] == "3" for item in match["deliveries"]))

    def test_today_tracking_scope_uses_current_date_and_delivery_status(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {"Order no": "101", "Delivery method": "Own van", "Status": "Scheduled"},
                    {"Order no": "102", "Delivery method": "Own van", "Status": "Delivered"},
                    {"Order no": "103", "Delivery method": "Own van", "Status": "Failed Delivery"},
                    {"Order no": "104", "Delivery method": "Own van", "Status": "Scheduled"},
                ]
            )
            with delivery_data.connect() as db:
                for order in ("101", "102", "103", "104"):
                    row = db.execute(
                        "SELECT payload FROM deliveries WHERE order_id=?", (order,)
                    ).fetchone()
                    payload = json.loads(row["payload"])
                    payload["date"] = (
                        date.today() if order not in ("103", "104") else date.today() - timedelta(days=1)
                    ).isoformat()
                    db.execute(
                        "UPDATE deliveries SET payload=? WHERE order_id=?",
                        (json.dumps(payload), order),
                    )
                db.commit()

            first = delivery_data.query_records(today=True, limit=1)
            second = delivery_data.query_records(today=True, limit=1, offset=1)
            self.assertEqual(first["total"], 2)
            self.assertTrue(first["hasMore"])
            self.assertEqual(
                {item["order"] for item in first["deliveries"] + second["deliveries"]},
                {"101", "102"},
            )
            dashboard = delivery_data.summary()
            self.assertEqual(dashboard["todayTotal"], 2)
            self.assertEqual([item["order"] for item in dashboard["today"]], ["101"])
            self.assertEqual(dashboard["ongoingTodayTotal"], 1)
            self.assertEqual([item["order"] for item in dashboard["failedPreview"]], ["103"])

    def test_http_tracking_returns_25_and_searches_all_saved_orders(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {
                        "Order no": str(number),
                        "Delivery method": "Palletways",
                        "Delivery name": f"Customer {number}",
                    }
                    for number in range(40)
                ]
            )
            http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(
                    delivery_data,
                    "current_or_sync",
                    return_value={"syncedAt": "2026-10-08T00:00:00Z"},
                ):
                    base = f"http://127.0.0.1:{http.server_port}/api/deliveries"
                    with urlopen(base) as response:
                        first = json.load(response)
                    self.assertEqual(len(first["deliveries"]), 25)
                    self.assertTrue(first["hasMore"])
                    with urlopen(base + "?q=Customer%203") as response:
                        found = json.load(response)
                    self.assertTrue(any(item["order"] == "3" for item in found["deliveries"]))
            finally:
                http.shutdown()
                http.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
