import httpx, json, os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"

def post(body, label, save=True):
    r = httpx.post(URL, headers=HEADERS, json=body, timeout=60)
    print(f"--- {label} --- status={r.status_code}")
    data = r.json()
    if save:
        with open(os.path.join(OUTDIR, f"raw-{label}.json"), "w") as f:
            json.dump(data, f, indent=2)
    return data

# Single day request: just July 15 (a day with a distinguishable count hopefully)
one_day = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"day",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2026-07-15T04:00:00.000Z",
    "to_date":"2026-07-16T03:59:59.999Z",
    "filters":[]
}
d1 = post(one_day, "one-day-jul15")
print("ticks:", d1["ticks"])
print("new_tickets:", d1["new_tickets"])
print("resolved:", d1["resolved"])

# 14 day request covering same window, from known-good body
fourteen = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"day",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2026-07-10T05:00:00.000Z",
    "to_date":"2026-07-23T03:59:59.999Z",
    "filters":[]
}
d14 = post(fourteen, "fourteen-day")
print("ticks:", d14["ticks"])
print("new_tickets:", d14["new_tickets"])
print("resolved:", d14["resolved"])
print("len ticks", len(d14["ticks"]), "len values", len(d14["new_tickets"]))

# find index of jul15 in the 14-day ticks
for i, t in enumerate(d14["ticks"]):
    print(i, t)
