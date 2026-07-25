#!/usr/bin/env python3
"""
Probe scope/filters behavior of the reporting API.
Run with: cd /home/timop/work/loopai && uv run scratch/fresh-eyes/probe-scope-filters.py
"""
import httpx
import json
import hashlib
import copy
import os
import time

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {
    "Authorization": "Bearer any-token-works",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"
EVDIR = os.path.join(OUTDIR, "evidence-scope")
os.makedirs(EVDIR, exist_ok=True)

BASE_BODY = {
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

METRIC_ARRAY_KEYS = [
    "ticks", "actioned_emails", "resolved", "new_tickets", "open", "replies",
    "new_emails", "replies_to_resolve", "replies_to_resolve_count",
    "resolve_time", "resolve_time_count", "response_time", "response_time_count",
    "time_to_first_reply", "time_to_first_reply_count",
    "resolve_time_business_hours", "resolve_time_business_hours_count",
    "response_time_business_hours", "response_time_business_hours_count",
    "time_to_first_reply_business_hours", "time_to_first_reply_business_hours_count",
    "handle_time", "handle_time_count", "sla_breaches",
]

client = httpx.Client(timeout=30)


def call(body, label):
    r = client.post(URL, headers=HEADERS, json=body)
    fname = os.path.join(EVDIR, f"{label}.json")
    result = {
        "status_code": r.status_code,
        "label": label,
        "request_body": body,
    }
    try:
        data = r.json()
        result["response"] = data
    except Exception as e:
        result["response_text"] = r.text
        result["parse_error"] = str(e)
    with open(fname, "w") as f:
        json.dump(result, f, indent=2)
    return r.status_code, result.get("response"), r.text


def resp_hash(resp_or_text):
    if isinstance(resp_or_text, (dict, list)):
        s = json.dumps(resp_or_text, sort_keys=True)
    else:
        s = str(resp_or_text)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def sum_metric_arrays(resp):
    """Sum each top-level metric array to a scalar for quick diffing."""
    out = {}
    if not isinstance(resp, dict):
        return out
    for k in METRIC_ARRAY_KEYS:
        v = resp.get(k)
        if isinstance(v, list):
            nums = [x for x in v if isinstance(x, (int, float))]
            out[k] = sum(nums) if nums else None
        else:
            out[k] = v
    return out


def breakdown_ids(resp, key):
    if not isinstance(resp, dict):
        return []
    arr = resp.get(key)
    if not isinstance(arr, list):
        return []
    ids = []
    for item in arr:
        if isinstance(item, dict):
            ids.append(item.get("id") or item.get("mailbox_id") or item.get("user_id"))
    return sorted(x for x in ids if x)


results_log = []


def run_case(label, body, notes=""):
    status, resp, text = call(body, label)
    h = resp_hash(resp if resp is not None else text)
    sums = sum_metric_arrays(resp) if isinstance(resp, dict) else {}
    actor_ids = breakdown_ids(resp, "actors")
    mailbox_ids = breakdown_ids(resp, "mailbox")
    row = {
        "label": label,
        "status": status,
        "hash": h,
        "sums": sums,
        "n_actors": len(actor_ids),
        "n_mailbox": len(mailbox_ids),
        "actor_ids": actor_ids,
        "mailbox_ids": mailbox_ids,
        "notes": notes,
    }
    results_log.append(row)
    print(f"{label:45s} status={status} hash={h} n_actors={row['n_actors']} n_mailbox={row['n_mailbox']} resolved_sum={sums.get('resolved')} ticks_sum={sums.get('ticks') if not isinstance(sums.get('ticks'), list) else 'n/a'}")
    return row


# ---------------------------------------------------------------
# STEP 1 handled separately after baseline is captured (harvest entities)
# ---------------------------------------------------------------

print("=== BASELINE (no scope) ===")
baseline = run_case("baseline_no_scope", copy.deepcopy(BASE_BODY), "no scope key at all")

# Harvest full entity universe from baseline
if isinstance(baseline["sums"], dict):
    pass

baseline_resp = json.load(open(os.path.join(EVDIR, "baseline_no_scope.json")))["response"]
all_actors = [{"id": a.get("id"), "name": a.get("name")} for a in baseline_resp.get("actors", [])]
all_mailboxes = [{"id": m.get("id"), "name": m.get("name")} for m in baseline_resp.get("mailbox", [])]

with open(os.path.join(OUTDIR, "harvested-actors.json"), "w") as f:
    json.dump(all_actors, f, indent=2)
with open(os.path.join(OUTDIR, "harvested-mailboxes.json"), "w") as f:
    json.dump(all_mailboxes, f, indent=2)

print(f"\nHarvested {len(all_actors)} actors, {len(all_mailboxes)} mailboxes -> saved to harvested-actors.json / harvested-mailboxes.json")

documented_sample_ids = [
    "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T",
    "ACqMGljMqLCOAZJ9ZYNz4oNZkF91D0T",
    "ACpw3ge04EDYzOsUMhVHgYGqpn2wq0T",
    "ACn0hYoSiro8YwtJVsN48DFDtyHyQ0T",
    "ACSzkQ6eDUuigSwb0AFR4r7Z19wog0T",
]
real_mailbox_ids = set(m["id"] for m in all_mailboxes)
doc_ids_present = {i: (i in real_mailbox_ids) for i in documented_sample_ids}
print("Documented sample mailbox ids present in real data:", doc_ids_present)

real_mailbox_ids_list = sorted(real_mailbox_ids)
real_actor_ids_list = sorted(a["id"] for a in all_actors if a.get("id"))

one_mailbox = all_mailboxes[0]
three_mailboxes = all_mailboxes[:3]

# ---------------------------------------------------------------
# STEP 2: does scope filter totals?
# ---------------------------------------------------------------
print("\n=== STEP 2: scope filtering totals ===")

def scope_body(scope_obj):
    b = copy.deepcopy(BASE_BODY)
    b["scope"] = scope_obj
    return b

run_case("scope_one_mailbox", scope_body({
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}), f"scope=exactly one real mailbox ({one_mailbox['name']})")

run_case("scope_three_mailboxes", scope_body({
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": m["id"], "name": m["name"]} for m in three_mailboxes]
}), "scope=3 real mailboxes")

run_case("scope_all_mailboxes", scope_body({
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": m["id"], "name": m["name"]} for m in all_mailboxes]
}), "scope=ALL real mailboxes")

# ---------------------------------------------------------------
# STEP 4: nonsense scope variants
# ---------------------------------------------------------------
print("\n=== STEP 4: nonsense scope variants ===")

run_case("scope_fabricated_id", scope_body({
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": "FAKE_MAILBOX_ID_DOES_NOT_EXIST", "name": "Nonexistent"}]
}), "fabricated mailbox id")

run_case("scope_empty_values", scope_body({
    "id": "mailboxes", "operator": {"id": "is"}, "values": []
}), "empty values array")

run_case("scope_name_only_no_id", scope_body({
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"name": one_mailbox["name"]}]
}), "values with only name, no id")

