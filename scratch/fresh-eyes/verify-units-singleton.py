import httpx, statistics as st
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
d=httpx.post(U,headers=H,json={"from_date":"2026-07-10T00:00:00Z","to_date":"2026-07-23T00:00:00Z"},timeout=90).json()
def fmt(v):
    return f"{v:9.3f} | as sec={v:6.1f}s({v/60:5.1f}m) | as min={v/60:5.2f}h | as hr={v:5.2f}h"
for m in ["resolve_time","response_time","time_to_first_reply","handle_time"]:
    c=m+"_count"
    singles=[]
    for a in d["actors"]:
        for i in range(len(a[m])):
            if a[c][i]==1: singles.append(a[m][i])
    print(f"\n### {m}: {len(singles)} actor-days with _count == 1 (value = ONE ticket)")
    if singles:
        singles.sort()
        for lbl,v in [("min",singles[0]),("p25",singles[len(singles)//4]),
                      ("median",st.median(singles)),("p75",singles[3*len(singles)//4]),
                      ("max",singles[-1])]:
            print(f"   {lbl:7s} {fmt(v)}")
print("\n### Cross-check: are counts additive too? (top vs sum actors)")
for m in ["resolve_time_count","response_time_count","handle_time_count"]:
    print(f"   {m:26s} top={sum(d[m]):8d} sum_actors={sum(sum(a[m]) for a in d['actors']):8d}")
print("\n### Ordering sanity on identical denominators")
print("   ttfr_count == response_time_count ?", d["time_to_first_reply_count"]==d["response_time_count"])
r1=sum(d["time_to_first_reply"])/sum(d["time_to_first_reply_count"])
r2=sum(d["response_time"])/sum(d["response_time_count"])
r3=sum(d["resolve_time"])/sum(d["resolve_time_count"])
r4=sum(d["handle_time"])/sum(d["handle_time_count"])
print(f"   window mean ttfr={r1:.3f}  response={r2:.3f}  resolve={r3:.3f}  handle={r4:.5f}")
