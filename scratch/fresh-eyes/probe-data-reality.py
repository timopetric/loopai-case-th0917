#!/usr/bin/env python3
"""Probe DATA REALITY: window boundaries, determinism, per-day shape, granularity consistency.
Saves raw evidence to scratch/fresh-eyes/evidence-data/ and prints summaries.
"""
import httpx
import json
import time
import os
from datetime import datetime, timezone

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

EVDIR = "/home/timop/work/loopai/scratch/fresh-eyes/evidence-data"
os.makedirs(EVDIR, exist_ok=True)

BASE = {
    "community_id": "demo-community",
    "event_types": ["resolved"],
    "time_type": "custom",
    "time_unit": "day",
    "time_period": 1,
    "timezone": "America/New_York",
    "from_date": "2026-07-10T05:00:00.000Z",
    "to_date": "2026-07-23T03:59:59.999Z",
    "filters": [],
}

ALL_EVENT_TYPES_GUESS = ["resolved"]  # will discover more if visible in response


def post(body, name=None, timeout=60):
    t0 = time.time()
    try:
        r = httpx.post(URL, headers=HEADERS, json=body, timeout=timeout)
        dt = time.time() - t0
        try:
            data = r.json()
        except Exception:
            data = {"_raw_text": r.text[:2000]}
        result = {"status": r.status_code, "elapsed_s": round(dt, 3), "body_len": len(r.content), "json": data}
    except Exception as e:
        dt = time.time() - t0
        result = {"status": None, "elapsed_s": round(dt, 3), "error": str(e)}
    if name:
        with open(os.path.join(EVDIR, name), "w") as f:
            json.dump({"request": body, "response": result}, f, indent=2, default=str)
    return result


def mk(**kwargs):
    b = json.loads(json.dumps(BASE))
    b.update(kwargs)
    return b


def summarize(res, label):
    print(f"--- {label} ---")
    print(f"status={res.get('status')} elapsed={res.get('elapsed_s')}s body_len={res.get('body_len')}")
    j = res.get("json")
    if isinstance(j, dict):
        keys = list(j.keys())
        print(f"top-level keys: {keys}")
    return j


if __name__ == "__main__":
    print("=== STEP 1: WIDE SWEEP (month buckets, 2015-2030) ===")
    r = post(mk(time_unit="month", time_period=1, from_date="2015-01-01T00:00:00.000Z", to_date="2030-01-01T00:00:00.000Z"), "01-wide-sweep-month.json")
    summarize(r, "wide sweep month 2015-2030")

print("\n=== STEP 2: FAR PAST / FAR FUTURE / GRANULARITY IGNORED? ===")
r2 = post(mk(time_unit="day", from_date="1999-01-01T00:00:00.000Z", to_date="1999-02-01T00:00:00.000Z"), "02-far-past.json")
summarize(r2, "far past 1999")
j2 = r2.get("json")
if isinstance(j2, dict):
    print("ticks:", j2.get("ticks"))

r3 = post(mk(time_unit="hour", from_date="2099-01-01T00:00:00.000Z", to_date="2099-02-01T00:00:00.000Z"), "03-far-future.json")
summarize(r3, "far future 2099")
j3 = r3.get("json")
if isinstance(j3, dict):
    print("ticks:", j3.get("ticks"))

r4 = post(mk(time_unit="week", time_period=2, from_date="2020-06-01T00:00:00.000Z", to_date="2020-06-15T00:00:00.000Z"), "04-different-week-req.json")
summarize(r4, "arbitrary week request 2020")
j4 = r4.get("json")
if isinstance(j4, dict):
    print("ticks:", j4.get("ticks"))
    print("resolved:", j4.get("resolved"))

print("\n=== STEP 3: MINUTE GRANULARITY OVER A MONTH (cap/timeout test) ===")
r5 = post(mk(time_unit="minute", time_period=1, from_date="2026-06-01T00:00:00.000Z", to_date="2026-07-01T00:00:00.000Z"), "05-minute-over-month.json", timeout=120)
summarize(r5, "minute granularity over a month")

print("\n=== STEP 4: ZERO-WIDTH RANGE (from==to) ===")
r6 = post(mk(from_date="2026-07-15T00:00:00.000Z", to_date="2026-07-15T00:00:00.000Z"), "06-zero-width.json")
summarize(r6, "zero-width from==to")