run_case("scope_as_array", [{
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}], "scope as ARRAY of objects (body['scope'] = [obj])")
# NOTE: run_case calls scope_body normally; for this one we bypass helper:
_b = copy.deepcopy(BASE_BODY)
_b["scope"] = [{
    "id": "mailboxes", "operator": {"id": "is"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}]
run_case("scope_as_array_v2", _b, "scope as ARRAY of one scope object")

run_case("scope_user_real_actor", scope_body({
    "id": "user", "operator": {"id": "is"},
    "values": [{"id": real_actor_ids_list[0] if real_actor_ids_list else "user_fake", "name": "x"}]
}), "scope id=user with real actor id")

run_case("scope_allMailboxes", scope_body({
    "id": "allMailboxes", "operator": {"id": "is"}, "values": []
}), "scope id=allMailboxes")

run_case("scope_mailbox_singular", scope_body({
    "id": "mailbox", "operator": {"id": "is"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}), "scope id='mailbox' (singular)")

run_case("scope_privateMailboxes", scope_body({
    "id": "privateMailboxes", "operator": {"id": "is"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}), "scope id=privateMailboxes")

# ---------------------------------------------------------------
# STEP 5: all operators
# ---------------------------------------------------------------
print("\n=== STEP 5: operators ===")
operators = ["is", "is_not", "or", "or_not", "and", "and_not"]
for op in operators:
    run_case(f"scope_operator_{op}", scope_body({
        "id": "mailboxes", "operator": {"id": op},
        "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
    }), f"operator={op} on one mailbox")

run_case("scope_operator_garbage", scope_body({
    "id": "mailboxes", "operator": {"id": "totally_bogus_operator"},
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}), "garbage operator id")

run_case("scope_operator_plain_string", scope_body({
    "id": "mailboxes", "operator": "is",
    "values": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}]
}), "operator as plain string instead of {'id':...}")

# ---------------------------------------------------------------
# STEP 6: filters array with documented filter ids
# ---------------------------------------------------------------
print("\n=== STEP 6: filters[] with documented ids ===")

def filters_body(filter_obj_list):
    b = copy.deepcopy(BASE_BODY)
    b["filters"] = filter_obj_list
    return b

filter_ids_plausible_values = {
    "user": [{"id": real_actor_ids_list[0] if real_actor_ids_list else "user_fake", "name": "x"}],
    "labels": [{"id": "label_fake", "name": "urgent"}],
    "topics": [{"id": "topic_fake", "name": "billing"}],
    "categories": [{"id": "cat_fake", "name": "support"}],
    "allMailboxes": [],
    "mailbox": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}],
    "mailboxes": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}],
    "privateMailboxes": [{"id": one_mailbox["id"], "name": one_mailbox["name"]}],
    "customerEmail": [{"id": "someone@example.com", "name": "someone@example.com"}],
    "customerDomain": [{"id": "example.com", "name": "example.com"}],
    "garbage_filter_id_xyz": [{"id": "whatever", "name": "whatever"}],
}

