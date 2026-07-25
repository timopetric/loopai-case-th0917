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

# time_period as string "1" isolated
b = copy.deepcopy(BASELINE); b["time_period"] = "1"
req("F1_time_period_string_1", b)

# time_period as string "abc" (garbage string)
b = copy.deepcopy(BASELINE); b["time_period"] = "abc"
req("F2_time_period_string_abc", b)

# from_date very old
b = copy.deepcopy(BASELINE); b["from_date"] = "1900-01-01T00:00:00.000Z"
req("F3_from_date_1900", b)

# from_date far future
b = copy.deepcopy(BASELINE); b["from_date"] = "2999-01-01T00:00:00.000Z"
req("F4_from_date_2999", b)

# from_date garbage non-date string
b = copy.deepcopy(BASELINE); b["from_date"] = "not-a-date-at-all"
req("F5_from_date_garbage_string", b)

# from_date as number (not epoch-like, random int)
b = copy.deepcopy(BASELINE); b["from_date"] = 42
req("F6_from_date_int_42", b)

# from_date as boolean
b = copy.deepcopy(BASELINE); b["from_date"] = True
req("F7_from_date_bool", b)

# community_id as object/array (wrong type)
b = copy.deepcopy(BASELINE); b["community_id"] = {"a": 1}
req("F8_community_id_object", b)
b = copy.deepcopy(BASELINE); b["community_id"] = [1,2,3]
req("F9_community_id_array", b)

# time_type as object
b = copy.deepcopy(BASELINE); b["time_type"] = {"a": 1}
req("F10_time_type_object", b)

# filters non-empty garbage
b = copy.deepcopy(BASELINE); b["filters"] = [{"field": "bogus_field", "op": "eq", "value": "x"}]
req("F11_filters_garbage", b)

# omit from_date but keep everything else, check exact same error regardless of other missing fields combo
b = {"from_date_ONLY_present": True}
req("F12_only_junk", b)

# empty string from_date
b = copy.deepcopy(BASELINE); b["from_date"] = ""
req("F13_from_date_empty_string", b)
