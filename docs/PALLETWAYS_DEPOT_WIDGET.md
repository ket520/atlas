# Palletways delivery-depot dwell widget

Select **Palletways · At Depot 3+ Days** from Customize Widgets. Restart the Python server after installation. Existing dashboard layouts are retained.

The background monitor checks up to 25 active Palletways orders per minute, oldest attempted check first, with a minimum 30-minute interval per order. It uses the configured PALLETWAYS_API_KEY and existing API request pacing. The dashboard refreshes the displayed cohort every minute while visible. Initial coverage takes multiple batches on large datasets; the widget footer reports coverage and the oldest successful check.

A confirmed arrival requires DeliveryDepot to match the depot number in a VU/SCN/700 unloading-from-trunk event. Generic “Scanned at Depot” notes are deliberately excluded until their meaning is verified. Same-stay repeated unload scans and booking notes do not reset the timer. Loading/departure, driver arrival and completion terminate the stay. A subsequent confirmed unloading event begins a new stay.

Arrival timestamps are interpreted in Europe/London and stored in UTC. The threshold is 72 elapsed hours including weekends. Results are ordered by oldest arrival first. Carrier-event time, not first observation time, starts the clock.

Missing or ambiguous evidence is excluded. API failures retain previous evidence and its successful check timestamp; the widget flags failed updates. A stored result describes the last successful carrier observation, not guaranteed real-time physical location. No tracking event codes other than the verified unloading combination establish arrival.
