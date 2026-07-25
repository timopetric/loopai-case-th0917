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
    print(label, r.status_code, len(r.content))
    try:
        data = r.json()
        with open(os.path.join(OUTDIR, f"raw-{label}.json"), "w") as f:
            json.dump(data, f, indent=2)
        return data
    except Exception as e:
        print("parse fail", e, r.text[:300])
        return None

# date range entirely before dataset
before = {
    "community_id":"demo-community",
    "event_types":["resolved"],
    "time_type":"custom",
    "time_unit":"day",
    "time_period":1,
    "timezone":"America/New_York",
    "from_date":"2020-01-01T00:00:00.000Z",
    "to_date":"2020-01-05T00:00:00.000Z",
    "filters":[]
}
d = post(before, "before-dataset")
if d:
    print("ticks:", d.get("ticks"))
    print("new_tickets:", d.get("new_tickets"))
    print("actors len:", len(d.get("actors",[])))
    print("mailbox len:", len(d.get("mailbox",[])))

# bogus event type
bogus = dict(before)
bogus["event_types"] = ["nonexistent_event_type_xyz"]
bogus["from_date"] = "2026-07-10T05:00:00.000Z"
bogus["to_date"] = "2026-07-23T03:59:59.999Z"
d2 = post(bogus, "bogus-event-type")
if d2:
    print("bogus ticks:", d2.get("ticks"))
    print("bogus new_tickets:", d2.get("new_tickets"))
    print("bogus actors len:", len(d2.get("actors",[])))
    print("bogus mailbox len:", len(d2.get("mailbox",[])))

# community_id nonsense
bad_comm = dict(before)
bad_comm["community_id"] = "does-not-exist-community"
bad_comm["from_date"] = "2026-07-10T05:00:00.000Z"
bad_comm["to_date"] = "2026-07-23T03:59:59.999Z"
d3 = post(bad_comm, "bad-community")
if d3:
    print("bad_comm ticks:", d3.get("ticks"))
    print("bad_comm actors len:", len(d3.get("actors",[])))
