# Palletways booking summary contract

Atlas requests `GET /atlas/orders?limit=100&offset=0&include=palletways_booking` from its server-side employee API client. The default orders response can remain unchanged. When the include value is present, each `palletways_shipments[]` entry should additionally carry `mapping_status` and `booking_summary`:

```json
{
  "tracking_id": "60051339718",
  "consignment_number": "1516825-41",
  "palletways_status": "Consignment Created",
  "mapping_status": "current",
  "booking_summary": {
    "booked_in": true,
    "book_in_request": false,
    "booking_date": "12/11/2026",
    "booking_time": "14:30",
    "checked_at": "2026-11-12T08:00:00Z",
    "source": "carrier"
  }
}
```

`booked_in` and `book_in_request` must each be a JSON boolean or null. They are independent facts. Missing or unverified facts are null; `DueDate` and `DueTime` must not be substituted for the appointment date/time. The API should preserve the source's date/time representation when no timezone is known. A current mapping must be distinguishable from an inactive one. Every consignment in an order needs its own summary, including shared consignments.

The Atlas client currently receives only the original five compact shipment fields. The employee API currently ignores the include parameter; the sampled order detail lacked `palletways.shipments`, and its full shipment route returned 404. Atlas therefore displays unknown booking values until the employee API provides this contract. The employee API implementation and deployment are outside this repository.
