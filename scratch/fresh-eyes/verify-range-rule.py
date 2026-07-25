import httpx, hashlib
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
def q(fd,td):
    b={"community_id":"demo-community","event_types":["resolved"],"time_type":"custom",
       "time_unit":"day","time_period":1,"timezone":"America/New_York",
       "from_date":fd,"to_date":td,"filters":[]}
    r=httpx.post(U,headers=H,json=b,timeout=60)
    try: d=r.json()
    except Exception: return None,r.status_code,r.text[:200]
    return d,r.status_code,None
cases=[
 ("overlap-left 07-05..07-12","2026-07-05T00:00:00Z","2026-07-12T00:00:00Z"),
 ("overlap-right 07-20..08-01","2026-07-20T00:00:00Z","2026-08-01T00:00:00Z"),
 ("exact window 07-10..07-24","2026-07-10T00:00:00Z","2026-07-24T00:00:00Z"),
 ("inside 07-11..07-23","2026-07-11T00:00:00Z","2026-07-23T00:00:00Z"),
 ("one day beyond 07-24..07-25","2026-07-24T00:00:00Z","2026-07-25T00:00:00Z"),
 ("zero width 07-15","2026-07-15T00:00:00Z","2026-07-15T00:00:00Z"),
 ("inverted 07-18..07-12","2026-07-18T00:00:00Z","2026-07-12T00:00:00Z"),
 ("no to_date","2026-07-15T00:00:00Z",None),
 ("mid-day from 07-15T13","2026-07-15T13:00:00Z","2026-07-17T09:00:00Z"),
]
for name,fd,td in cases:
    b_td = td
    if td is None:
        r=httpx.post(U,headers=H,json={"from_date":fd},timeout=60); d=r.json()
    else:
        d,sc,err=q(fd,td)
        if d is None: print(f"{name:30s} ERR {sc} {err}"); continue
    t=d["ticks"]
    print(f"{name:30s} nvals={len(d['resolved']):3d} first={t[0]} last={t[-1]} sum={sum(d['resolved'])}")
