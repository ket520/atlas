import collections, glob, json, re
import openpyxl

path = glob.glob(
    r"C:\Users\NITRO V15\AppData\Local\Packages\sandbox.*\AC\Temp\browser-use\exports\OW Ticket Fetch*.xlsx"
)[-1]
wb = openpyxl.load_workbook(path, read_only=True, data_only=True)


def norm(v):
    if v is None:
        return ""
    s = str(v).strip()
    return s[:-2] if re.fullmatch(r"\d+\.0", s) else s


def rows(tab, fields):
    it = wb[tab].iter_rows(values_only=True)
    headers = [norm(x) for x in next(it)]
    out = []
    for row in it:
        if not row or not norm(row[0]):
            continue
        out.append({key: norm(row[i]) if i < len(row) else "" for key, i in fields.items()})
    return out


ow = rows("Sales Activity", dict(order=0, status=9, tracking=18, method=19, ref=4))
orders = {}
for r in ow:
    orders.setdefault(r["order"], r)
groups = {
    "Amazon Shipping": (lambda x: x.lower().startswith(("ama ", "amazon shipping"))),
    "Palletways": (lambda x: "palletways" in x.lower() or x.lower() == "next day (pallet)"),
    "XDP": (lambda x: "xdp" in x.lower()),
    "STOPSTART": (lambda x: x.lower().startswith("stopstart")),
}
source = {
    "Amazon Shipping": rows("Amazon Shipping", dict(tracking=1, status=6, ref=5)),
    "Palletways": rows("Palletways", dict(order=0, tracking=1, status=5)),
    "XDP": rows("XDP", dict(order=0, tracking=3, consignment=4, status=8)),
    "STOPSTART": rows("STOPSTART", dict(order=0, status=8)),
}
results = []
for name, pred in groups.items():
    cohort = {k: r for k, r in orders.items() if pred(r["method"])}
    src = source[name]
    idx = collections.defaultdict(list)
    if name == "Amazon Shipping":
        for r in src:
            idx[r["tracking"].upper()].append(r)
        matched = {
            k: r for k, r in cohort.items() if r["tracking"].upper() in idx and r["tracking"]
        }
        no_key = sum(not r["tracking"] for r in cohort.values())
    else:
        for r in src:
            idx[r["order"]].append(r)
        matched = {k: r for k, r in cohort.items() if k in idx}
        no_key = 0
    conflicts = []
    tracking_disagree = []
    for k, r in matched.items():
        key = r["tracking"].upper() if name == "Amazon Shipping" else k
        ss = idx[key]
        if len({x["status"] for x in ss if x["status"]}) > 1:
            conflicts.append(k)
        if (
            name in ("Palletways", "XDP")
            and r["tracking"]
            and ss[0]["tracking"]
            and r["tracking"].upper() != ss[0]["tracking"].upper()
        ):
            tracking_disagree.append(k)
    results.append(
        dict(
            source=name,
            ow_orders=len(cohort),
            source_rows=len(src),
            matched_orders=len(matched),
            unmatched_orders=len(cohort) - len(matched),
            ow_missing_tracking=no_key,
            status_conflict_orders=len(conflicts),
            tracking_disagree_orders=len(tracking_disagree),
            tracking_disagree_sample=tracking_disagree[:6],
        )
    )
open("C:/atlas/docs/guidance-review/source_audit.json", "w", encoding="utf8").write(
    json.dumps(results, indent=2)
)
print(json.dumps(results, indent=2))
