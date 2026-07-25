import httpx, json
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
def q(**kw):
    b={"community_id":"demo-community","event_types":["resolved"],"time_type":"custom",
       "time_unit":"day","time_period":1,"timezone":"America/New_York",
       "from_date":"2026-07-10T00:00:00Z","to_date":"2026-07-24T00:00:00Z","filters":[]}
    b.update(kw); return httpx.post(U,headers=H,json=b,timeout=90).json()
d=q()
METRICS=[k for k,v in d.items() if isinstance(v,list) and k not in("ticks","actors","mailbox","labels","topics","categories")]
print("== RECONCILIATION over full window ==")
print(f"{'metric':45s} {'top':>14s} {'actors':>14s} {'act_res%':>9s} {'mailbox':>14s} {'mb_res%':>8s}")
for m in METRICS:
    top=sum(d[m]); a=sum(sum(x[m]) for x in d["actors"]); mb=sum(sum(x[m]) for x in d["mailbox"])
    pa=(a-top)/top*100 if top else 0.0
    pm=(mb-top)/top*100 if top else 0.0
    print(f"{m:45s} {top:14.2f} {a:14.2f} {pa:8.2f}% {mb:14.2f} {pm:7.2f}%")
print("\n== TIMEZONE effect (ticks + totals) ==")
for tz in ["America/New_York","UTC","Asia/Tokyo","Pacific/Kiritimati","Not/AZone",None]:
    r=q(timezone=tz) if tz else q()
    print(f"{str(tz):20s} first={r['ticks'][0]} n={len(r['resolved'])} sum={sum(r['resolved'])}")
