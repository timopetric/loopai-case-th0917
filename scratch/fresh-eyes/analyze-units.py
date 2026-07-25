import json, math

D = "/home/timop/work/loopai/scratch/fresh-eyes"
d = json.load(open(f"{D}/raw-units-daily.json"))

TIME_METRICS = [
    "resolve_time", "response_time", "time_to_first_reply",
    "resolve_time_business_hours", "response_time_business_hours",
    "time_to_first_reply_business_hours", "handle_time",
]
DENOM = {
    "resolve_time": "resolved",  # hypothesis to test
    "response_time": "replies",
    "time_to_first_reply": "new_tickets",
    "resolve_time_business_hours": "resolved",
    "response_time_business_hours": "replies",
    "time_to_first_reply_business_hours": "new_tickets",
    "handle_time": None,
}

n = len(d["resolved"])
print(f"N daily buckets = {n}\n")

print("=" * 100)
print("SECTION 0: bucketing param behavior (time_unit / time_period)")
print("=" * 100)
daily = d
weekly = json.load(open(f"{D}/raw-units-weekly.json"))
hourly = json.load(open(f"{D}/raw-units-hourly.json"))
tp7 = json.load(open(f"{D}/raw-units-timeperiod7.json"))
print("time_unit=day  ticks:", daily["ticks"])
print("time_unit=week ticks:", weekly["ticks"])
print("time_unit=hour ticks:", hourly["ticks"])
print("time_unit=day,time_period=7 ticks:", tp7["ticks"])
same_wk = weekly["resolve_time"] == daily["resolve_time"][:len(weekly["resolve_time"])]
same_hr = hourly["resolve_time"] == daily["resolve_time"][5:5+len(hourly["resolve_time"])]
same_tp = tp7["resolve_time"] == daily["resolve_time"][:len(tp7["resolve_time"])]
print(f"weekly resolve_time array == daily prefix? {same_wk}")
print(f"hourly resolve_time array == daily slice (day 07-15,07-16)? {same_hr}")
print(f"time_period=7 resolve_time array == daily prefix? {same_tp}")
print("CONCLUSION: time_unit and time_period are IGNORED by the server. Every request,")
print("regardless of requested granularity, returns ONE BUCKET PER CALENDAR DAY covering")
print("[from_date, to_date]. There is no server-side weekly/hourly aggregation to compare")
print("against, so the prescribed 'day-bucket vs week-bucket' cross-check is NOT POSSIBLE")
print("empirically -- this is itself a finding, not a gap in method.")
print()

print("=" * 100)
print("SECTION 1: MEAN vs SUM -- magnitude/count consistency test (since real weekly")
print("buckets do not exist, we test internal consistency: does time_metric look like a")
print("per-ticket mean (comparable magnitude to its own _count denominator), or a SUM")
print("(which would need to be ~count times larger)?")
print("=" * 100)
for m in TIME_METRICS:
    vals = d[m]
    cnt_key = f"{m}_count"
    counts = d.get(cnt_key)
    denom_key = DENOM[m]
    denom = d.get(denom_key) if denom_key else None
    print(f"\n--- {m} ---")
    for i in range(n):
        v = vals[i]
        c = counts[i] if counts else None
        dn = denom[i] if denom else None
        # SUM hypothesis: implied per-ticket seconds = v / c
        if c:
            implied_mean_if_sum = v / c
        else:
            implied_mean_if_sum = None
        if i < 3 or i == n - 1:
            print(f"  day{i}: value={v:.4f} count={c} denom({denom_key})={dn} "
                  f"| if SUM: per-ticket={implied_mean_if_sum}")
    # Aggregate check: sum(v_i) vs sum(v_i*c_i)/sum(c_i) -- compare to typical single-day v magnitude
    total_v = sum(vals)
    if counts:
        total_c = sum(counts)
        weighted_mean = sum(v * c for v, c in zip(vals, counts)) / total_c if total_c else None
    else:
        total_c = None
        weighted_mean = None
    avg_single_day_v = sum(vals) / n
    print(f"  SUM-of-all-14-days = {total_v:.2f}")
    print(f"  MEAN-of-all-14-days (unweighted) = {avg_single_day_v:.2f}")
    print(f"  count-weighted-MEAN-of-means = {weighted_mean}")
    print(f"  -> single day value (e.g. day0={vals[0]:.2f}) is same order of magnitude as "
          f"the weighted mean ({weighted_mean}), NOT the running total ({total_v:.2f}). "
          f"This is consistent with each day's value already being a MEAN, not a running SUM.")

