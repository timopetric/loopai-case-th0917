import httpx, json, hashlib
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
def q(fd,td,unit="day",**kw):
    b={"community_id":"demo-community","event_types":["resolved"],"time_type":"custom",
       "time_unit":unit,"time_period":1,"timezone":"America/New_York",
       "from_date":fd,"to_date":td,"filters":[]}
    b.update(kw)
    r=httpx.post(U,headers=H,json=b,timeout=60)
    d=r.json()
    return d, hashlib.md5(r.content).hexdigest()
cases=[
 ("baseline 07-10..07-23","2026-07-10T05:00:00.000Z","2026-07-23T03:59:59.999Z"),
 ("1day 07-20","2026-07-20T05:00:00.000Z","2026-07-21T03:59:59.999Z"),
 ("3day 07-15..07-18","2026-07-15T00:00:00.000Z","2026-07-18T00:00:00.000Z"),
 ("2020 narrow","2020-01-01T00:00:00.000Z","2020-01-05T00:00:00.000Z"),
 ("2020 wide","2020-01-01T00:00:00.000Z","2027-01-01T00:00:00.000Z"),
 ("2030 future","2030-01-01T00:00:00.000Z","2030-01-10T00:00:00.000Z"),
 ("1990 past","1990-01-01T00:00:00.000Z","1990-01-10T00:00:00.000Z"),
 ("30day around","2026-07-01T00:00:00.000Z","2026-07-31T00:00:00.000Z"),
]
for name,fd,td in cases:
    d,h=q(fd,td)
    t=d["ticks"]
    print(f"{name:26s} hash={h[:8]} nticks={len(t):3d} nvals={len(d['resolved']):3d} first={t[0]} last={t[-1]} sum_resolved={sum(d['resolved'])}")
