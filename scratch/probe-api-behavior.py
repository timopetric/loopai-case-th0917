"""Full probe of the reporting API, covering questions 1-7."""
import json
import sys
import copy

sys.path.insert(0, "/home/timop/work/loopai/scratch")
from probe_common import URL, HEADERS, ALL_EVENT_TYPES, MAILBOX_SCOPE, base_body, call

SCRATCH = "/home/timop/work/loopai/scratch"


def q1_full_structure():
    print("\n########## Q1: full response structure (14-day, day bucket) ##########")
    body = base_body(
        from_date="2026-07-10T04:00:00.000Z",
        to_date="2026-07-24T03:59:59.999Z",
        time_unit="day",
    )
    resp, result = call(body, label="Q1 14-day full", save_to=f"{SCRATCH}/resp-q1-full-14day.json")
    j = result.get("response_json", {})
    print("Top-level keys:", list(j.keys()))
    print("num ticks:", len(j.get("ticks", [])))
    actors = j.get("actors", [])
    print(f"num actors: {len(actors)}")
    for a in actors:
        print("  actor:", {k: v for k, v in a.items() if not isinstance(v, list)})
    mailbox = j.get("mailbox") or j.get("mailboxes")
    print("mailbox key present:", "mailbox" in j, "mailboxes key present:", "mailboxes" in j)
    if mailbox:
        print(f"num mailbox entries: {len(mailbox)}")
        for m in mailbox:
            non_list = {k: v for k, v in m.items() if not isinstance(v, list)}
            print("  mailbox entry non-list fields:", non_list)
            # check nesting: does mailbox entry itself contain actors?
            nested_actor_keys = [k for k in m.keys() if "actor" in k.lower()]
            print("  nested actor-like keys in mailbox entry:", nested_actor_keys)
    else:
        print("No mailbox/mailboxes key found at top level.")
    # check if actors have nested mailbox breakdown
    if actors:
        nested_mailbox_keys = [k for k in actors[0].keys() if "mailbox" in k.lower()]
        print("nested mailbox-like keys inside actor[0]:", nested_mailbox_keys)
    return j


def q2_units_mystery():
    print("\n########## Q2: units mystery (day vs hour bucket, 1-day window) ##########")
    metrics = ["handle_time", "resolve_time", "response_time", "time_to_first_reply"]
    day_body = base_body(
        event_types=metrics,
        from_date="2026-07-15T04:00:00.000Z",
        to_date="2026-07-16T03:59:59.999Z",
        time_unit="day",
    )
    hour_body = base_body(
        event_types=metrics,
        from_date="2026-07-15T04:00:00.000Z",
        to_date="2026-07-16T03:59:59.999Z",
        time_unit="hour",
    )
    _, day_result = call(day_body, label="Q2 day-bucket 1-day window", save_to=f"{SCRATCH}/resp-q2-day-bucket.json")
    _, hour_result = call(hour_body, label="Q2 hour-bucket 1-day window", save_to=f"{SCRATCH}/resp-q2-hour-bucket.json")
    dj = day_result.get("response_json", {})
    hj = hour_result.get("response_json", {})
    print("day ticks:", dj.get("ticks"))
    print("hour ticks count:", len(hj.get("ticks", [])))
    for m in metrics:
        dv = dj.get(m)
        hv = hj.get(m)
        dc = dj.get(f"{m}_count")
        hc = hj.get(f"{m}_count")
        print(f"\n-- metric: {m} --")
        print("  day value:", dv, " day_count:", dc)
        print("  hour values:", hv)
        print("  hour_count:", hc)
        if hv:
            print("  sum(hour values):", sum(hv))
        if hc:
            print("  sum(hour_count):", sum(hc))
        if dv and hv and sum(hv) != 0:
            ratio = dv[0] / sum(hv) if sum(hv) else None
            print(f"  day / sum(hour) ratio: {ratio}")
    return dj, hj


def q3_event_types_filtering():
    print("\n########## Q3: does event_types filtering do anything? ##########")
    body_all = base_body(event_types=list(ALL_EVENT_TYPES))
    body_one = base_body(event_types=["resolved"])
    _, r_all = call(body_all, label="Q3 all event_types", save_to=f"{SCRATCH}/resp-q3-all-event-types.json")
    _, r_one = call(body_one, label="Q3 only resolved", save_to=f"{SCRATCH}/resp-q3-only-resolved.json")
    ja = r_all.get("response_json", {})
    jo = r_one.get("response_json", {})
    print("keys (all):", sorted(ja.keys()))
    print("keys (only resolved):", sorted(jo.keys()))
    print("keys only in 'all':", sorted(set(ja.keys()) - set(jo.keys())))
    print("keys only in 'resolved-only':", sorted(set(jo.keys()) - set(ja.keys())))
    print("resolved values equal?:", ja.get("resolved") == jo.get("resolved"))


