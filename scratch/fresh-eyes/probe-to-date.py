import httpx, json, copy, os

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
    return resp

# Vary to_date, keep from_date fixed at baseline, use valid ISO dates
for td in ["2026-07-15T00:00:00.000Z", "2026-07-11T00:00:00.000Z", "2026-08-01T00:00:00.000Z", "2026-07-10T12:00:00.000Z"]:
    b = copy.deepcopy(BASELINE); b["to_date"] = td
    req(f"G_to_date_{td.replace(':','-')}", b)

# to_date garbage string (non-date)
b = copy.deepcopy(BASELINE); b["to_date"] = "not-a-date"
req("G_to_date_garbage_string", b)

# to_date int
b = copy.deepcopy(BASELINE); b["to_date"] = 42
req("G_to_date_int_42", b)

# to_date empty string
b = copy.deepcopy(BASELINE); b["to_date"] = ""
req("G_to_date_empty_string", b)

# from_date empty string with different to_date to see if it's really "must be non-empty" gate
b = copy.deepcopy(BASELINE); b["from_date"] = ""
req("G_from_date_empty_string_recheck", b)

# both from_date and to_date garbage strings
b = copy.deepcopy(BASELINE); b["from_date"] = "garbage1"; b["to_date"] = "garbage2"
req("G_both_garbage", b)
