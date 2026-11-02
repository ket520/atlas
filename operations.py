"""Read-only tracking endpoints."""

from datetime import date


def read_operation(action, params, api):
    if action == "activity":
        from activity_log import lookup

        return lookup(params.get("orderNo", [""])[0], api)
    if action == "refresh":
        ids = [item for item in params.get("ids", [""])[0].split(",") if item]
        if len(ids) > 25:
            raise ValueError("Refresh at most 25 orders.")
        if not ids:
            return {"records": []}
        from server import normalize

        orders = api(
            "search_orders",
            {
                "orders": [{"id": item} for item in ids],
                "includeOrderData": True,
                "includeScheduleInformation": True,
            },
        )
        done = api(
            "get_completion_details",
            {"orders": [{"id": item} for item in ids], "includeCustomerFeedback": True},
        )
        by_id = {item.get("id"): item for item in done["orders"]}
        records = [normalize(item, by_id.get(item.get("id"))) for item in orders["orders"]]
        from activity_log import archive_records

        archive_records(records)
        return {"records": records}
    if action == "events":
        from activity_log import sync_events

        return sync_events(api)
    if action not in {"routes", "dispatch"}:
        raise ValueError("This app supports read-only tracking endpoints.")
    day = params.get("date", [""])[0]
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("Select a valid date.")
    if action == "routes":
        return api(
            "get_routes",
            {
                "date": day,
                "includeRoutePolyline": "true",
                "includeRouteStartEnd": "true",
                "includeDispatchStatus": "true",
            },
            "GET",
        )
    return api("get_dispatch_status", {"date": day, "includeRouteChanges": "true"}, "GET")
