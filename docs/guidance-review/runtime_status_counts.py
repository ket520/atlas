import sqlite3, json

p = "file:C:/atlas/data/delivery-desk.sqlite3?mode=ro"
try:
    db = sqlite3.connect(p, uri=True)
    for carrier in ["Own van", "Self Delivery", "LOCAL MULTIDROP", "Palletways", "XDP", "AMZ"]:
        rows = db.execute(
            "SELECT json_extract(payload,'$.providerStatus'),json_extract(payload,'$.st'),count(*) FROM deliveries WHERE json_extract(payload,'$.carrier')=? GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12",
            (carrier,),
        ).fetchall()
        print(carrier, rows)
    print(
        "sources",
        db.execute(
            "SELECT json_extract(payload,'$.carrier'),json_extract(payload,'$.statusSource'),count(*) FROM deliveries WHERE json_extract(payload,'$.carrier') IN ('Own van','Palletways','XDP','AMZ') GROUP BY 1,2 ORDER BY 1,3 DESC"
        ).fetchall(),
    )
except Exception as e:
    print(type(e).__name__, str(e))
