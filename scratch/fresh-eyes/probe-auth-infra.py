import httpx, json, time, sys

HOST = "https://ai-homework-production-2423.up.railway.app"
PATH = "/reporting_api/v1/reporting/stats/json"
URL = HOST + PATH

BODY = {
    "community_id": "demo-community",
    "event_types": ["resolved"],
    "time_type": "custom",
    "time_unit": "day",
    "time_period": 1,
    "timezone": "America/New_York",
    "from_date": "2026-07-10T05:00:00.000Z",
    "to_date": "2026-07-23T03:59:59.999Z",
    "filters": []
}

out = []

def log(section, msg):
    print(f"=== {section} === {msg}")
    out.append(f"=== {section} ===\n{msg}\n")

client = httpx.Client(timeout=30)

# 1. AUTH MATRIX
auth_cases = [
    ("no_auth_header", {}),
    ("empty_auth_header", {"Authorization": ""}),
    ("bearer_no_token", {"Authorization": "Bearer"}),
    ("bearer_space_no_token", {"Authorization": "Bearer "}),
    ("bearer_random_junk", {"Authorization": "Bearer " + "x"*20}),
    ("basic_xyz", {"Authorization": "Basic xyz"}),
    ("weird_chars_token", {"Authorization": "Bearer !@#$%^&*()_+{}|:\"<>?"}),
    ("very_long_token", {"Authorization": "Bearer " + "a"*5000}),
    ("lowercase_bearer", {"Authorization": "bearer sometoken123"}),
    ("known_good_1", {"Authorization": "Bearer any-token-works"}),
    ("known_good_2", {"Authorization": "Bearer totally-different-token-abc"}),
    ("known_good_3", {"Authorization": "Bearer 12345"}),
    ("known_good_4", {"Authorization": "Bearer " + "z"*10}),
    ("known_good_5", {"Authorization": "Bearer TEST-TOKEN-9999"}),
]

auth_responses = {}
for name, extra_headers in auth_cases:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(extra_headers)
    try:
        r = client.post(URL, json=BODY, headers=headers)
        body_snip = r.text[:500]
        log("AUTH:" + name, f"status={r.status_code} headers={dict(r.headers)}\nbody={body_snip}")
        auth_responses[name] = (r.status_code, r.text)
    except Exception as e:
        log("AUTH:" + name, f"EXCEPTION: {e}")

# token in query param instead of header
try:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post(URL + "?token=any-token-works", json=BODY, headers=headers)
    log("AUTH:token_in_query_no_header", f"status={r.status_code} body={r.text[:500]}")
except Exception as e:
    log("AUTH:token_in_query_no_header", f"EXCEPTION: {e}")

# diff known-good responses across 5 different tokens
log("AUTH:diff_check", "Comparing bodies for known_good_1..5")
bodies = [auth_responses.get(f"known_good_{i}", (None,None))[1] for i in range(1,6)]
identical = all(b == bodies[0] for b in bodies if b is not None)
log("AUTH:diff_check_result", f"All 5 token responses identical: {identical}")

# auth on /spec and pdf
for p in ["/spec", "/reporting-api-guide.pdf", "/"]:
    r_noauth = client.get(HOST + p)
    r_auth = client.get(HOST + p, headers={"Authorization": "Bearer any-token-works"})
    log(f"AUTH:page:{p}", f"no_auth status={r_noauth.status_code} len={len(r_noauth.content)} | with_auth status={r_auth.status_code} len={len(r_auth.content)}")

with open("/home/timop/work/loopai/scratch/fresh-eyes/evidence-auth-infra/auth_matrix.txt", "w") as f:
    f.write("\n".join(out))

print("DONE AUTH")
