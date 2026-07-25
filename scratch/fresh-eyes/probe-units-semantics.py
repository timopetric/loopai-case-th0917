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
    print(f"--- {label} --- status={r.status_code} size={len(r.content)}")
    fn = os.path.join(OUTDIR, f"raw-{label}.json")
    data = r.json()
    with open(fn, "w") as f:
        json.dump(data, f, indent=2)
    print(f"saved {fn}  ticks={data.get('ticks')}")
    return data


if __name__ == "__main__":
    # 14 daily buckets, 2026-07-10 .. 2026-07-24 (matches known-good but refetch fresh)
    daily = post({
        "community_id": "demo-community",
        "event_types": ["resolved"],
        "time_type": "custom",
        "time_unit": "day",
        "time_period": 1,
        "timezone": "America/New_York",
        "from_date": "2026-07-10T05:00:00.000Z",
        "to_date": "2026-07-23T03:59:59.999Z",
        "filters": [],
    }, "units-daily")

    # 1 week bucket covering the SAME 7 days as first 7 daily buckets: 07-10 .. 07-17 (7 days)
    weekly = post({
        "community_id": "demo-community",
        "event_types": ["resolved"],
        "time_type": "custom",
        "time_unit": "week",
        "time_period": 1,
        "timezone": "America/New_York",
        "from_date": "2026-07-10T05:00:00.000Z",
        "to_date": "2026-07-17T04:59:59.999Z",
        "filters": [],
    }, "units-weekly")

    # hourly buckets for a single day: 2026-07-15 (America/New_York, so 05:00Z..next 05:00Z)
    hourly = post({
        "community_id": "demo-community",
        "event_types": ["resolved"],
        "time_type": "custom",
        "time_unit": "hour",
        "time_period": 1,
        "timezone": "America/New_York",
        "from_date": "2026-07-15T04:00:00.000Z",
        "to_date": "2026-07-16T03:59:59.999Z",
        "filters": [],
    }, "units-hourly")

    print("DONE")
