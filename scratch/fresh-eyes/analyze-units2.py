import json, math

D = "/home/timop/work/loopai/scratch/fresh-eyes"
d = json.load(open(f"{D}/raw-units-daily.json"))

TIME_METRICS = [
    "resolve_time", "response_time", "time_to_first_reply",
    "resolve_time_business_hours", "response_time_business_hours",
    "time_to_first_reply_business_hours", "handle_time",
]


def frac_dist(x):
    return abs(x - round(x))


# CORRECTED near-integer test: guard against trivial "rounds to 0" artifacts by
# requiring the tested integer candidate to be >= 1 (i.e. x*mult >= 0.5).
def collect(vals_with_metric):
    out = {}
    for mult, label in [(1, "x1"), (60, "x60"), (3600, "x3600"), (1000, "x1000"),
                         (1/60, "div60"), (1/3600, "div3600")]:
        dists = []
        skipped_trivial = 0
        for m, v in vals_with_metric:
            y = v * mult
            if abs(round(y)) < 1:  # would trivially round to 0 -- not evidence of anything
                skipped_trivial += 1
                continue
            dists.append(frac_dist(y))
        out[label] = (dists, skipped_trivial)
    return out


bucket_vals = [(m, v) for m in TIME_METRICS for v in d[m] if v != 0]
actor_vals = [(f"actor:{m}", v) for act in d["actors"] for m in TIME_METRICS if m in act for v in act[m] if v != 0]

print(f"bucket-level nonzero samples: {len(bucket_vals)}")
print(f"actor-level nonzero samples: {len(actor_vals)}")

for label_set, vals in [("BUCKET-LEVEL", bucket_vals), ("ACTOR-LEVEL", actor_vals), ("COMBINED", bucket_vals + actor_vals)]:
    print(f"\n--- {label_set} (n={len(vals)}) ---")
    res = collect(vals)
    for mult_label, (dists, skipped) in res.items():
        if not dists:
            print(f"  {mult_label:8s}: all trivial, skipped={skipped}")
            continue
        near01 = sum(1 for x in dists if x < 0.01)
        near001 = sum(1 for x in dists if x < 0.001)
        mean_d = sum(dists) / len(dists)
        print(f"  {mult_label:8s}: n_valid={len(dists)} skipped_trivial={skipped} "
              f"mean_frac_dist={mean_d:.5f} frac<0.01={near01}/{len(dists)}={near01/len(dists):.3f} "
              f"frac<0.001={near001}/{len(dists)}={near001/len(dists):.3f}")

print()
print("Per-metric breakdown (bucket-level only, all 6 multiplier hypotheses):")
for m in TIME_METRICS:
    vals = [(m, v) for v in d[m] if v != 0]
    print(f"\n  {m} (n={len(vals)}):")
    res = collect(vals)
    for mult_label, (dists, skipped) in res.items():
        if not dists:
            print(f"    {mult_label:8s}: all trivial, skipped={skipped}")
            continue
        near01 = sum(1 for x in dists if x < 0.01)
        mean_d = sum(dists) / len(dists)
        print(f"    {mult_label:8s}: n_valid={len(dists)} mean_frac_dist={mean_d:.5f} frac<0.01={near01}/{len(dists)}")

# Direct magnitude sanity check: interpret resolve_time under each unit hypothesis
print()
print("=" * 90)
print("Magnitude plausibility check for resolve_time day0=9384.0846, response_time day0=17634.15, handle_time day0=7.989")
print("=" * 90)
for name, v in [("resolve_time_day0", 9384.084580277779), ("response_time_day0", 17634.150968333335),
                ("handle_time_day0", 7.989141388888889), ("resolve_time_biz_day0", 6376.1608)]:
    print(f"{name} = {v}")
    print(f"   as SECONDS -> {v/60:.2f} min = {v/3600:.4f} hours")
    print(f"   as MINUTES -> {v:.2f} min = {v/60:.4f} hours")
    print(f"   as HOURS   -> {v:.2f} hours = {v*60:.1f} min (implausible if large)")
