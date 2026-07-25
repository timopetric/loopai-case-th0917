import httpx, json, sys, os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"

def post(body, label):
    r = httpx.post(URL, headers=HEADERS, json=body, timeout=60)
    print(f"--- {label} --- status={r.status_code} time={r.elapsed.total_seconds():.2f}s size={len(r.content)}")
    print("headers:", dict(r.headers))
    fn = os.path.join(OUTDIR, f"raw-{label}.json")
    try:
        data = r.json()
        with open(fn, "w") as f:
            json.dump(data, f, indent=2)
        print(f"saved {fn}")
        return data
    except Exception as e:
        print("JSON parse failed:", e)
        with open(fn + ".txt", "w") as f:
            f.write(r.text)
        return None

base = {
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

if __name__ == "__main__":
    data = post(base, "known-good")
    if data:
        print("TOP LEVEL KEYS:", list(data.keys()))
        for k, v in data.items():
            if isinstance(v, list):
                print(f"  {k}: list len={len(v)}", v[:2] if len(v) else v)
            elif isinstance(v, dict):
                print(f"  {k}: dict keys={list(v.keys())}")
            else:
                print(f"  {k}: {type(v)} = {v}")
