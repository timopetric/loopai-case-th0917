import httpx, statistics as st
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
d=httpx.post(U,headers=H,json={"from_date":"2026-07-10T00:00:00Z","to_date":"2026-07-23T00:00:00Z"},timeout=90).json()
DUR=["resolve_time","response_time","time_to_first_reply",
     "resolve_time_business_hours","response_time_business_hours",
     "time_to_first_reply_business_hours","handle_time","replies_to_resolve"]
print("=== A. ADDITIVITY: is top-level == sum over actors, per BUCKET? ===")
for m in DUR:
    res=[]
    for i in range(len(d[m])):
        s=sum(a[m][i] for a in d["actors"])
        res.append(abs(s-d[m][i]))
    print(f"  {m:38s} max per-bucket |Sigma_actors - top| = {max(res):.9f}")

print("\n=== B. value/count ratio per day (what one 'unit' means per ticket) ===")
print(f"{'metric':38s} {'ratio min':>10s} {'median':>10s} {'max':>10s}  -> median as sec/min/hr")
for m in DUR:
    c=m+"_count"
    r=[d[m][i]/d[c][i] for i in range(len(d[m])) if d[c][i]]
    med=st.median(r)
    print(f"{m:38s} {min(r):10.3f} {med:10.3f} {max(r):10.3f}  "
          f"{med:.0f}s={med/60:.1f}m | {med:.1f}m={med/60:.2f}h | {med:.2f}h")

print("\n=== C. Is the per-ACTOR ratio the same as the top-level ratio? ===")
for m in ["resolve_time","handle_time"]:
    c=m+"_count"
    tot=sum(d[m])/sum(d[c])
    per=[]
    for a in d["actors"]:
        n=sum(a[c]); 
        if n>20: per.append(sum(a[m])/n)
    print(f"  {m:34s} top-level ratio={tot:.4f}  actor ratios: min={min(per):.4f} med={st.median(per):.4f} max={max(per):.4f} (n={len(per)})")

print("\n=== D. handle_time raw values (why it looks odd) ===")
print("  handle_time      :", [round(x,4) for x in d["handle_time"]])
print("  handle_time_count:", d["handle_time_count"])
print("  resolve_time     :", [round(x,2) for x in d["resolve_time"]])
print("  resolve_time_cnt :", d["resolve_time_count"])

print("\n=== E. business-hours ratio (implied working day) ===")
for base in ["resolve_time","response_time","time_to_first_reply"]:
    bh=base+"_business_hours"
    r=[d[bh][i]/d[base][i] for i in range(len(d[base])) if d[base][i]]
    print(f"  {bh:38s} ratio med={st.median(r):.4f} min={min(r):.4f} max={max(r):.4f}")

print("\n=== F. _count companions vs plausible denominators ===")
print("  resolved              :", d["resolved"])
print("  resolve_time_count    :", d["resolve_time_count"])
print("  replies               :", d["replies"])
print("  response_time_count   :", d["response_time_count"])
print("  new_tickets           :", d["new_tickets"])
print("  ttfr_count            :", d["time_to_first_reply_count"])
