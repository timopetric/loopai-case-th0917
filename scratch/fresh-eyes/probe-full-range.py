import httpx, json, os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"

def post(body, label):
    r = httpx.post(URL, headers=HEADERS, json=body, timeout=90)
    print(label, r.status_code, len(r.content))
    data = r.json()
    with open(os.path.join(OUTDIR, f"raw-{label}.json"), "w") as f:
        json.dump(data, f, indent=2)
    return data

wide = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"day",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2020-01-01T00:00:00.000Z",
    "to_date":"2027-01-01T00:00:00.000Z",
    "filters":[]
}
d = post(wide, "wide-2020-2027")
print("num ticks:", len(d["ticks"]), "num values:", len(d["new_tickets"]))
print("first tick:", d["ticks"][0], "last tick:", d["ticks"][-1])
nz = [i for i,v in enumerate(d["new_tickets"]) if v != 0]
print("nonzero new_tickets indices range:", nz[0] if nz else None, nz[-1] if nz else None, "count nonzero:", len(nz))
print("num actors:", len(d["actors"]))
print("num mailbox:", len(d["mailbox"]))

# try time_type "all"
try:
    all_type = dict(wide)
    all_type["time_type"] = "all"
    d2 = post(all_type, "time-type-all")
    print("all-type ticks len:", len(d2.get("ticks", [])))
except Exception as e:
    print("time_type=all failed:", e)
