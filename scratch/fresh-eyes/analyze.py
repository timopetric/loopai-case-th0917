import json

d = json.load(open('/home/timop/work/loopai/scratch/fresh-eyes/evidence/_summary.json'))

def tick_summary(obj):
    if obj is None:
        return "None"
    if not isinstance(obj, dict):
        return f"non-dict: {type(obj)}"
    ticks = obj.get("ticks")
    if ticks is None:
        return f"no 'ticks' key; keys={sorted(obj.keys())}"
    return f"len={len(ticks)} first={ticks[0] if ticks else None} last={ticks[-1] if ticks else None}"

def metric_sum(obj, key):
    if not isinstance(obj, dict):
        return None
    v = obj.get(key)
    if isinstance(v, list):
        return sum(x for x in v if isinstance(x, (int,float)))
    return v

print("=== BASELINE ===")
b = d["baseline"]
print("keys:", sorted(b.keys()) if isinstance(b, dict) else b)
print("ticks:", tick_summary(b))
for k in ["resolved","new_tickets","open","actioned_emails"]:
    print(f"  sum({k}) =", metric_sum(b, k))

print("\n=== event_types ===")
for name, obj in d["event_types"].items():
    print(f"-- {name}: keys={sorted(obj.keys()) if isinstance(obj,dict) else obj} ticks={tick_summary(obj)}")
    if isinstance(obj, dict):
        for k in ["resolved","new_tickets"]:
            if k in obj:
                print(f"     sum({k})=", metric_sum(obj,k))

print("\n=== community_id ===")
for name, obj in d["community_id"].items():
    print(f"-- {name}: ticks={tick_summary(obj)} sum(resolved)={metric_sum(obj,'resolved')} sum(new_tickets)={metric_sum(obj,'new_tickets')}")

print("\n=== time_type (with dates held constant) ===")
for name, obj in d["time_type"].items():
    print(f"-- {name}: ticks={tick_summary(obj)} sum(resolved)={metric_sum(obj,'resolved')}")

print("\n=== time_type WITHOUT dates (expect 422 -> None) ===")
for name, obj in d["time_type_nodates"].items():
    print(f"-- {name}: {obj}")

print("\n=== time_unit ===")
for name, obj in d["time_unit"].items():
    print(f"-- {name}: ticks={tick_summary(obj)}")

print("\n=== time_period ===")
for name, obj in d["time_period"].items():
    print(f"-- {name}: ticks={tick_summary(obj)}")

print("\n=== time_unit_period_combo ===")
for name, obj in d["time_unit_period_combo"].items():
    print(f"-- {name}: ticks={tick_summary(obj)}")

print("\n=== timezone ===")
for name, obj in d["timezone"].items():
    print(f"-- {name}: ticks={tick_summary(obj)}")

print("\n=== extra_fields ===")
for name, obj in d["extra_fields"].items():
    print(f"-- {name}: keys={sorted(obj.keys()) if isinstance(obj,dict) else obj} ticks={tick_summary(obj)}")

print("\n=== date_variants ===")
for name, obj in d["date_variants"].items():
    print(f"-- {name}: ticks={tick_summary(obj)}")

print("\n=== full results_log (status codes / errors) ===")
for r in d["results_log"]:
    if r.get("status") and r["status"] != 200:
        print(f"-- {r['name']}: status={r['status']} body={r.get('body_snippet','')[:300]}")