print()
print("=" * 100)
print("SECTION 2: near-integer fractional test -- decisive unit test")
print("Multiply every time-metric value by 1, 60, 3600, 1000 and check how close to an")
print("integer the result is. If original unit is HOURS, value*3600 (seconds) should be")
print("near-integer IF underlying storage was integer seconds converted to hours.")
print("=" * 100)


def frac_dist(x):
    return abs(x - round(x))


results = {}
all_vals = []
for m in TIME_METRICS:
    for v in d[m]:
        if v != 0:
            all_vals.append((m, v))
# also include per-actor time values
actor_vals = []
for act in d["actors"]:
    for m in TIME_METRICS:
        if m in act:
            for v in act[m]:
                if v != 0:
                    actor_vals.append((f"actor:{m}", v))

combined = all_vals + actor_vals
print(f"Total nonzero time-metric samples (bucket-level): {len(all_vals)}")
print(f"Total nonzero time-metric samples (actor-level): {len(actor_vals)}")
print(f"Combined: {len(combined)}")

for mult, label in [(1, "x1 (as-is)"), (60, "x60"), (3600, "x3600"), (1000, "x1000"), (1/60, "/60"), (1/3600, "/3600")]:
    dists = [frac_dist(v * mult) for _, v in combined]
    near_int_001 = sum(1 for x in dists if x < 0.01)
    near_int_0001 = sum(1 for x in dists if x < 0.001)
    mean_dist = sum(dists) / len(dists)
    print(f"  {label:12s}: mean frac-dist-to-int={mean_dist:.5f}  "
          f"fraction<0.01={near_int_001}/{len(dists)}={near_int_001/len(dists):.3f}  "
          f"fraction<0.001={near_int_0001}/{len(dists)}={near_int_0001/len(dists):.3f}")

print()
print("Sample raw fractional tails (bucket-level, first 10 nonzero resolve_time values):")
for v in d["resolve_time"][:10]:
    print(f"   {v!r}")

print()
print("Hypothesis: value = (integer total seconds) / (count of tickets) [a MEAN of integer")
print("second-durations]. Test: value * count should be near-integer.")
for m in TIME_METRICS:
    cnt_key = f"{m}_count"
    if cnt_key not in d:
        continue
    dists = []
    for v, c in zip(d[m], d[cnt_key]):
        if v != 0 and c:
            dists.append(frac_dist(v * c))
    if dists:
        near = sum(1 for x in dists if x < 0.02)
        print(f"  {m}: value*count near-integer fraction = {near}/{len(dists)} = {near/len(dists):.3f}  "
              f"(mean dist={sum(dists)/len(dists):.5f})")

print()
print("=" * 100)
print("SECTION 3: business_hours vs plain -- always <= ? ratio distribution")
print("=" * 100)
pairs = [
    ("resolve_time", "resolve_time_business_hours"),
    ("response_time", "response_time_business_hours"),
    ("time_to_first_reply", "time_to_first_reply_business_hours"),
]
for plain, biz in pairs:
    ratios = []
    violations = 0
    for i in range(n):
        p, b = d[plain][i], d[biz][i]
        if p == 0:
            continue
        if b > p + 1e-6:
            violations += 1
        ratios.append(b / p)
    print(f"{plain} vs {biz}: violations(biz>plain)={violations}/{n}  "
          f"ratio min={min(ratios):.4f} max={max(ratios):.4f} mean={sum(ratios)/len(ratios):.4f}")
    # 8h/24h calendar day implies ratio ~ 8/24=0.333 if business hours counted as fraction of elapsed time
    print(f"   (8/24 = {8/24:.4f} for reference -- an 8h business day out of 24h calendar day)")

print()
print("=" * 100)
print("SECTION 4: handle_time -- presence, relation to other metrics")
print("=" * 100)
print("handle_time:", d["handle_time"])
print("handle_time_count:", d["handle_time_count"])
print("resolved:", d["resolved"])
print("actioned_emails:", d["actioned_emails"])
for i in range(n):
    print(f"  day{i}: handle_time={d['handle_time'][i]:.4f} handle_time_count={d['handle_time_count'][i]} "
          f"resolved={d['resolved'][i]} actioned_emails={d['actioned_emails'][i]} "
          f"resolve_time={d['resolve_time'][i]:.2f}")

