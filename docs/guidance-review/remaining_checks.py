import collections,glob,openpyxl
p=glob.glob(r'C:\Users\NITRO V15\AppData\Local\Packages\sandbox.*\AC\Temp\browser-use\exports\OW Ticket Fetch*.xlsx')[-1]
w=openpyxl.load_workbook(p,read_only=True,data_only=True)
def key(v): return str(v or '').strip().removesuffix('.0')
ow={}
for r in w['Sales Activity'].iter_rows(min_row=2,values_only=True):
 if r and r[0]:ow[key(r[0])]=(str(r[9] or '').strip().upper(),str(r[19] or '').strip().upper(),key(r[18]).upper())
cancelled=[(k,v[1]) for k,v in ow.items() if v[0]=='CANCELLED']
print('OW Cancelled unique',len(cancelled),'methods',collections.Counter(m for _,m in cancelled).most_common(15))
unmapped={'DELIVERY_ATTEMPTED','REJECTED','PICKUP_CANCELLED','AWAITING_CUSTOMER_PICKUP','CARRIER_CANCELLED_PICKUP','RETURNED','RETURNED_TO_SELLER'}
by_track=collections.defaultdict(set)
for r in w['Amazon Shipping'].iter_rows(min_row=2,values_only=True):
 if r and r[1]:by_track[key(r[1]).upper()].add(str(r[6] or '').strip().upper())
affected=collections.defaultdict(set)
for k,(status,method,tracking) in ow.items():
 if method.startswith(('AMA ','AMAZON SHIPPING')):
  for raw in by_track.get(tracking,set()) & unmapped:affected[raw].add((k,status))
for raw,pairs in sorted(affected.items()):
 print(raw,'OW orders',len(pairs),'OW Completed',sum(s=='COMPLETED' for _,s in pairs),'sample',next(iter(pairs))[0])
