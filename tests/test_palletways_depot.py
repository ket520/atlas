import unittest
from datetime import datetime, timedelta, timezone
from palletways_depot import depot_stay


class DepotStayTests(unittest.TestCase):
    def event(
        self,
        group="VU",
        kind="SCN",
        code="700",
        text="Scanned off from vehicle t2d at depot 6 trunk run",
        hours=0,
    ):
        at = datetime(2026, 10, 30, 4, 29, tzinfo=timezone.utc) + timedelta(hours=hours)
        return dict(
            group=group,
            type=kind,
            statusCode=code,
            text=text,
            date=at.date().isoformat(),
            time=at.time().isoformat(),
        )

    def test_destination_match(self):
        self.assertTrue(depot_stay({"DeliveryDepot": "6"}, [self.event()])["verified"])
        self.assertFalse(depot_stay({"DeliveryDepot": "41"}, [self.event()])["verified"])
        self.assertFalse(depot_stay({}, [self.event()])["verified"])

    def test_duplicate_and_booking_do_not_reset(self):
        first = self.event()
        events = [
            self.event(hours=24),
            self.event("BIN", "BIN", "", "Booked for delivery", 30),
            first,
        ]
        self.assertEqual(
            depot_stay({"DeliveryDepot": "6"}, events)["arrivedAt"], "2026-10-30T04:29:00+00:00"
        )

    def test_departure_and_return(self):
        departed = self.event("VL", "SCN", "800", "Scanned onto vehicle at depot 6 C&D", 4)
        self.assertFalse(depot_stay({"DeliveryDepot": "6"}, [self.event(), departed])["verified"])
        result = depot_stay({"DeliveryDepot": "6"}, [self.event(), departed, self.event(hours=10)])
        self.assertEqual(result["arrivedAt"], "2026-10-30T14:29:00+00:00")

    def test_alternate_arrivals_require_destination_evidence(self):
        generic = self.event(text="Scanned at Depot 6")
        self.assertTrue(depot_stay({"DeliveryDepot": "6"}, [generic])["verified"])
        route = self.event("JIN", "GDEP", "550", "Left hub Fradley on vehicle TRUCK[6]", -1)
        inbound = self.event("BAY", "SCN", "700", "Inbound/Receive Scan")
        repeated = self.event("BAY", "SCN", "700", "Inbound/Receive Scan", 24)
        self.assertTrue(depot_stay({"DeliveryDepot": "6"}, [route, inbound])["verified"])
        self.assertEqual(
            depot_stay({"DeliveryDepot": "6"}, [route, inbound, repeated])["arrivedAt"],
            "2026-10-30T04:29:00+00:00",
        )
        self.assertFalse(depot_stay({"DeliveryDepot": "7"}, [route, inbound])["verified"])
        self.assertFalse(depot_stay({"DeliveryDepot": "6"}, [inbound])["verified"])

    def test_only_destination_delivery_loading_closes_stay(self):
        cases = [
            ("300", "Scanned onto vehicle at depot 6 trunk run"),
            ("800", "Scanned onto vehicle at depot 41 C&D"),
            ("800", "Scanned onto vehicle C&D"),
            ("800", "Scanned onto vehicle at depot 6 trunk run"),
        ]
        for code, text in cases:
            with self.subTest(code=code, text=text):
                result = depot_stay(
                    {"DeliveryDepot": "6"},
                    [self.event(), self.event("VL", "SCN", code, text, 4)],
                )
                self.assertTrue(result["verified"])
                self.assertEqual(result["departedAt"], "")

    def test_loading_closes_before_later_delivery_confirmation(self):
        loading = self.event("VL", "SCN", "800", "Scanned onto vehicle at depot 6 C&D", 4)
        result = depot_stay({"DeliveryDepot": "6"}, [self.event(), loading])
        self.assertFalse(result["verified"])
        self.assertEqual(result["departedAt"], "2026-10-30T08:29:00+00:00")
        later = self.event("VP", "DAR", "", "Driver arrived", 8)
        completed = self.event("POD", "POD", "", "Clean POD", 9)
        result = depot_stay({"DeliveryDepot": "6"}, [self.event(), loading, later, completed])
        self.assertEqual(result["departedAt"], "2026-10-30T08:29:00+00:00")

    def test_fallback_does_not_invent_departure_time(self):
        result = depot_stay(
            {"DeliveryDepot": "6"},
            [self.event(), self.event("VP", "DAR", "", "Driver arrived", 8)],
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["departedAt"], "")

    def test_completion_and_unknown_scan(self):
        self.assertFalse(
            depot_stay(
                {"DeliveryDepot": "6"}, [self.event(), self.event("POD", "POD", "", "Clean POD", 5)]
            )["verified"]
        )
        self.assertFalse(
            depot_stay({"DeliveryDepot": "6"}, [self.event(text="Scan completed")])["verified"]
        )
        self.assertFalse(
            depot_stay({"DeliveryDepot": "6"}, [dict(self.event(), date="invalid")])["verified"]
        )


if __name__ == "__main__":
    unittest.main()
