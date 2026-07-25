import httpx, json, time

HOST = "https://ai-homework-production-2423.up.railway.app"
URL = HOST + "/reporting_api/v1/reporting/stats/json"
AUTH = {"Authorization": "Bearer any-token-works", "Content-Type": "application/json", "Accept": "application/json"}

BASE = {
    "community_id": "demo-community",
    "event_types": ["resolved"],
    "time_type": "custom",
    "time_unit": "day",
    "time_period": 1,
    "timezone": "America/New_York",
    "from_date": "2026-07-10T05:00:00.000Z",
    "to_date": "2026-07-23T03:59:59.999Z",
    "filters": []
}

client = httpx.Client(timeout=45)
out = []

def run(name, body_or_bytes, headers=None, timeout=45):
    h = dict(AUTH)
    if headers: h.update(headers)
    t0 = time.perf_counter()
    try:
        if isinstance(body_or_bytes, (bytes, str)):
            r = client.post(URL, content=body_or_bytes, headers=h, timeout=timeout)
        else:
            r = client.post(URL, json=body_or_bytes, headers=h, timeout=timeout)
        dt = time.perf_counter() - t0
        msg = f"{name}: status={r.status_code} time={dt:.2f}s resp_len={len(r.content)} body_snip={r.text[:300]}"
    except httpx.TimeoutException as e:
        dt = time.perf_counter() - t0
        msg = f"{name}: TIMEOUT after {dt:.2f}s ({e})"
    except Exception as e:
        dt = time.perf_counter() - t0
        msg = f"{name}: EXCEPTION after {dt:.2f}s: {e}"
    print(msg)
    out.append(msg)

# 1. huge body - pad with a huge filters array of junk
big_filters = [{"field": f"junk_field_{i}", "op": "eq", "value": "x"*50} for i in range(50000)]
big_body = dict(BASE)
big_body["filters"] = big_filters
run("HUGE_BODY(~50k filter objs)", big_body)

# 2. deeply nested filters value
def make_nested(depth):
    obj = {"v": 1}
    for _ in range(depth):
        obj = {"nested": obj}
    return obj

nested_body = dict(BASE)
nested_body["filters"] = [make_nested(5000)]
run("DEEPLY_NESTED_FILTERS(depth5000)", nested_body)

nested_body2 = dict(BASE)
nested_body2["filters"] = [make_nested(50000)]
run("DEEPLY_NESTED_FILTERS(depth50000)", nested_body2)

# 3. enormous date range
huge_range_body = dict(BASE)
huge_range_body["from_date"] = "1900-01-01T00:00:00.000Z"
huge_range_body["to_date"] = "2100-01-01T00:00:00.000Z"
run("ENORMOUS_DATE_RANGE(1900-2100)", huge_range_body)

huge_range_body2 = dict(BASE)
huge_range_body2["from_date"] = "1900-01-01T00:00:00.000Z"
huge_range_body2["to_date"] = "2100-01-01T00:00:00.000Z"
huge_range_body2["time_unit"] = "hour"
run("ENORMOUS_DATE_RANGE_HOURLY(1900-2100,hour)", huge_range_body2)

# 4. raw huge byte body (not valid structured but huge)
raw_huge = b'{"community_id":"demo-community","filters":[' + b'"x",' * 2000000 + b'"end"]}'
run("RAW_HUGE_BYTES(~10MB junk array)", raw_huge)

with open("/home/timop/work/loopai/scratch/fresh-eyes/evidence-auth-infra/robustness.txt", "w") as f:
    f.write("\n".join(out))

print("DONE ROBUSTNESS")
