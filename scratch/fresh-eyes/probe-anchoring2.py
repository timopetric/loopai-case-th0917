import httpx, json, os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"

def post(body, label):
    r = httpx.post(URL, headers=HEADERS, json=body, timeout=60)
    data = r.json()
    with open(os.path.join(OUTDIR, f"raw-{label}.json"), "w") as f:
        json.dump(data, f, indent=2)
    return data

# exact UTC single day
strict_day = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"day",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2026-07-15T00:00:00.000Z",
    "to_date":"2026-07-16T00:00:00.000Z",
    "filters":[]
}
d = post(strict_day, "strict-utc-day-jul15")
print("ticks:", d["ticks"])
print("new_tickets:", d["new_tickets"])
print("resolved:", d["resolved"])

# 2-day exact
two_day = dict(strict_day)
two_day["to_date"] = "2026-07-17T00:00:00.000Z"
d2 = post(two_day, "strict-utc-2day")
print("ticks:", d2["ticks"])
print("new_tickets:", d2["new_tickets"])

# week unit test
week = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"week",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2026-07-01T00:00:00.000Z",
    "to_date":"2026-07-29T00:00:00.000Z",
    "filters":[]
}
dw = post(week, "week-unit")
print("week ticks:", dw["ticks"])
print("week new_tickets:", dw["new_tickets"])

# month unit test
month = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"month",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2026-01-01T00:00:00.000Z",
    "to_date":"2026-08-01T00:00:00.000Z",
    "filters":[]
}
dm = post(month, "month-unit")
print("month ticks:", dm["ticks"])
print("month new_tickets:", dm["new_tickets"])
