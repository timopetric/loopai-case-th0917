import httpx, time, statistics, json

HOST = "https://ai-homework-production-2423.up.railway.app"
URL = HOST + "/reporting_api/v1/reporting/stats/json"
AUTH = {"Authorization": "Bearer any-token-works", "Content-Type": "application/json", "Accept": "application/json"}

SMALL_BODY = {
    "community_id": "demo-community",
    "event_types": ["resolved"],
    "time_type": "custom",
    "time_unit": "day",
    "time_period": 1,
    "timezone": "America/New_York",
    "from_date": "2026-07-22T05:00:00.000Z",
    "to_date": "2026-07-23T03:59:59.999Z",
    "filters": []
}

LARGE_BODY = {
    "community_id": "demo-community",
    "event_types": ["resolved", "actioned_emails"],
    "time_type": "custom",
    "time_unit": "hour",
    "time_period": 1,
    "timezone": "America/New_York",
    "from_date": "2026-06-25T05:00:00.000Z",
    "to_date": "2026-07-25T03:59:59.999Z",
    "filters": []
}

client = httpx.Client(timeout=60)
out = []

def measure(name, body, n=8):
    times = []
    sizes = []
    statuses = []
    for i in range(n):
        t0 = time.perf_counter()
        r = client.post(URL, json=body, headers=AUTH)
        dt = time.perf_counter() - t0
        times.append(dt)
        sizes.append(len(r.content))
        statuses.append(r.status_code)
    times_sorted = sorted(times)
    p50 = times_sorted[len(times_sorted)//2]
    p90 = times_sorted[min(len(times_sorted)-1, int(len(times_sorted)*0.9))]
    msg = f"{name}: n={n} statuses={statuses} sizes={sizes} times={[round(t,3) for t in times]} p50={p50:.3f}s p90={p90:.3f}s"
    print(msg)
    out.append(msg)
    return times, r

# small request latency
measure("SMALL(1day,resolved)", SMALL_BODY)
# large request latency
measure("LARGE(30days,hourly,2 event types)", LARGE_BODY)

# caching check: identical repeated request timing + headers
r1 = client.post(URL, json=SMALL_BODY, headers=AUTH)
r2 = client.post(URL, json=SMALL_BODY, headers=AUTH)
msg = f"CACHE_CHECK: etag1={r1.headers.get('etag')} etag2={r2.headers.get('etag')} cache-control={r1.headers.get('cache-control')} last-modified={r1.headers.get('last-modified')} identical_body={r1.text==r2.text}"
print(msg); out.append(msg)

with open("/home/timop/work/loopai/scratch/fresh-eyes/evidence-auth-infra/latency.txt","w") as f:
    f.write("\n".join(out))

# ---- RATE LIMIT BURST ----
print("Starting burst...")
burst_results = []
N = 80
t_start = time.perf_counter()
for i in range(N):
    t0 = time.perf_counter()
    try:
        r = client.post(URL, json=SMALL_BODY, headers=AUTH)
        dt = time.perf_counter() - t0
        burst_results.append((i, r.status_code, round(dt,3), r.headers.get("retry-after")))
        if r.status_code == 429:
            print(f"429 at request {i}, retry-after={r.headers.get('retry-after')}")
    except Exception as e:
        burst_results.append((i, "EXC", str(e)[:80], None))
t_total = time.perf_counter() - t_start

statuses = [b[1] for b in burst_results]
n_429 = statuses.count(429)
n_200 = statuses.count(200)
throughput = N / t_total
summary = f"BURST: N={N} total_time={t_total:.2f}s throughput={throughput:.2f} req/s  status_counts: 200={n_200} 429={n_429} other={N-n_200-n_429}"
print(summary)

with open("/home/timop/work/loopai/scratch/fresh-eyes/evidence-auth-infra/rate_limit_burst.txt","w") as f:
    f.write(summary + "\n")
    for row in burst_results:
        f.write(str(row) + "\n")

print("DONE")
