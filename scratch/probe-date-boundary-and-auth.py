"""Second pass Q4 (date window boundary binary search) and Q5 (auth edge / rate limit)."""
import sys, json, time
sys.path.insert(0, "/home/timop/work/loopai/scratch")
import requests
from probe_common import URL, HEADERS, call, base_body

SCRATCH = "/home/timop/work/loopai/scratch"


def ticks_for(from_date, to_date):
    body = base_body(from_date=from_date, to_date=to_date, time_unit="day")
    _, r = call(body)
    j = r.get("response_json", {})
    return j.get("ticks", [])


def main():
    print("### Binary search: earliest from_date that still produces the FULL clamp-fallback (i.e. overlap start) ###")
    # We know 2026-07-10 to 2026-07-24 is the 'good' window (from pass 1).
    # Probe from_date values approaching 2026-07-10 from below and above to find the true left edge.
    candidates = [
        "2026-07-08T00:00:00.000Z", "2026-07-09T00:00:00.000Z", "2026-07-09T12:00:00.000Z",
        "2026-07-09T23:00:00.000Z", "2026-07-09T23:59:00.000Z", "2026-07-09T23:59:59.999Z",
        "2026-07-10T00:00:00.000Z", "2026-07-10T00:00:00.001Z", "2026-07-10T01:00:00.000Z",
        "2026-07-11T00:00:00.000Z",
    ]
    to_date_fixed = "2026-07-24T23:59:59.999Z"
    for c in candidates:
        t = ticks_for(c, to_date_fixed)
        print(f"  from={c} -> ticks[0]={t[0] if t else None} ticks[-1]={t[-1] if t else None} n={len(t)}")

    print("\n### Binary search: right edge (to_date) — where does 'today' cut off? ###")
    from_date_fixed = "2026-07-01T00:00:00.000Z"
    candidates_to = [
        "2026-07-22T00:00:00.000Z", "2026-07-23T00:00:00.000Z", "2026-07-23T23:59:59.999Z",
        "2026-07-24T00:00:00.000Z", "2026-07-24T12:00:00.000Z", "2026-07-24T23:59:59.999Z",
        "2026-07-25T00:00:00.000Z", "2026-07-26T00:00:00.000Z", "2026-07-31T00:00:00.000Z",
    ]
    for c in candidates_to:
        t = ticks_for(from_date_fixed, c)
        print(f"  to={c} -> ticks[0]={t[0] if t else None} ticks[-1]={t[-1] if t else None} n={len(t)}")

    print("\n### Just-barely-overlapping ranges (1-day sliver at each edge of the fixed window) ###")
    # 1 day before window start, overlapping only the very first day
    t = ticks_for("2026-07-09T00:00:00.000Z", "2026-07-10T12:00:00.000Z")
    print(f"  sliver at left edge -> ticks={t}")
    # 1 day after window end
    t = ticks_for("2026-07-23T12:00:00.000Z", "2026-07-25T00:00:00.000Z")
    print(f"  sliver at right edge -> ticks={t}")
    # just outside, 1 day beyond window on both sides, no overlap
    t = ticks_for("2026-07-25T00:00:00.000Z", "2026-07-26T00:00:00.000Z")
    print(f"  1-day range fully after window (07-25 to 07-26) -> ticks={t}")
    t = ticks_for("2026-07-08T00:00:00.000Z", "2026-07-09T00:00:00.000Z")
    print(f"  1-day range fully before window (07-08 to 07-09) -> ticks={t}")

    print("\n### Auth edge cases ###")
    body = base_body()

    def try_auth(headers, label):
        try:
            r = requests.post(URL, headers=headers, json=body, timeout=20)
            print(f"  {label}: status={r.status_code} body[:150]={r.text[:150]!r}")
        except Exception as e:
            print(f"  {label}: EXCEPTION {e}")

    try_auth({"Authorization": "Bearer test", "Content-Type": "application/json"}, "Bearer test (baseline)")
    try_auth({"Authorization": "Bearer ", "Content-Type": "application/json"}, "Bearer <empty>")
    try_auth({"Authorization": "Basic dGVzdDp0ZXN0", "Content-Type": "application/json"}, "Basic auth")
    try_auth({"Authorization": "test", "Content-Type": "application/json"}, "raw token, no scheme")
    try_auth({"Authorization": "Bearer " + "x" * 500, "Content-Type": "application/json"}, "very long bearer token")
    try_auth({"Content-Type": "application/json"}, "no Authorization header at all")
    try_auth({"Authorization": "", "Content-Type": "application/json"}, "empty Authorization header")

    print("\n### Burst / rate limit check (20 rapid requests) ###")
    statuses = []
    t0 = time.time()
    for i in range(20):
        r = requests.post(URL, headers=HEADERS, json=body, timeout=20)
        statuses.append(r.status_code)
    dt = time.time() - t0
    print(f"  20 requests in {dt:.2f}s, statuses: {statuses}")
    print(f"  unique statuses: {set(statuses)}")


if __name__ == "__main__":
    main()
