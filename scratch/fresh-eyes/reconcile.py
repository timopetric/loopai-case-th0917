import json, os

OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"
with open(os.path.join(OUTDIR, "raw-known-good.json")) as f:
    d = json.load(f)

top_keys = list(d.keys())
print("TOP KEYS:", top_keys)

actor0 = d["actors"][0]
mbox0 = d["mailbox"][0]
print("\nACTOR KEYS:", list(actor0.keys()))
print("\nMAILBOX KEYS:", list(mbox0.keys()))

breakdown_only_keys = ["labels", "topics", "categories"]
metric_keys = [k for k in top_keys if isinstance(d[k], list) and k not in ("ticks","actors","mailbox") and k not in breakdown_only_keys]
print("\nMETRIC-LIKE TOP KEYS:", metric_keys)
print("EMPTY BREAKDOWN-ONLY KEYS (not in actor/mailbox):", {k: d[k] for k in breakdown_only_keys})

# which have _count companions
count_keys = [k for k in metric_keys if k.endswith("_count")]
base_with_count = [k[:-6] for k in count_keys]
print("\n_count companion keys:", count_keys)
print("base metrics with _count:", base_with_count)
print("metrics WITHOUT _count:", [k for k in metric_keys if k not in count_keys and k not in base_with_count])

n = len(d["ticks"]) - 1
print(f"\nnum buckets (ticks-1) = {n}")

def check_len(obj, name):
    for k in metric_keys:
        v = obj.get(k)
        if v is None:
            print(f"  {name}: MISSING key {k}")
        elif len(v) != n:
            print(f"  {name}: key {k} has len {len(v)} != {n}")

print("\n--- length checks actors ---")
for a in d["actors"]:
    check_len(a, a.get("id"))
print("--- length checks mailbox ---")
for m in d["mailbox"]:
    check_len(m, m.get("id"))
print("(no output above = all lengths match)")

# RECONCILIATION: sum per-actor vs top-level, per metric, per-bucket and total
print("\n=== RECONCILIATION: actors vs top-level ===")
for k in metric_keys:
    top = d[k]
    summed = [0]*n
    for a in d["actors"]:
        vals = a.get(k, [0]*n)
        for i in range(n):
            summed[i] += vals[i]
    total_top = sum(top)
    total_sum = sum(summed)
    per_bucket_resid = [summed[i]-top[i] for i in range(n)]
    max_resid = max(abs(x) for x in per_bucket_resid)
    pct = (abs(total_sum-total_top)/total_top*100) if total_top else float('nan')
    print(f"{k}: total_top={total_top} total_actorsum={total_sum} resid={total_sum-total_top} pct={pct:.4f}% max_per_bucket_resid={max_resid}")

print("\n=== RECONCILIATION: mailbox vs top-level ===")
for k in metric_keys:
    top = d[k]
    summed = [0]*n
    for m in d["mailbox"]:
        vals = m.get(k, [0]*n)
        for i in range(n):
            summed[i] += vals[i]
    total_top = sum(top)
    total_sum = sum(summed)
    per_bucket_resid = [summed[i]-top[i] for i in range(n)]
    max_resid = max(abs(x) for x in per_bucket_resid)
    pct = (abs(total_sum-total_top)/total_top*100) if total_top else float('nan')
    print(f"{k}: total_top={total_top} total_mailboxsum={total_sum} resid={total_sum-total_top} pct={pct:.4f}% max_per_bucket_resid={max_resid}")

print("\n=== actors total vs mailbox total (do they agree with each other) ===")
for k in metric_keys:
    ta = sum(sum(a.get(k,[0]*n)) for a in d["actors"])
    tm = sum(sum(m.get(k,[0]*n)) for m in d["mailbox"])
    print(f"{k}: actors_total={ta} mailbox_total={tm} diff={ta-tm}")

# empty breakdown check for labels/topics/categories
print("\nlabels:", d.get("labels"))
print("topics:", d.get("topics"))
print("categories:", d.get("categories"))

# check for actor/mailbox singular vs plural extra keys
print("\nHas 'actor' key (singular)?", "actor" in d)
print("Has 'mailboxes' key (plural)?", "mailboxes" in d)
