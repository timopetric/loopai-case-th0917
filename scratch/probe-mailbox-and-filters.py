"""Q2/Q3 second pass: does scope/filters affect WHICH mailbox entries appear or make values nonzero?"""
import sys, json
sys.path.insert(0, "/home/timop/work/loopai/scratch")
from probe_common import call, base_body

SCRATCH = "/home/timop/work/loopai/scratch"

MB_RETURNS = {"id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns"}
MB_PARTNERSHIPS = {"id": "ACqMGljMqLCOAZJ9ZYNz4oNZkF91D0T", "name": "Partnerships"}
MB_COMPLIANCE = {"id": "ACpw3ge04EDYzOsUMhVHgYGqpn2wq0T", "name": "Compliance"}
MB_FAX = {"id": "ACn0hYoSiro8YwtJVsN48DFDtyHyQ0T", "name": "Fax"}
MB_OUTBOUND = {"id": "ACSzkQ6eDUuigSwb0AFR4r7Z19wog0T", "name": "Outbound"}
MB_FAKE = {"id": "FAKE_ID_XYZ_123", "name": "MadeUp"}


def report(label, body, savename):
    _, r = call(body, label=label, save_to=f"{SCRATCH}/{savename}")
    j = r.get("response_json", {})
    mb = j.get("mailbox", [])
    print(f"  mailbox entries: {len(mb)}")
    for m in mb:
        resolved_sum = sum(m.get("resolved", []))
        nt_sum = sum(m.get("new_tickets", []))
        print(f"    id={m.get('id')} name={m.get('name')} resolved_sum={resolved_sum} new_tickets_sum={nt_sum}")
    for extra in ("labels", "topics", "categories"):
        v = j.get(extra)
        print(f"  {extra}: len={len(v) if v is not None else None} content={v if v else '[]'}")
    return j


print("### 1 mailbox scope (Returns) ###")
report("1 mailbox", base_body(scope={"id": "mailboxes", "operator": {"id": "is"}, "values": [MB_RETURNS]}),
       "resp-y1-scope-1mailbox.json")

print("\n### 3 mailboxes scope (Returns, Partnerships, Compliance) ###")
report("3 mailboxes", base_body(scope={"id": "mailboxes", "operator": {"id": "is"}, "values": [MB_RETURNS, MB_PARTNERSHIPS, MB_COMPLIANCE]}),
       "resp-y2-scope-3mailboxes.json")

print("\n### no scope key at all ###")
b = base_body()
del b["scope"]
report("no scope", b, "resp-y3-no-scope.json")

print("\n### scope with fake mailbox id only ###")
report("fake mailbox id", base_body(scope={"id": "mailboxes", "operator": {"id": "is"}, "values": [MB_FAKE]}),
       "resp-y4-fake-mailbox.json")

print("\n### scope id='mailbox' (singular) with 1 real mailbox ###")
report("singular mailbox id field", base_body(scope={"id": "mailbox", "operator": {"id": "is"}, "values": [MB_RETURNS]}),
       "resp-y5-singular-mailbox-scope.json")

print("\n### scope id='allMailboxes' ###")
report("allMailboxes scope", base_body(scope={"id": "allMailboxes", "operator": {"id": "is"}, "values": []}),
       "resp-y6-allmailboxes-scope.json")

print("\n### scope operator 'or' with 5 mailboxes ###")
report("operator or, 5 mailboxes", base_body(scope={"id": "mailboxes", "operator": {"id": "or"}, "values": [MB_RETURNS, MB_PARTNERSHIPS, MB_COMPLIANCE, MB_FAX, MB_OUTBOUND]}),
       "resp-y7-operator-or.json")

print("\n### scope operator 'is_not' with 1 mailbox ###")
report("operator is_not", base_body(scope={"id": "mailboxes", "operator": {"id": "is_not"}, "values": [MB_RETURNS]}),
       "resp-y8-operator-isnot.json")

print("\n### filters array (instead of scope) with 1 mailbox, scope absent ###")
b = base_body()
del b["scope"]
b["filters"] = [{"id": "mailboxes", "operator": {"id": "is"}, "values": [MB_RETURNS]}]
report("filters array only", b, "resp-y9-filters-only.json")

print("\n### filters array with labels ###")
b = base_body()
b["filters"] = [{"id": "labels", "operator": {"id": "is"}, "values": [{"id": "label_urgent", "name": "Urgent"}]}]
report("filters labels", b, "resp-y10-filters-labels.json")

print("\n### filters array with topics ###")
b = base_body()
b["filters"] = [{"id": "topics", "operator": {"id": "is"}, "values": [{"id": "topic_billing", "name": "Billing"}]}]
report("filters topics", b, "resp-y11-filters-topics.json")

print("\n### filters array with categories ###")
b = base_body()
b["filters"] = [{"id": "categories", "operator": {"id": "is"}, "values": [{"id": "cat_1", "name": "Cat1"}]}]
report("filters categories", b, "resp-y12-filters-categories.json")

print("\n### filters array with user, operator and_not ###")
b = base_body()
b["filters"] = [{"id": "user", "operator": {"id": "and_not"}, "values": [{"id": "user_yoJRgsMu", "name": "Support"}]}]
report("filters user and_not", b, "resp-y13-filters-user-andnot.json")

print("\n### scope + filters both present (scope=Returns, filters excludes Fax) ###")
b = base_body(scope={"id": "mailboxes", "operator": {"id": "is"}, "values": [MB_RETURNS]})
b["filters"] = [{"id": "mailboxes", "operator": {"id": "is_not"}, "values": [MB_FAX]}]
report("scope+filters combined", b, "resp-y14-scope-plus-filters.json")

print("\n### customerEmail / customerDomain filter id (undocumented data shape) ###")
b = base_body()
b["filters"] = [{"id": "customerEmail", "operator": {"id": "is"}, "values": [{"id": "someone@example.com", "name": "someone@example.com"}]}]
report("filters customerEmail", b, "resp-y15-filters-customeremail.json")
