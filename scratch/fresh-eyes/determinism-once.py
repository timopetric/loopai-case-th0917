#!/usr/bin/env python3
import httpx, json, time, sys
URL = 'https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json'
HEADERS = {'Authorization': 'Bearer any-token-works', 'Content-Type': 'application/json', 'Accept': 'application/json'}
BODY = {'community_id':'demo-community','event_types':['resolved'],'time_type':'custom','time_unit':'day','time_period':1,'timezone':'America/New_York','from_date':'2026-07-10T05:00:00.000Z','to_date':'2026-07-23T03:59:59.999Z','filters':[]}
r = httpx.post(URL, headers=HEADERS, json=BODY, timeout=60)
outfile = sys.argv[1] if len(sys.argv) > 1 else 'scratch/fresh-eyes/evidence-data/determinism-x.json'
with open(outfile, 'w') as f:
    json.dump({'t': time.time(), 'status': r.status_code, 'json': r.json()}, f, indent=2)
print('done', r.status_code, time.time())
