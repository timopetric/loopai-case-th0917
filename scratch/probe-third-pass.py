"""Third pass: fresh unscoped full-window all-metrics fixture, window-roll check,
per-metric reconciliation across the full unscoped dataset, open/business_hours characterization."""
import sys, json
sys.path.insert(0, "/home/timop/work/loopai/scratch")
from probe_common import call, base_body, ALL_EVENT_TYPES

SCRATCH = "/home/timop/work/loopai/scratch"

TIME_METRICS = [
    "resolve_time", "response_time", "time_to_first_reply",
    "resolve_time_business_hours", "response_time_business_hours",
    "time_to_first_reply_business_hours", "handle_time",
]
COUNT_METRICS = ["actioned_emails", "resolved", "new_tickets", "open", "replies",
                  "new_emails", "replies_to_resolve", "sla_breaches"]
ALL_METRICS = COUNT_METRICS + TIME_METRICS


def main():
    print("### Fresh unscoped, full-window, all-metrics fetch (today) ###")
    body = base_body(
        from_date="2026-07-01T00:00:00.000Z",
        to_date="2026-08-10T00:00:00.000Z",  # deliberately wide, to see if window rolled
        time_unit="day",
        event_types=list(ALL_EVENT_TYPES),
    )
    del body["scope"]  # unscoped -> full mailbox universe
    _, r = call(body, label="fresh unscoped full-window", save_to=f"{SCRATCH}/resp-full-unscoped-latest.json")
    j = r.get("response_json", {})

    ticks = j.get("ticks", [])
    print("ticks:", ticks)
    print("num ticks:", len(ticks))

    # actors / mailboxes lists
    actors = j.get("actors", [])
    mailboxes = j.get("mailbox", [])
    actors_list = [{"user_id": a.get("user_id"), "id": a.get("id"), "name": a.get("name")} for a in actors]
    mailboxes_list = [{"id": m.get("id"), "mailbox_id": m.get("mailbox_id"), "name": m.get("name")} for m in mailboxes]
    with open(f"{SCRATCH}/actors-list.json", "w") as f:
        json.dump(actors_list, f, indent=2)
    with open(f"{SCRATCH}/mailboxes-list.json", "w") as f:
        json.dump(mailboxes_list, f, indent=2)
    print(f"num actors: {len(actors)}  num mailboxes: {len(mailboxes)}")
    print(f"saved actors-list.json, mailboxes-list.json")

    # --- window roll check vs yesterday's saved resp-q1-full-14day.json ---
    print("\n### Window roll check vs yesterday (resp-q1-full-14day.json) ###")
    old = json.load(open(f"{SCRATCH}/resp-q1-full-14day.json"))
    old_ticks = old["response_json"]["ticks"]
    print("yesterday's ticks (pass 1/2, requested 07-10..07-24):", old_ticks)
    print("today's ticks (this fetch, wide request 07-01..08-10):", ticks)
    print("today ticks[0]:", ticks[0] if ticks else None, " ticks[-1]:", ticks[-1] if ticks else None)

    # Also do a narrow request matching yesterday's exact request to compare apples to apples
    body_narrow = base_body(from_date="2026-07-10T04:00:00.000Z", to_date="2026-07-24T03:59:59.999Z", time_unit="day")
    _, r_narrow = call(body_narrow, label="today, same request as pass-1 Q1", save_to=f"{SCRATCH}/resp-q1-rerun-day2.json")
    j_narrow = r_narrow.get("response_json", {})
    print("\ntoday, same exact request as pass-1 Q1 -> ticks:", j_narrow.get("ticks"))
    print("identical to yesterday's saved response (full dict)?:", j_narrow == old["response_json"])
    if j_narrow.get("resolved") != old["response_json"].get("resolved"):
        print("  resolved differs: yesterday=", old["response_json"].get("resolved"), " today=", j_narrow.get("resolved"))
    else:
        print("  resolved identical to yesterday.")

    # --- per-metric reconciliation across FULL unscoped dataset ---
    print("\n### Per-metric reconciliation: top-level total vs sum(actors) vs sum(mailboxes) ###")
    print(f"{'metric':45s} {'top_total':>14s} {'actor_sum':>14s} {'mailbox_sum':>14s} {'actor_match':>12s} {'mb_match':>10s}")
    recon = {}
    for m in ALL_METRICS:
        top = sum(j.get(m, []) or [])
        actor_sum = sum(sum(a.get(m, []) or []) for a in actors)
        mb_sum = sum(sum(mb.get(m, []) or []) for mb in mailboxes)
        actor_match = abs(top - actor_sum) < 1e-6
        mb_match = abs(top - mb_sum) < 1e-6
        recon[m] = {"top": top, "actor_sum": actor_sum, "mailbox_sum": mb_sum,
                     "actor_match": actor_match, "mailbox_match": mb_match}
        print(f"{m:45s} {top:14.4f} {actor_sum:14.4f} {mb_sum:14.4f} {str(actor_match):>12s} {str(mb_match):>10s}")

    # counts too
    print("\n### _count companions reconciliation ###")
    for m in TIME_METRICS:
        cm = f"{m}_count"
        top = sum(j.get(cm, []) or [])
        actor_sum = sum(sum(a.get(cm, []) or []) for a in actors)
        mb_sum = sum(sum(mb.get(cm, []) or []) for mb in mailboxes)
        print(f"{cm:45s} top={top:.4f} actor_sum={actor_sum:.4f} mailbox_sum={mb_sum:.4f} "
              f"actor_match={abs(top-actor_sum)<1e-6} mb_match={abs(top-mb_sum)<1e-6}")

    with open(f"{SCRATCH}/z3-reconciliation.json", "w") as f:
        json.dump(recon, f, indent=2)

    # --- open metric characterization ---
    print("\n### 'open' metric characterization ###")
    print("top-level open:", j.get("open"))
    print("sum:", sum(j.get("open", []) or []))
    nonzero_actors_open = [a["name"] for a in actors if sum(a.get("open", []) or []) != 0]
    print("actors with nonzero open:", nonzero_actors_open[:20], "..." if len(nonzero_actors_open) > 20 else "")
    nonzero_mb_open = [m["name"] for m in mailboxes if sum(m.get("open", []) or []) != 0]
    print("mailboxes with nonzero open:", nonzero_mb_open[:20], "..." if len(nonzero_mb_open) > 20 else "")

    # --- business_hours vs base metric ratio ---
    print("\n### business_hours vs base metric comparison ###")
    pairs = [
        ("resolve_time", "resolve_time_business_hours"),
        ("response_time", "response_time_business_hours"),
        ("time_to_first_reply", "time_to_first_reply_business_hours"),
    ]
    for base, bh in pairs:
        base_total = sum(j.get(base, []) or [])
        bh_total = sum(j.get(bh, []) or [])
        base_count = sum(j.get(f"{base}_count", []) or [])
        bh_count = sum(j.get(f"{bh}_count", []) or [])
        ratio = bh_total / base_total if base_total else None
        print(f"{base}: total={base_total:.3f} count={base_count}  |  {bh}: total={bh_total:.3f} count={bh_count}  |  bh/base ratio={ratio}")
        if base_count and bh_count:
            print(f"    avg {base}={base_total/base_count:.4f}h  avg {bh}={bh_total/bh_count:.4f}h  (business avg {'<' if bh_total/bh_count < base_total/base_count else '>='} total avg)")


if __name__ == "__main__":
    main()