print("\n=== STEP 5: INVERTED RANGE (to < from) ===")
r7 = post(mk(from_date="2026-07-23T00:00:00.000Z", to_date="2026-07-10T00:00:00.000Z"), "07-inverted.json")
summarize(r7, "inverted to<from")

print("\n=== STEP 6: from_date TIME-OF-DAY VARIATIONS ===")
for hh in ["00","05","12","23"]:
    rr = post(mk(from_date=f"2026-07-10T{hh}:00:00.000Z"), f"08-tod-{hh}.json")
    j = rr.get("json")
    print(f"hh={hh} status={rr.get('status')} ticks[0:2]={j.get('ticks')[:2] if isinstance(j,dict) else None} resolved[0]={j.get('resolved')[0] if isinstance(j,dict) else None}")

print("\n=== STEP 7: DETERMINISM - repeat identical known-good request now (t0) ===")
r8a = post(mk(), "09-determinism-t0.json")
summarize(r8a, "determinism t0")

print("\n=== STEP 8: PARTIAL SUB-RANGE WITHIN CANNED WINDOW ===")
r9 = post(mk(from_date="2026-07-12T00:00:00.000Z", to_date="2026-07-18T00:00:00.000Z"), "10-subrange.json")
j9 = r9.get("json")
print("ticks:", j9.get("ticks") if isinstance(j9, dict) else None)
print("resolved:", j9.get("resolved") if isinstance(j9, dict) else None)

print("\n=== STEP 9: from_date INSIDE window, to_date FAR future (clamp test) ===")
r10 = post(mk(from_date="2026-07-20T00:00:00.000Z", to_date="2099-01-01T00:00:00.000Z"), "11-from-inside-to-far.json")
j10 = r10.get("json")
print("ticks:", j10.get("ticks") if isinstance(j10, dict) else None)
print("resolved:", j10.get("resolved") if isinstance(j10, dict) else None)

print("\n=== STEP 10: from_date BEFORE window, to_date INSIDE window (clamp test) ===")
r11 = post(mk(from_date="2015-01-01T00:00:00.000Z", to_date="2026-07-15T00:00:00.000Z"), "12-from-far-to-inside.json")
j11 = r11.get("json")
print("ticks:", j11.get("ticks") if isinstance(j11, dict) else None)
print("resolved:", j11.get("resolved") if isinstance(j11, dict) else None)

print("\n=== STEP 11: from_date one day BEFORE window start (2026-07-09) ===")
r12 = post(mk(from_date="2026-07-09T00:00:00.000Z", to_date="2026-07-11T00:00:00.000Z"), "13-from-just-before.json")
j12 = r12.get("json")
print("ticks:", j12.get("ticks") if isinstance(j12, dict) else None)
print("resolved:", j12.get("resolved") if isinstance(j12, dict) else None)

print("\n=== STEP 12: from_date one day AFTER window end (2026-07-25, i.e. today) ===")
r13 = post(mk(from_date="2026-07-25T00:00:00.000Z", to_date="2026-07-26T00:00:00.000Z"), "14-from-after-window.json")
j13 = r13.get("json")
print("status:", r13.get("status"))
print("ticks:", j13.get("ticks") if isinstance(j13, dict) else j13)
print("resolved:", j13.get("resolved") if isinstance(j13, dict) else None)

print("\n=== STEP 13: BOTH ENDPOINTS PAST WINDOW END (2026-07-26 to 07-28) ===")
r14 = post(mk(from_date="2026-07-26T00:00:00.000Z", to_date="2026-07-28T00:00:00.000Z"), "15-both-past-end.json")
j14 = r14.get("json")
print("ticks:", j14.get("ticks") if isinstance(j14, dict) else j14)

print("\n=== STEP 14: last actual day only (07-24 to 07-25) ===")
r15 = post(mk(from_date="2026-07-24T00:00:00.000Z", to_date="2026-07-25T00:00:00.000Z"), "16-last-day-only.json")
j15 = r15.get("json")
print("ticks:", j15.get("ticks") if isinstance(j15, dict) else j15)
print("resolved:", j15.get("resolved") if isinstance(j15, dict) else None)

