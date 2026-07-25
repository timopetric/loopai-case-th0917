import httpx, json

HOST = "https://ai-homework-production-2423.up.railway.app"
AUTH = {"Authorization": "Bearer any-token-works", "Content-Type": "application/json", "Accept": "application/json"}
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

client = httpx.Client(timeout=20)
rows = []

paths = [
    "/reporting_api/v1/reporting/stats/csv",
    "/reporting_api/v1/reporting/stats/xlsx",
    "/reporting_api/v1/reporting/stats/excel",
    "/reporting_api/v1/reporting/stats/json/",
    "/reporting_api/v1/reporting/stats",
    "/reporting_api/v1/reporting/",
    "/reporting_api/v1/reporting",
    "/reporting_api/v1/",
    "/reporting_api/v1",
    "/reporting_api/",
    "/reporting_api",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/swagger",
    "/swagger.json",
    "/health",
    "/healthz",
    "/api",
    "/api/v1",
    "/v1",
    "/reporting_api/v1/reporting/mailboxes",
    "/users",
    "/actors",
    "/agents",
    "/communities",
    "/metrics",
    "/reporting_api/v2/reporting/stats/json",
    "/.well-known/",
    "/.well-known/security.txt",
    "/favicon.ico",
    "/robots.txt",
    "/spec",
    "/reporting-api-guide.pdf",
    "/nonexistent-route-xyz-123",
]

for p in paths:
    url = HOST + p
    try:
        r = client.get(url, headers=AUTH)
        rows.append((p, "GET", r.status_code, len(r.content), r.headers.get("content-type",""), r.text[:150].replace("\n"," ")))
    except Exception as e:
        rows.append((p, "GET", "EXC", 0, "", str(e)[:150]))

# main path with various methods
main = "/reporting_api/v1/reporting/stats/json"
for method in ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "TRACE"]:
    try:
        r = client.request(method, HOST + main, headers=AUTH, json=BODY if method in ("PUT","PATCH") else None)
        rows.append((main, method, r.status_code, len(r.content), r.headers.get("content-type",""), r.text[:150].replace("\n"," ")))
    except Exception as e:
        rows.append((main, method, "EXC", 0, "", str(e)[:150]))

# POST without auth to a few paths to see 404 vs 401 precedence
for p in ["/nonexistent-route-xyz-123", "/reporting_api/v1/reporting/stats/csv"]:
    try:
        r = client.post(HOST+p, json=BODY, headers={"Content-Type":"application/json"})
        rows.append((p, "POST-noauth", r.status_code, len(r.content), r.headers.get("content-type",""), r.text[:150]))
    except Exception as e:
        rows.append((p, "POST-noauth", "EXC", 0, "", str(e)[:150]))

# malformed JSON body -> see error format (422 fingerprint)
try:
    r = client.post(HOST+main, content=b"{not valid json", headers={"Authorization":"Bearer x","Content-Type":"application/json"})
    rows.append((main, "POST-badjson", r.status_code, len(r.content), r.headers.get("content-type",""), r.text[:300]))
except Exception as e:
    rows.append((main, "POST-badjson", "EXC", 0, "", str(e)[:150]))

# missing required field -> validation error format
try:
    r = client.post(HOST+main, json={"community_id":"demo-community"}, headers={"Authorization":"Bearer x","Content-Type":"application/json"})
    rows.append((main, "POST-missingfields", r.status_code, len(r.content), r.headers.get("content-type",""), r.text[:500]))
except Exception as e:
    rows.append((main, "POST-missingfields", "EXC", 0, "", str(e)[:150]))

with open("/home/timop/work/loopai/scratch/fresh-eyes/evidence-auth-infra/routes.txt", "w") as f:
    for row in rows:
        line = " | ".join(str(x) for x in row)
        print(line)
        f.write(line + "\n")