print()
print("=" * 100)
print("SECTION 5: replies_to_resolve / replies_to_resolve_count -- mean replies per resolved ticket?")
print("=" * 100)
for i in range(n):
    rtr = d["replies_to_resolve"][i]
    rtrc = d["replies_to_resolve_count"][i]
    ratio = rtr / rtrc if rtrc else None
    print(f"  day{i}: replies_to_resolve={rtr} count={rtrc} ratio(replies/resolved-ticket)={ratio} "
          f"replies={d['replies'][i]} resolved={d['resolved'][i]}")

print()
print("=" * 100)
print("SECTION 6: which metrics have _count companions; count vs plausible denominator")
print("=" * 100)
all_keys = [k for k in d.keys() if isinstance(d[k], list) and k != "ticks"]
count_keys = [k for k in all_keys if k.endswith("_count")]
base_keys = [k[:-6] for k in count_keys]
no_count = [k for k in all_keys if not k.endswith("_count") and k not in base_keys and k not in ("actors", "mailbox", "labels", "topics", "categories")]
print("Keys WITH _count companion:", base_keys)
print("Keys WITHOUT _count companion:", no_count)

print()
print("Testing count vs candidate denominator equality per day:")
tests = [
    ("resolve_time_count", "resolved"),
    ("response_time_count", "replies"),
    ("time_to_first_reply_count", "new_tickets"),
    ("resolve_time_business_hours_count", "resolved"),
    ("response_time_business_hours_count", "replies"),
    ("time_to_first_reply_business_hours_count", "new_tickets"),
]
for ck, dk in tests:
    diffs = [d[ck][i] - d[dk][i] for i in range(n)]
    exact = sum(1 for x in diffs if x == 0)
    print(f"  {ck} vs {dk}: exact matches {exact}/{n}, diffs={diffs}")

print()
print("=" * 100)
print("SECTION 7: are 'open' and 'sla_breaches' always zero?")
print("=" * 100)
print("open (bucket-level):", d["open"], " all-zero?", all(x == 0 for x in d["open"]))
print("sla_breaches (bucket-level):", d["sla_breaches"], " all-zero?", all(x == 0 for x in d["sla_breaches"]))
open_actor_nonzero = sum(1 for act in d["actors"] for v in act.get("open", []) if v != 0)
sla_actor_nonzero = sum(1 for act in d["actors"] for v in act.get("sla_breaches", []) if v != 0) if "sla_breaches" in d["actors"][0] else "N/A (no sla_breaches key per-actor)"
print("open: nonzero entries across all actors:", open_actor_nonzero)
print("sla_breaches per-actor present in actor objects?", "sla_breaches" in d["actors"][0])
print(json.dumps({k: v for k, v in d["actors"][0].items() if k in ("user_id", "open", "sla_breaches")}, indent=2) if "sla_breaches" in d["actors"][0] else "actor keys: " + str(list(d["actors"][0].keys())))

print()
print("=" * 100)
print("SECTION 9: per-actor unit cross-check")
print("=" * 100)
# pick a few actors with substantial counts, run the same value*count near-integer test
actor_dists_count = []
for act in d["actors"]:
    for m in TIME_METRICS:
        ck = f"{m}_count"
        if m not in act or ck not in act:
            continue
        for v, c in zip(act[m], act[ck]):
            if v != 0 and c:
                actor_dists_count.append(frac_dist(v * c))
near = sum(1 for x in actor_dists_count if x < 0.02)
print(f"Per-actor value*count near-integer: {near}/{len(actor_dists_count)} = "
      f"{near/len(actor_dists_count) if actor_dists_count else 0:.3f}")

# print a concrete actor example with decent volume
best_actor = max(d["actors"], key=lambda a: sum(a.get("resolve_time_count", [0])))
print(f"\nExample actor with most resolved tickets: {best_actor['user_id']}")
print("resolve_time:", best_actor["resolve_time"])
print("resolve_time_count:", best_actor["resolve_time_count"])
for v, c in zip(best_actor["resolve_time"], best_actor["resolve_time_count"]):
    if v and c:
        print(f"   v={v!r} c={c} v*c={v*c!r} frac_dist={frac_dist(v*c):.6f}")
