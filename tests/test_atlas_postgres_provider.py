import io
import json
import os
import unittest
from unittest.mock import patch

import atlas_postgres_provider as provider
import delivery_data


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class AtlasPostgresProviderTests(unittest.TestCase):
    def test_nested_response_is_mapped_to_sales_activity_row_shape(self):
        payload = {"data": {"orders": [{
            "id": "db-1",
            "order": {"number": "OW-1"},
            "salesActivity": {
                "Delivery method": "Own van",
                "Delivery name": "Customer",
                "Delivery postcode": "AB1 2CD",
                "Product SKU": "SKU-1",
            },
        }]}}
        with patch.object(provider, "urlopen", return_value=Response(json.dumps(payload).encode())):
            with patch.dict(os.environ, {"STAR_PARK_API_USERNAME": "atlas-admin", "STAR_PARK_API_PASSWORD": "secret"}, clear=False):
                rows = provider.read_sales_activity()
        self.assertEqual(rows[0]["Order no"], "OW-1")
        self.assertEqual(rows[0]["Delivery method"], "Own van")
        self.assertEqual(rows[0]["Delivery postcode"], "AB1 2CD")
        self.assertEqual(rows[0]["Product SKU"], "SKU-1")
        delivery = delivery_data.row_to_delivery(rows[0])
        self.assertEqual(delivery["id"], "OW-1")
        self.assertEqual(delivery["carrier"], "Own van")
        self.assertEqual(delivery["postcode"], "AB1 2CD")

    def test_paginates_without_exposing_auth_header_to_browser(self):
        calls = []

        def fetch(request, timeout):
            calls.append((request.full_url, request.headers.get("Authorization"), timeout))
            page = "offset=0" in request.full_url
            body = {"orders": [{"orderNo": "OW-1" if page else "OW-2", "deliveryMethod": "Own van"}], "has_more": page}
            return Response(json.dumps(body).encode())

        with patch.object(provider, "urlopen", side_effect=fetch):
            with patch.dict(os.environ, {"STAR_PARK_API_USERNAME": "atlas-admin", "STAR_PARK_API_PASSWORD": "secret", "STAR_PARK_API_PAGE_SIZE": "1"}, clear=False):
                rows = provider.read_sales_activity()
        self.assertEqual([row["Order no"] for row in rows], ["OW-1", "OW-2"])
        self.assertTrue(calls[0][1].startswith("Basic "))
        self.assertTrue(calls[0][0].endswith("limit=1&offset=0"))
        self.assertEqual(calls[0][2], 20.0)

    def test_real_starpark_items_response_preserves_cells_and_offset(self):
        calls = []

        def fetch(request, timeout):
            calls.append(request.full_url)
            second_page = "offset=2" in request.full_url
            items = ([
                {"order_no": "OW-1", "line_key": "1", "occurrence": 1, "product_sku": "SKU-1",
                 "status": "W", "updated_at": "2026-11-11T10:00:00Z",
                 "cells": {"Delivery method": "Own van", "Delivery name": "One", "Custom object": {"source": "db"}}},
                {"order_no": "OW-2", "line_key": "1", "occurrence": 1, "product_sku": "SKU-2",
                 "status": "W", "updated_at": "2026-11-11T10:00:00Z",
                 "cells": {"Delivery method": "Palletways", "Delivery name": "Two"}},
            ] if not second_page else [{
                "order_no": "OW-3", "line_key": "1", "occurrence": 1, "product_sku": "SKU-3",
                "status": "C", "updated_at": "2026-11-11T10:00:00Z",
                "cells": {"Delivery method": "XDP", "Delivery name": "Three"},
            }])
            return Response(json.dumps({"items": items, "count": len(items), "has_more": not second_page,
                                        "limit": 2, "offset": 2 if second_page else 0}).encode())

        with patch.object(provider, "urlopen", side_effect=fetch):
            with patch.dict(os.environ, {"STAR_PARK_API_USERNAME": "atlas-admin", "STAR_PARK_API_PASSWORD": "secret", "STAR_PARK_API_PAGE_SIZE": "2"}, clear=False):
                rows = provider.read_sales_activity()
        self.assertEqual([row["Order no"] for row in rows], ["OW-1", "OW-2", "OW-3"])
        self.assertEqual(json.loads(rows[0]["Custom object"]), {"source": "db"})
        self.assertTrue(calls[0].endswith("limit=2&offset=0"))
        self.assertTrue(calls[1].endswith("limit=2&offset=2"))

    def test_connection_check_reads_health_and_two_orders_without_service_token(self):
        calls = []

        def fetch(request, timeout):
            calls.append(request)
            body = b'{"ok":true}' if request.full_url.endswith("/atlas/health") else b'{"orders":[{"orderNo":"OW-1","deliveryMethod":"Own van"}]}'
            return Response(body)

        with patch.object(provider, "urlopen", side_effect=fetch):
            with patch.dict(os.environ, {"STAR_PARK_API_USERNAME": "atlas-admin", "STAR_PARK_API_PASSWORD": "secret"}, clear=False):
                result = provider.connection_test()
        self.assertEqual(result["orderCount"], 1)
        self.assertNotIn("X-Atlas-Service-Token", calls[0].headers)
        self.assertNotIn("X-Atlas-Service-Token", calls[1].headers)
        self.assertTrue(calls[1].full_url.endswith("/atlas/orders?limit=2"))

    def test_postgresql_mode_uses_separate_test_cache(self):
        with patch.dict(os.environ, {"ATLAS_DELIVERY_SOURCE": "postgresql"}, clear=False):
            self.assertNotEqual(delivery_data.configured_db_path(), delivery_data.DB_PATH)

    def test_source_switch_is_explicit_and_has_no_fallback(self):
        with patch.dict(os.environ, {"ATLAS_DELIVERY_SOURCE": ""}, clear=False), patch("google_sheets.read_sales_activity", return_value=[{"source": "sheets"}]) as sheets:
            self.assertEqual(delivery_data.read_sales_activity_source(), [{"source": "sheets"}])
            sheets.assert_called_once_with()
        with patch.dict(os.environ, {"ATLAS_DELIVERY_SOURCE": "postgresql"}, clear=False), patch("atlas_postgres_provider.read_sales_activity", return_value=[{"source": "postgres"}]) as postgres:
            self.assertEqual(delivery_data.read_sales_activity_source(), [{"source": "postgres"}])
            postgres.assert_called_once_with()
        with patch.dict(os.environ, {"ATLAS_DELIVERY_SOURCE": "invalid"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "google_sheets or postgresql"):
                delivery_data.read_sales_activity_source()


if __name__ == "__main__":
    unittest.main()
