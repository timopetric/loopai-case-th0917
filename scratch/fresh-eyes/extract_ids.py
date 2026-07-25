import json, os
OUTDIR = "/home/timop/work/loopai/scratch/fresh-eyes"
with open(os.path.join(OUTDIR, "raw-known-good.json")) as f:
    d = json.load(f)

actors = [{"id": a["id"], "user_id": a["user_id"], "name": a["name"]} for a in d["actors"]]
mailboxes = [{"id": m["id"], "mailbox_id": m["mailbox_id"], "name": m["name"]} for m in d["mailbox"]]

with open(os.path.join(OUTDIR, "actors.json"), "w") as f:
    json.dump(actors, f, indent=2)
with open(os.path.join(OUTDIR, "mailboxes.json"), "w") as f:
    json.dump(mailboxes, f, indent=2)

print("num actors:", len(actors))
print("num mailboxes:", len(mailboxes))
# check id == user_id always?
mismatch = [a for a in actors if a["id"] != a["user_id"]]
print("actor id!=user_id mismatches:", len(mismatch), mismatch[:3])
mismatch2 = [m for m in mailboxes if m["id"] != m["mailbox_id"]]
print("mailbox id!=mailbox_id mismatches:", len(mismatch2), mismatch2[:3])
# duplicate names?
from collections import Counter
namesA = Counter(a["name"] for a in actors)
dupA = {k:v for k,v in namesA.items() if v>1}
print("duplicate actor names:", dupA)
namesM = Counter(m["name"] for m in mailboxes)
dupM = {k:v for k,v in namesM.items() if v>1}
print("duplicate mailbox names:", dupM)

# sanity check for _count semantics
n = len(d["ticks"])-1
rt = d["resolve_time"]; rtc = d["resolve_time_count"]; resolved = d["resolved"]
print("\nbucket: resolve_time, resolve_time_count, resolved, ratio(resolve_time/count)")
for i in range(n):
    ratio = rt[i]/rtc[i] if rtc[i] else None
    print(i, rt[i], rtc[i], resolved[i], ratio)
