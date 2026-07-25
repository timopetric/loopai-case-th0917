#!/usr/bin/env python3
"""Probe the reporting stats endpoint's REQUEST CONTRACT and VALIDATION behavior.
Saves raw evidence to scratch/fresh-eyes/evidence/ and a summary JSON.
"""
import httpx
import json
import copy
import time
import os

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

BASELINE = {
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

EVDIR = "/home/timop/work/loopai/scratch/fresh-eyes/evidence"
os.makedirs(EVDIR, exist_ok=True)

results = []
client = httpx.Client(timeout=30)

def save_raw(name, resp):
    fn = os.path.join(EVDIR, name + ".json")
    try:
        body = resp.text
    except Exception:
        body = "<no body>"
    with open(fn, "w") as f:
        f.write(f"STATUS: {resp.status_code}\n")
        f.write(f"HEADERS: {dict(resp.headers)}\n")
        f.write("BODY:\n")
        f.write(body)
    return fn

def do_request(name, body=None, raw_content=None, method="POST", headers=None, params=None):
    h = headers if headers is not None else HEADERS
    try:
        if raw_content is not None:
            resp = client.request(method, URL, content=raw_content, headers=h, params=params)
        else:
            resp = client.request(method, URL, json=body, headers=h, params=params)
    except Exception as e:
        rec = {"name": name, "error": str(e)}
        results.append(rec)
        print(f"[{name}] EXCEPTION: {e}")
        return None
    fn = save_raw(name, resp)
    try:
        parsed = resp.json()
    except Exception:
        parsed = None
    rec = {
        "name": name,
        "status": resp.status_code,
        "body_snippet": (resp.text[:500] if resp.text else ""),
        "file": fn,
        "keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
    }
    results.append(rec)
    print(f"[{name}] status={resp.status_code} keys={rec['keys']}")
    return resp, parsed

def get_resp_json(name, body):
    r = do_request(name, body)
    if r is None:
        return None
    resp, parsed = r
    return parsed

# ---------- 0. Baseline ----------
print("\n=== 0. BASELINE ===")
base_resp, base_json = do_request("00_baseline", BASELINE)

# ---------- 1. Missing required fields, one at a time ----------
print("\n=== 1. FIELD OMISSION ===")
fields = list(BASELINE.keys())
for f in fields:
    b = copy.deepcopy(BASELINE)
    del b[f]
    do_request(f"01_omit_{f}", b)

do_request("01_empty_body", {})

# ---------- 2. event_types variations ----------
print("\n=== 2. event_types ===")
et_variants = {
    "single_metric_new_tickets": ["new_tickets"],
    "empty_array": [],
    "unknown_metric": ["totally_bogus_metric"],
    "mixed_known_unknown": ["resolved", "bogus"],
    "non_array_string": "resolved",
    "non_array_number": 5,
    "null": None,
    "all_15": ["actioned_emails","resolved","new_tickets","open","replies","new_emails",
               "replies_to_resolve","resolve_time","response_time","time_to_first_reply",
               "resolve_time_business_hours","response_time_business_hours",
               "time_to_first_reply_business_hours","sla_breaches","handle_time"],
}
et_results = {}
for name, val in et_variants.items():
    b = copy.deepcopy(BASELINE)
    b["event_types"] = val
    parsed = get_resp_json(f"02_event_types_{name}", b)
    et_results[name] = parsed
et_omit = get_resp_json("02_event_types_omitted", {k:v for k,v in BASELINE.items() if k != "event_types"})
et_results["omitted"] = et_omit

# ---------- 3. community_id variations ----------
print("\n=== 3. community_id ===")
cid_variants = {
    "other_string": "some-other-community",
    "empty_string": "",
    "null": None,
    "numeric": 12345,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "nonexistent_realistic": "nonexistent-community-xyz",
}
cid_results = {}
for name, val in cid_variants.items():
    b = copy.deepcopy(BASELINE)
    b["community_id"] = val
    parsed = get_resp_json(f"03_community_id_{name}", b)
    cid_results[name] = parsed

# ---------- 4. time_type variations ----------
print("\n=== 4. time_type ===")
tt_variants = ["today", "yesterday", "all", "custom", "7d", "30d", "1d", "90d",
               "garbage_value", None, 123]
tt_results = {}
for val in tt_variants:
    b = copy.deepcopy(BASELINE)
    b["time_type"] = val
    key = str(val)
    parsed = get_resp_json(f"04_time_type_{key}", b)
    tt_results[key] = parsed

# time_type without from_date/to_date
print("\n=== 4b. time_type without from_date/to_date ===")
tt_nodates_results = {}
for val in ["today", "yesterday", "all", "7d", "30d", "custom"]:
    b = copy.deepcopy(BASELINE)
    b["time_type"] = val
    b.pop("from_date", None)
    b.pop("to_date", None)
    parsed = get_resp_json(f"04b_time_type_nodates_{val}", b)
    tt_nodates_results[val] = parsed

# ---------- 5. time_unit variations ----------
print("\n=== 5. time_unit ===")
tu_variants = ["minute", "hour", "day", "week", "month", "garbage", None]
tu_results = {}
for val in tu_variants:
    b = copy.deepcopy(BASELINE)
    b["time_unit"] = val
    key = str(val)
    parsed = get_resp_json(f"05_time_unit_{key}", b)
    tu_results[key] = parsed

# ---------- 6. time_period variations ----------
print("\n=== 6. time_period ===")
tp_variants = [1, 2, 3, 7, 0, -1, 100, "1", None, 1.5]
tp_results = {}
for val in tp_variants:
    b = copy.deepcopy(BASELINE)
    b["time_period"] = val
    key = str(val)
    parsed = get_resp_json(f"06_time_period_{key}", b)
    tp_results[key] = parsed

# combine time_unit + time_period
print("\n=== 6b. time_unit + time_period combos ===")
combo_results = {}
for tu in ["hour", "week"]:
    for tp in [1, 2, 7]:
        b = copy.deepcopy(BASELINE)
        b["time_unit"] = tu
        b["time_period"] = tp
        parsed = get_resp_json(f"06b_combo_{tu}_{tp}", b)
        combo_results[f"{tu}_{tp}"] = parsed

# ---------- 7. timezone variations ----------
print("\n=== 7. timezone ===")
tz_variants = ["America/New_York", "UTC", "Asia/Tokyo", "Pacific/Kiritimati", "garbage/Zone", None]
tz_results = {}
for val in tz_variants:
    b = copy.deepcopy(BASELINE)
    b["timezone"] = val
    key = str(val).replace("/", "_")
    parsed = get_resp_json(f"07_timezone_{key}", b)
    tz_results[key] = parsed
# omitted
tz_results["omitted"] = get_resp_json("07_timezone_omitted", {k:v for k,v in BASELINE.items() if k != "timezone"})

# ---------- 8. Unknown/extra fields ----------
print("\n=== 8. extra/unknown fields ===")
extra_variants = {
    "junk_keys": {"group_by":"agent","limit":5,"foo":"bar"},
    "group_by_agent": {"group_by":"agent"},
    "granularity": {"granularity":"hour"},
    "breakdown": {"breakdown":"agent"},
    "limit_offset_page": {"limit":5,"offset":0,"page":1},
    "sort": {"sort":"asc"},
    "metrics": {"metrics":["resolved"]},
    "agent_id": {"agent_id":"agent-1"},
    "user_id": {"user_id":"user-1"},
    "include": {"include":["agents"]},
    "scope": {"scope":{"type":"agent","id":"agent-1"}},
}
extra_results = {}
for name, extra in extra_variants.items():
    b = copy.deepcopy(BASELINE)
    b.update(extra)
    parsed = get_resp_json(f"08_extra_{name}", b)
    extra_results[name] = parsed

# ---------- 9. Wrong types on dates ----------
print("\n=== 9. date type/format variations ===")
date_variants = {
    "from_date_no_time": "2026-07-10",
    "from_date_word_yesterday": "yesterday",
    "from_date_epoch_int": 1752120000,
}
date_results = {}
for name, val in date_variants.items():
    b = copy.deepcopy(BASELINE)
    b["from_date"] = val
    parsed = get_resp_json(f"09_{name}", b)
    date_results[name] = parsed

# to_date before from_date
b = copy.deepcopy(BASELINE)
b["from_date"], b["to_date"] = BASELINE["to_date"], BASELINE["from_date"]
date_results["to_before_from"] = get_resp_json("09_to_before_from", b)

# identical dates
b = copy.deepcopy(BASELINE)
b["to_date"] = b["from_date"]
date_results["identical_dates"] = get_resp_json("09_identical_dates", b)

# null dates
b = copy.deepcopy(BASELINE)
b["from_date"] = None
date_results["from_date_null"] = get_resp_json("09_from_date_null", b)
b = copy.deepcopy(BASELINE)
b["to_date"] = None
date_results["to_date_null"] = get_resp_json("09_to_date_null", b)

# ---------- 10. Method / content-type ----------
print("\n=== 10. method/content-type ===")
do_request("10_GET", body=None, method="GET")
do_request("10_PUT", body=BASELINE, method="PUT")
do_request("10_DELETE", body=None, method="DELETE")

# form-encoded
form_headers = dict(HEADERS)
form_headers["Content-Type"] = "application/x-www-form-urlencoded"
try:
    resp = client.post(URL, data={"community_id":"demo-community"}, headers=form_headers)
    save_raw("10_form_encoded", resp)
    print(f"[10_form_encoded] status={resp.status_code}")
    results.append({"name":"10_form_encoded","status":resp.status_code,"body_snippet":resp.text[:500]})
except Exception as e:
    print(f"[10_form_encoded] EXCEPTION {e}")

# malformed JSON
try:
    resp = client.post(URL, content='{"community_id": "demo-community", BAD JSON', headers=HEADERS)
    save_raw("10_malformed_json", resp)
    print(f"[10_malformed_json] status={resp.status_code}")
    results.append({"name":"10_malformed_json","status":resp.status_code,"body_snippet":resp.text[:500]})
except Exception as e:
    print(f"[10_malformed_json] EXCEPTION {e}")

# ---------- Save everything ----------
with open(os.path.join(EVDIR, "_summary.json"), "w") as f:
    json.dump({
        "baseline": base_json,
        "results_log": results,
        "event_types": et_results,
        "community_id": cid_results,
        "time_type": tt_results,
        "time_type_nodates": tt_nodates_results,
        "time_unit": tu_results,
        "time_period": tp_results,
        "time_unit_period_combo": combo_results,
        "timezone": tz_results,
        "extra_fields": extra_results,
        "date_variants": date_results,
    }, f, indent=2, default=str)

print("\nDONE. Summary written to", os.path.join(EVDIR, "_summary.json"))
