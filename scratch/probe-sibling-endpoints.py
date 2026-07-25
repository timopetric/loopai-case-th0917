"""Probe for sibling endpoints and verb/OPTIONS behavior."""
import sys
sys.path.insert(0, "/home/timop/work/loopai/scratch")
import requests
from probe_common import HEADERS, base_body

BASE = "https://ai-homework-production-2423.up.railway.app"

PATHS = [
    "/reporting_api/v1/reporting/stats/json",
    "/reporting_api/v1/reporting/stats/csv",
    "/reporting_api/v1/reporting/stats/xlsx",
    "/reporting_api/v1/reporting/stats/excel",
    "/reporting_api/v1/reporting/stats/pdf",
    "/reporting_api/v1/reporting/stats",
    "/reporting_api/v1/reporting/",
    "/reporting_api/v1/reporting",
    "/reporting_api/v1/",
    "/reporting_api/v1",
    "/reporting_api/",
    "/reporting_api",
    "/reporting_api/v1/reporting/mailboxes",
    "/reporting_api/v1/reporting/users",
    "/reporting_api/v1/reporting/agents",
    "/reporting_api/v1/reporting/metadata",
    "/reporting_api/v1/reporting/export",
    "/reporting_api/v1/reporting/stats/export",
]

VERBS = ["GET", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]


def main():
    print("### Sibling path probing (POST with normal body, and GET) ###")
    body = base_body()
    for path in PATHS:
        url = BASE + path
        try:
            r_post = requests.post(url, headers=HEADERS, json=body, timeout=20)
            post_info = f"POST={r_post.status_code} len={len(r_post.content)}"
        except Exception as e:
            post_info = f"POST=EXC:{e}"
        try:
            r_get = requests.get(url, headers=HEADERS, timeout=20)
            get_info = f"GET={r_get.status_code} len={len(r_get.content)}"
        except Exception as e:
            get_info = f"GET=EXC:{e}"
        print(f"{path:55s} {post_info:25s} {get_info}")
        snippet = None
        try:
            snippet = r_post.text[:200]
        except Exception:
            pass
        if r_post.status_code not in (404,) or path == PATHS[0]:
            print(f"    POST body snippet: {snippet!r}")

    print("\n### Verb probing on the known-good stats/json endpoint ###")
    url = BASE + "/reporting_api/v1/reporting/stats/json"
    for verb in VERBS:
        try:
            r = requests.request(verb, url, headers=HEADERS, json=body if verb not in ("GET", "HEAD", "OPTIONS") else None, timeout=20)
            allow = r.headers.get("Allow") or r.headers.get("allow")
            acao = r.headers.get("access-control-allow-methods")
            print(f"{verb:8s} status={r.status_code} len={len(r.content)} Allow={allow} ACAO-methods={acao}")
            if r.status_code not in (404,):
                print(f"    body snippet: {r.text[:200]!r}")
        except Exception as e:
            print(f"{verb:8s} EXCEPTION: {e}")


if __name__ == "__main__":
    main()