def q4_scope_filtering():
    print("\n########## Q4: does scope filter anything? ##########")
    body_noscope = base_body()
    del body_noscope["scope"]
    body_1mailbox = base_body(scope={
        "id": "mailboxes", "operator": {"id": "is"},
        "values": [{"id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns"}],
    })
    body_fake_mailbox = base_body(scope={
        "id": "mailboxes", "operator": {"id": "is"},
        "values": [{"id": "FAKE_MAILBOX_ID_DOES_NOT_EXIST", "name": "Nope"}],
    })

    _, r_noscope = call(body_noscope, label="Q4 no scope", save_to=f"{SCRATCH}/resp-q4-no-scope.json")
    _, r_1mb = call(body_1mailbox, label="Q4 1 real mailbox", save_to=f"{SCRATCH}/resp-q4-1-mailbox.json")
    _, r_fake = call(body_fake_mailbox, label="Q4 fake mailbox", save_to=f"{SCRATCH}/resp-q4-fake-mailbox.json")

    j_noscope = r_noscope.get("response_json", {})
    j_1mb = r_1mb.get("response_json", {})
    j_fake = r_fake.get("response_json", {})

    print("resolved (no scope):", j_noscope.get("resolved"))
    print("resolved (1 mailbox):", j_1mb.get("resolved"))
    print("resolved (fake mailbox):", j_fake.get("resolved"))

    # user scope with a real user id - need to fetch actors first
    _, r_probe = call(base_body(), label="Q4 probe actors")
    actors = r_probe.get("response_json", {}).get("actors", [])
    if actors:
        real_user_id = actors[0].get("user_id") or actors[0].get("id")
        print("using real user_id:", real_user_id)
        body_user_scope = base_body(scope={
            "id": "user", "operator": {"id": "is"},
            "values": [{"id": real_user_id, "name": actors[0].get("name")}],
        })
        _, r_user = call(body_user_scope, label="Q4 user scope", save_to=f"{SCRATCH}/resp-q4-user-scope.json")
        j_user = r_user.get("response_json", {})
        print("resolved (user scope):", j_user.get("resolved"))
        print("num actors returned (user scope):", len(j_user.get("actors", [])))
    else:
        print("No actors found in probe response; skipping user-scope test.")


def q5_community_timezone_timetype():
    print("\n########## Q5: community_id / timezone / time_type ##########")
    body_c1 = base_body(community_id="demo-community")
    body_c2 = base_body(community_id="some-other-community-xyz")
    _, r_c1 = call(body_c1, label="Q5 community=demo-community", save_to=f"{SCRATCH}/resp-q5-community1.json")
    _, r_c2 = call(body_c2, label="Q5 community=other", save_to=f"{SCRATCH}/resp-q5-community2.json")
    j_c1 = r_c1.get("response_json", {})
    j_c2 = r_c2.get("response_json", {})
    print("resolved (community1):", j_c1.get("resolved"))
    print("resolved (community2):", j_c2.get("resolved"))
    print("identical response?:", j_c1 == j_c2)

    body_tz1 = base_body(timezone="America/New_York")
    body_tz2 = base_body(timezone="Asia/Tokyo")
    _, r_tz1 = call(body_tz1, label="Q5 timezone=America/New_York", save_to=f"{SCRATCH}/resp-q5-tz1.json")
    _, r_tz2 = call(body_tz2, label="Q5 timezone=Asia/Tokyo", save_to=f"{SCRATCH}/resp-q5-tz2.json")
    j_tz1 = r_tz1.get("response_json", {})
    j_tz2 = r_tz2.get("response_json", {})
    print("ticks (NY):", j_tz1.get("ticks"))
    print("ticks (Tokyo):", j_tz2.get("ticks"))
    print("ticks identical?:", j_tz1.get("ticks") == j_tz2.get("ticks"))
    print("resolved identical?:", j_tz1.get("resolved") == j_tz2.get("resolved"))

    body_7d = base_body(time_type="7d")
    body_7d.pop("from_date", None)
    body_7d.pop("to_date", None)
    # try without dropping dates too since fields are "required"
    body_7d_with_dates = base_body(time_type="7d")
    _, r_7d = call(body_7d_with_dates, label="Q5 time_type=7d (with from/to present)", save_to=f"{SCRATCH}/resp-q5-7d.json")
    j_7d = r_7d.get("response_json", {})
    print("ticks (7d preset, dates given):", j_7d.get("ticks") if isinstance(j_7d, dict) else j_7d)

    body_custom = base_body(time_type="custom")
    _, r_custom = call(body_custom, label="Q5 time_type=custom", save_to=f"{SCRATCH}/resp-q5-custom.json")
    j_custom = r_custom.get("response_json", {})
    print("ticks (custom):", j_custom.get("ticks") if isinstance(j_custom, dict) else j_custom)

    # try 7d without from/to at all
    body_7d_nodate, r_7d_nodate = None, None
    try:
        b = base_body(time_type="7d")
        del b["from_date"]
        del b["to_date"]
        _, r_7d_nodate = call(b, label="Q5 time_type=7d (no dates)", save_to=f"{SCRATCH}/resp-q5-7d-nodates.json")
    except Exception as e:
        print("error building/sending 7d-no-dates request:", e)


