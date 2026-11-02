import glob, openpyxl

p = glob.glob(
    r"C:\Users\NITRO V15\AppData\Local\Packages\sandbox.*\AC\Temp\browser-use\exports\OW Ticket Fetch*.xlsx"
)[-1]
w = openpyxl.load_workbook(p, read_only=True, data_only=True)
x = {
    str(r[0]).removesuffix(".0"): str(r[8] or "").strip()
    for r in w["XDP"].iter_rows(min_row=2, values_only=True)
    if r and r[0]
}
found = set()
for r in w["Sales Activity"].iter_rows(min_row=2, values_only=True):
    if not r or not r[0] or "xdp" not in str(r[19] or "").lower():
        continue
    k = str(r[0]).removesuffix(".0")
    if k in found or x.get(k) != "DELIVERED":
        continue
    print(k, "OW=", r[9], "XDP=", x[k], "method=", r[19])
    found.add(k)
    if len(found) >= 3:
        break