print("\n=== STEP 15: first actual day only (07-10 to 07-11) ===")
r16 = post(mk(from_date="2026-07-10T00:00:00.000Z", to_date="2026-07-11T00:00:00.000Z"), "17-first-day-only.json")
j16 = r16.get("json")
print("ticks:", j16.get("ticks") if isinstance(j16, dict) else j16)
print("resolved:", j16.get("resolved") if isinstance(j16, dict) else None)

print("\n=== STEP 16: FULL DUMP of canned window, all metrics ===")
rfull = post(mk(from_date="2026-07-01T00:00:00.000Z", to_date="2026-08-05T00:00:00.000Z"), "18-full-dump.json")
jfull = rfull.get("json")
metrics = ['actioned_emails','resolved','new_tickets','open','replies','new_emails',
           'replies_to_resolve','replies_to_resolve_count','resolve_time','resolve_time_count',
           'response_time','response_time_count','time_to_first_reply','time_to_first_reply_count',
           'resolve_time_business_hours','resolve_time_business_hours_count',
           'response_time_business_hours','response_time_business_hours_count',
           'time_to_first_reply_business_hours','time_to_first_reply_business_hours_count',
           'handle_time','handle_time_count','sla_breaches']
print("ticks:", jfull.get("ticks"))
for m in metrics:
    v = jfull.get(m)
    print(m, "->", v)
for dim in ['actors','mailbox','labels','topics','categories']:
    print(dim, "->", jfull.get(dim))

print("\n=== STEP 17: RE-TEST last-day-only with UTC timezone (avoid TZ confound) ===")
r17 = post(mk(timezone="UTC", from_date="2026-07-24T00:00:00.000Z", to_date="2026-07-25T00:00:00.000Z"), "19-last-day-utc.json")
j17 = r17.get("json")
print("ticks:", j17.get("ticks") if isinstance(j17, dict) else j17)
print("resolved:", j17.get("resolved") if isinstance(j17, dict) else None)

print("\n=== STEP 18: from=07-24T04:00Z (=midnight EDT) to=07-25T04:00Z, tz=America/New_York ===")
r18 = post(mk(from_date="2026-07-24T04:00:00.000Z", to_date="2026-07-25T04:00:00.000Z"), "20-last-day-edt-midnight.json")
j18 = r18.get("json")
print("ticks:", j18.get("ticks") if isinstance(j18, dict) else j18)
print("resolved:", j18.get("resolved") if isinstance(j18, dict) else None)

print("\n=== STEP 19: from=07-23T00:00Z to=07-25T00:00Z, tz=UTC (2-day span at true end) ===")
r19 = post(mk(timezone="UTC", from_date="2026-07-23T00:00:00.000Z", to_date="2026-07-25T00:00:00.000Z"), "21-2day-end-utc.json")
j19 = r19.get("json")
print("ticks:", j19.get("ticks") if isinstance(j19, dict) else j19)
print("resolved:", j19.get("resolved") if isinstance(j19, dict) else None)

print("\n=== STEP 20: EXACT BOUNDARY - from=07-09T23:59:59Z (1s before window) ===")
rb1 = post(mk(from_date="2026-07-09T23:59:59.000Z", to_date="2026-07-11T00:00:00.000Z"), "22-boundary-before.json")
jb1 = rb1.get("json")
print("ticks:", jb1.get("ticks") if isinstance(jb1, dict) else jb1)

print("\n=== STEP 21: EXACT BOUNDARY - from=07-10T00:00:00Z (exactly window start) ===")
rb2 = post(mk(from_date="2026-07-10T00:00:00.000Z", to_date="2026-07-11T00:00:00.000Z"), "23-boundary-exact-start.json")
jb2 = rb2.get("json")
print("ticks:", jb2.get("ticks") if isinstance(jb2, dict) else jb2)
print("resolved:", jb2.get("resolved") if isinstance(jb2, dict) else None)

print("\n=== STEP 22: from=07-23T23:59:59Z (last valid day, late in day) ===")
rb3 = post(mk(from_date="2026-07-23T23:59:59.000Z", to_date="2026-07-24T23:59:59.000Z"), "24-boundary-last-valid.json")
jb3 = rb3.get("json")
print("ticks:", jb3.get("ticks") if isinstance(jb3, dict) else jb3)
print("resolved:", jb3.get("resolved") if isinstance(jb3, dict) else None)