def q6_date_coverage():
    print("\n########## Q6: date coverage & determinism ##########")
    body_wide = base_body(
        from_date="2025-01-01T00:00:00.000Z",
        to_date="2026-08-01T00:00:00.000Z",
        time_unit="week",
        event_types=["resolved", "new_tickets", "replies"],
    )
    _, r_wide = call(body_wide, label="Q6 wide range weekly", save_to=f"{SCRATCH}/resp-q6-wide-range.json")
    j_wide = r_wide.get("response_json", {})
    ticks = j_wide.get("ticks", [])
    resolved = j_wide.get("resolved", [])
    print("num ticks:", len(ticks))
    nonzero_idx = [i for i, v in enumerate(resolved) if v]
    if nonzero_idx:
        print(f"resolved nonzero for {len(nonzero_idx)}/{len(resolved)} buckets")
        print("first nonzero bucket tick range:", ticks[nonzero_idx[0]], "-", ticks[nonzero_idx[0]+1])
        print("last nonzero bucket tick range:", ticks[nonzero_idx[-1]], "-", ticks[nonzero_idx[-1]+1])
    else:
        print("resolved all zero across entire wide range!")
    print("sample resolved values:", resolved[:10], "...", resolved[-10:] if len(resolved) > 10 else "")

    # determinism check - call same body twice
    body_det = base_body(
        from_date="2026-07-15T04:00:00.000Z",
        to_date="2026-07-16T03:59:59.999Z",
        time_unit="day",
    )
    _, r_det1 = call(body_det, label="Q6 determinism call 1", save_to=f"{SCRATCH}/resp-q6-determinism-1.json")
    _, r_det2 = call(body_det, label="Q6 determinism call 2", save_to=f"{SCRATCH}/resp-q6-determinism-2.json")
    j1 = r_det1.get("response_json", {})
    j2 = r_det2.get("response_json", {})
    print("identical responses across 2 identical calls?:", j1 == j2)
    if j1 != j2:
        for k in j1:
            if j1.get(k) != j2.get(k):
                print(f"  differs at key: {k}")


def q7_weird_inputs():
    print("\n########## Q7: weird inputs ##########")

    def try_call(body, label, save_name):
        try:
            resp, result = call(body, label=label, save_to=f"{SCRATCH}/{save_name}")
            j = result.get("response_json")
            if isinstance(j, dict) and "ticks" in j:
                print(f"  -> OK, {len(j.get('ticks', []))} ticks")
            else:
                print(f"  -> body: {json.dumps(j)[:500] if j else result.get('response_text','')[:500]}")
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")

    # time_unit week
    try_call(base_body(time_unit="week", from_date="2026-01-01T00:00:00.000Z", to_date="2026-07-24T00:00:00.000Z"),
              "Q7 time_unit=week", "resp-q7-week.json")
    # time_unit month
    try_call(base_body(time_unit="month", from_date="2025-01-01T00:00:00.000Z", to_date="2026-07-24T00:00:00.000Z"),
              "Q7 time_unit=month", "resp-q7-month.json")
    # invalid event_type
    try_call(base_body(event_types=["not_a_real_event_type"]),
              "Q7 invalid event_type", "resp-q7-invalid-event-type.json")
    # from_date after to_date
    try_call(base_body(from_date="2026-07-24T00:00:00.000Z", to_date="2026-07-10T00:00:00.000Z"),
              "Q7 from_date after to_date", "resp-q7-inverted-dates.json")
    # very large range with minute buckets
    try_call(base_body(time_unit="minute", from_date="2020-01-01T00:00:00.000Z", to_date="2026-07-24T00:00:00.000Z"),
              "Q7 huge range, minute buckets", "resp-q7-huge-minute.json")
    # missing required field
    b = base_body()
    del b["from_date"]
    try_call(b, "Q7 missing from_date", "resp-q7-missing-fromdate.json")
    # invalid time_type
    try_call(base_body(time_type="banana"), "Q7 invalid time_type", "resp-q7-invalid-timetype.json")
    # time_period > 1
    try_call(base_body(time_period=3, time_unit="day"), "Q7 time_period=3", "resp-q7-time-period-3.json")
    # negative time_period
    try_call(base_body(time_period=-1), "Q7 time_period=-1", "resp-q7-time-period-neg1.json")


if __name__ == "__main__":
    q1_full_structure()
    q2_units_mystery()
    q3_event_types_filtering()
    q4_scope_filtering()
    q5_community_timezone_timetype()
    q6_date_coverage()
    q7_weird_inputs()
    print("\nDONE")