for fid, vals in filter_ids_plausible_values.items():
    run_case(f"filter_{fid}", filters_body([{
        "id": fid, "operator": {"id": "is"}, "values": vals
    }]), f"filters=[{{id:{fid}}}]")

# ---------------------------------------------------------------
# STEP 7: filter by real actor specifically (user id)
# ---------------------------------------------------------------
print("\n=== STEP 7: filter by real actor (repeat, explicit) ===")
if real_actor_ids_list:
    real_actor = real_actor_ids_list[0]
    run_case("filter_user_real_actor_explicit", filters_body([{
        "id": "user", "operator": {"id": "is"},
        "values": [{"id": real_actor, "name": "RealActor"}]
    }]), f"filters user=is real actor id {real_actor}")
    run_case("filter_user_real_actor_is_not", filters_body([{
        "id": "user", "operator": {"id": "is_not"},
        "values": [{"id": real_actor, "name": "RealActor"}]
    }]), f"filters user=is_not real actor id {real_actor}")

# ---------------------------------------------------------------
# STEP 8: undocumented plausible filter ids
# ---------------------------------------------------------------
print("\n=== STEP 8: undocumented plausible filter ids ===")
undoc_ids = ["agent", "agents", "team", "teams", "tags", "status", "channel", "inbox", "inboxes"]
for fid in undoc_ids:
    run_case(f"filter_undoc_{fid}", filters_body([{
        "id": fid, "operator": {"id": "is"},
        "values": [{"id": "whatever_id", "name": "whatever"}]
    }]), f"undocumented filter id={fid}")

# ---------------------------------------------------------------
# STEP 5 (is/is_not complement check on filters too)
# ---------------------------------------------------------------
print("\n=== is vs is_not complement check ===")
if real_actor_ids_list:
    real_actor = real_actor_ids_list[0]
    is_case = run_case("complement_check_is", scope_body({
        "id": "user", "operator": {"id": "is"},
        "values": [{"id": real_actor, "name": "x"}]
    }), "for complement check: scope user is X")
    is_not_case = run_case("complement_check_is_not", scope_body({
        "id": "user", "operator": {"id": "is_not"},
        "values": [{"id": real_actor, "name": "x"}]
    }), "for complement check: scope user is_not X")
    resolved_is = is_case["sums"].get("resolved")
    resolved_is_not = is_not_case["sums"].get("resolved")
    resolved_baseline = baseline["sums"].get("resolved")
    print(f"resolved: is={resolved_is} is_not={resolved_is_not} sum={ (resolved_is or 0) + (resolved_is_not or 0) } baseline={resolved_baseline}")

# ---------------------------------------------------------------
# STEP 9: exhaustive sweep summary
# ---------------------------------------------------------------
print("\n=== SUMMARY: all hashes ===")
baseline_hash = results_log[0]["hash"]
identical_to_baseline = []
different_from_baseline = []
for row in results_log:
    if row["hash"] == baseline_hash:
        identical_to_baseline.append(row["label"])
    else:
        different_from_baseline.append(row["label"])

print(f"\nTotal cases: {len(results_log)}")
print(f"Identical to baseline hash ({baseline_hash}): {len(identical_to_baseline)}")
for l in identical_to_baseline:
    print(f"  = {l}")
print(f"\nDIFFERENT from baseline: {len(different_from_baseline)}")
for l in different_from_baseline:
    print(f"  != {l}")

# Save full results log
with open(os.path.join(OUTDIR, "scope-filters-results-log.json"), "w") as f:
    json.dump({
        "baseline_hash": baseline_hash,
        "results": results_log,
        "doc_sample_ids_present": doc_ids_present,
        "real_mailbox_ids": real_mailbox_ids_list,
        "real_actor_ids": real_actor_ids_list,
    }, f, indent=2)

print("\nSaved full results log to scratch/fresh-eyes/scope-filters-results-log.json")
