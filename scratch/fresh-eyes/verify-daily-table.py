import httpx
U="https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
H={"Authorization":"Bearer t","Content-Type":"application/json"}
d=httpx.post(U,headers=H,json={"from_date":"2026-07-10T00:00:00Z","to_date":"2026-07-23T00:00:00Z"},timeout=90).json()
import datetime as dt
print("| day | dow | new_tickets | resolved | replies | actioned | sla_br | resolve_h/tkt | ttfr_h/tkt |")
print("|---|---|---|---|---|---|---|---|---|")
for i,t in enumerate(d["ticks"][:-1]):
    day=dt.datetime.fromisoformat(t.replace("Z","+00:00"))
    rt=d["resolve_time"][i]/d["resolve_time_count"][i] if d["resolve_time_count"][i] else 0
    ft=d["time_to_first_reply"][i]/d["time_to_first_reply_count"][i] if d["time_to_first_reply_count"][i] else 0
    print(f"| {day:%Y-%m-%d} | {day:%a} | {d['new_tickets'][i]} | {d['resolved'][i]} | {d['replies'][i]} | {d['actioned_emails'][i]} | {d['sla_breaches'][i]} | {rt:.2f} | {ft:.2f} |")
print()
print("open all zero:", all(v==0 for v in d["open"]), "| across actors:", all(v==0 for a in d["actors"] for v in a["open"]))
print("sla_breaches total:", sum(d["sla_breaches"]))
print("labels/topics/categories:", d["labels"], d["topics"], d["categories"])
nz=[a["name"] for a in d["actors"] if sum(a["new_tickets"])>0]
print(f"actors with any new_tickets: {len(nz)}/108")
nzm=[m["name"] for m in d["mailbox"] if sum(m["new_tickets"])>0]
print(f"mailboxes with any new_tickets: {len(nzm)}/103")
