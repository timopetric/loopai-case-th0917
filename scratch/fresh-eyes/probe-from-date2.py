import httpx, copy, os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {"Authorization": "Bearer any-token-works", "Content-Type": "application/json", "Accept": "application/json"}
BASELINE = {
    "community_id": "demo-community", "event_types": ["resolved"], "time_type": "custom",
    "time_unit": "day", "time_period": 1, "timezone": "America/New_York",
    "from_date": "2026-07-10T05:00:00.000Z", "to_date": "2026-07-23T03:59:59.999Z", "filters": [],
}
EVDIR = "/home/timop/work/loopai/scratch/fresh-eyes/evidence"
client = httpx.Client(timeout=30)

def req(name, body):
    resp = client.post(URL, json=body, headers=HEADERS)
    with open(os.path.join(EVDIR, name + ".json"), "w") as f:
        f.write(f"STATUS: {resp.status_code}\nBODY:\n{resp.text}")
    try:
        j = resp.json()
        ticks = j.get("ticks") if isinstance(j, dict) else None
    except Exception:
        ticks = None
    print(name, resp.status_code, "ticks:", ticks)

for fd in ["2026-07-15T00:00:00.000Z", "2026-06-01T00:00:00.000Z", "2026-07-20T00:00:00.000Z", "2026-01-01T00:00:00.000Z"]:
    b = copy.deepcopy(BASELINE); b["from_date"] = fd
    req(f"H_from_date_{fd[:10]}", b)
