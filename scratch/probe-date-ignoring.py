"""Follow-up probe: does the API actually respect from_date/to_date/time_unit at all?"""
import sys
sys.path.insert(0, "/home/timop/work/loopai/scratch")
from probe_common import call, base_body

SCRATCH = "/home/timop/work/loopai/scratch"


def show(label, body, savename):
    _, r = call(body, label=label, save_to=f"{SCRATCH}/{savename}")
    j = r.get("response_json", {})
    ticks = j.get("ticks") if isinstance(j, dict) else j
    print(f"  ticks: {ticks}")
    if isinstance(j, dict):
        print(f"  resolved: {j.get('resolved')}")
    print(f"  status: {r.get('status_code')}")


print("### entirely-in-the-past small range (2024-03-01 to 2024-03-06, day) ###")
show("past range", base_body(from_date="2024-03-01T00:00:00.000Z", to_date="2024-03-06T00:00:00.000Z", time_unit="day"),
     "resp-x1-past-range.json")

print("\n### entirely-in-the-past small range (2020-01-01 to 2020-01-04, day) ###")
show("past range 2020", base_body(from_date="2020-01-01T00:00:00.000Z", to_date="2020-01-04T00:00:00.000Z", time_unit="day"),
     "resp-x2-past-range-2020.json")

print("\n### far future range (2030-01-01 to 2030-01-06) ###")
show("future range", base_body(from_date="2030-01-01T00:00:00.000Z", to_date="2030-01-06T00:00:00.000Z", time_unit="day"),
     "resp-x3-future-range.json")

print("\n### narrow 2-day range within the 'known good' window (07-15 to 07-17) ###")
show("narrow known-good", base_body(from_date="2026-07-15T00:00:00.000Z", to_date="2026-07-17T00:00:00.000Z", time_unit="day"),
     "resp-x4-narrow-knowngood.json")

print("\n### same but different to_date only (07-10 to 07-12) ###")
show("diff to_date", base_body(from_date="2026-07-10T00:00:00.000Z", to_date="2026-07-12T00:00:00.000Z", time_unit="day"),
     "resp-x5-diff-todate.json")

print("\n### exact inverted (from=07-24 to=07-10) again for clarity ###")
show("inverted exact", base_body(from_date="2026-07-24T00:00:00.000Z", to_date="2026-07-10T00:00:00.000Z", time_unit="day"),
     "resp-x6-inverted.json")

print("\n### from==to (zero-width range) ###")
show("zero width", base_body(from_date="2026-07-15T00:00:00.000Z", to_date="2026-07-15T00:00:00.000Z", time_unit="day"),
     "resp-x7-zerowidth.json")

print("\n### tiny range far past, from < to (2019-05-01 to 2019-05-03) ###")
show("tiny far past", base_body(from_date="2019-05-01T00:00:00.000Z", to_date="2019-05-03T00:00:00.000Z", time_unit="day"),
     "resp-x8-tinyfarpast.json")

print("\n### time_type=today (per spec, should be very small window) ###")
show("time_type=today", base_body(time_type="today"), "resp-x9-time-type-today.json")

print("\n### time_type=yesterday ###")
show("time_type=yesterday", base_body(time_type="yesterday"), "resp-x10-time-type-yesterday.json")

print("\n### time_type=all ###")
show("time_type=all", base_body(time_type="all"), "resp-x11-time-type-all.json")
