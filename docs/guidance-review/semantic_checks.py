import collections, glob, openpyxl

p = glob.glob(
    r"C:\Users\NITRO V15\AppData\Local\Packages\sandbox.*\AC\Temp\browser-use\exports\OW Ticket Fetch*.xlsx"
)[-1]
w = openpyxl.load_workbook(p, read_only=True, data_only=True)


def key(v):
    return str(v or "").strip().removesuffix(".0")


ow = {}
for r in w["Sales Activity"].iter_rows(min_row=2, values_only=True):
    if r and r[0]:
        ow[key(r[0])] = {
            "status": str(r[9] or "").strip(),
            "method": str(r[19] or "").strip(),
            "tracking": key(r[18]),
        }
for tab, status_col, carrier_test in [
    ("XDP", 8, lambda m: "xdp" in m.lower()),
    ("Palletways", 5, lambda m: "palletways" in m.lower() or m.lower() == "next day (pallet)"),
]:
    count = collections.Counter()
    examples = {}
    for r in w[tab].iter_rows(min_row=2, values_only=True):
        if not r or not r[0]:
            continue
        k = key(r[0])
        o = ow.get(k)
        if not o or not carrier_test(o["method"]) or o["status"].lower() != "completed":
            continue
        s = str(r[status_col] or "").strip().upper()
        count[s] += 1
        examples.setdefault(s, k)
    print(
        tab,
        "OW Completed paired carrier status:",
        count.most_common(18),
        "examples:",
        {k: examples[k] for k, _ in count.most_common(8)},
    )
tracking_status = collections.defaultdict(set)
for r in w["Amazon Shipping"].iter_rows(min_row=2, values_only=True):
    if r and r[1]:
        tracking_status[key(r[1]).upper()].add(str(r[6] or "").strip().upper())
count = collections.Counter()
examples = {}
for k, o in ow.items():
    if (
        not (
            o["method"].lower().startswith("ama ")
            or o["method"].lower().startswith("amazon shipping")
        )
        or o["status"].lower() != "completed"
    ):
        continue
    for s in tracking_status.get(o["tracking"].upper(), set()):
        count[s] += 1
        examples.setdefault(s, k)
print(
    "Amazon OW Completed paired carrier status:",
    count.most_common(18),
    "examples:",
    {k: examples[k] for k, _ in count.most_common(8)},
)
