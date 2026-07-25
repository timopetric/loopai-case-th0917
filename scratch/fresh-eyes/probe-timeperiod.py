import httpx, json

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {"Authorization": "Bearer any-token-works", "Content-Type": "application/json", "Accept": "application/json"}

body = {
    "community_id": "demo-community", "event_types": ["resolved"], "time_type": "custom",
    "time_unit": "day", "time_period": 7, "timezone": "America/New_York",
    "from_date": "2026-07-10T05:00:00.000Z", "to_date": "2026-07-17T04:59:59.999Z", "filters": []
}
r = httpx.post(URL, headers=HEADERS, json=body, timeout=60)
d = r.json()
print("ticks", d["ticks"])
print("resolved", d["resolved"])
print("resolve_time", d["resolve_time"])
print("resolve_time_count", d["resolve_time_count"])
json.dump(d, open("/home/timop/work/loopai/scratch/fresh-eyes/raw-units-timeperiod7.json", "w"), indent=2)
