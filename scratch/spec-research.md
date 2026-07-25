# Research: ai-homework-production-2423.up.railway.app

## Tech observations

- Server: `railway-hikari` (Railway's edge proxy) fronting an `Express` app (`x-powered-by: Express`) — a Node.js backend.
- No FastAPI / OpenAPI: `/openapi.json`, `/docs`, `/redoc` all 404 ("Cannot GET ...").
- CORS is wide open: `access-control-allow-origin: *`, allowed methods `POST, GET, OPTIONS`, allowed headers `authorization, content-type`. This strongly signals the endpoint is meant to be called directly from a browser-based frontend.
- The reporting endpoint validates JSON body server-side with clear Rust/serde-like error messages (e.g. `Failed to deserialize the JSON body into the target type: missing field \`from_date\``) — suggests the actual `/reporting_api/...` service might be a separate (possibly Rust/Axum) microservice behind the Express gateway, or Express with a strict schema validator producing serde-style messages. Root site (`/`, `/spec`) itself is a simple static Express page.
- Auth: `Authorization: Bearer <any-token>` — literally any bearer token is accepted (confirmed empirically: `Bearer test-token` and `Bearer x` both authorized). No token means `{"error":"No auth provided"}`.
- GET on the stats endpoint returns 404 — POST only.
- A downloadable PDF exists at `/reporting-api-guide.pdf` (530KB, application/pdf) — same guide as `/spec` in PDF form, not yet parsed (only fetched headers).

## What the root URL (`/`) serves

An HTML "case file" landing page (styled like a detective dossier, sepia paper theme) for a take-home/homework assignment from a company called **InTheLoop** (support-inbox / helpdesk analytics product), Case No. TH-0917. It is not an API — it's the assignment brief. Full text below.

### Root page content (verbatim, text extracted from HTML)

> **InTheLoop · Engineering — Case No. TH-0917 — [Open Case]**
>
> # The endpoint knows something.
> ## Your job is to find out what.
>
> A live data feed. A frustrated client. A deadline. The docs are thin and possibly unreliable. Investigate, and build what the client actually needs.
>
> **◷ The incident — 09:14**
>
> A client runs a **large** support operation — many agents, many shared inboxes — and they're flying blind. They can't see **who did what, where, and how fast**. Frustrated clients don't stay clients.
>
> Your PM forwards the client's email. He trusts you to run with it.
>
> > **EXHIBIT A** — fwd from PM · subject: this is the whole ask 🙏
> >
> > "We want a **CSV file** with, per **day**, how much each **agent** did in each **inbox** — replies, resolved, handle time, all of it. But not one frozen file — we want an **interface where we decide how the report looks**. Oh, and **Excel** too. And honestly? It'd be amazing to **also look at it in the browser, prepare reports right there, and download them**."
>
> Note: we don't ship tools that just sit and wait. The client also gets an **AI agent** — they describe what they want in plain English, and it builds the report.
>
> **⌁ The lead**
>
> Our backend dev stood up an **endpoint** before he got pulled away. He left a short guide — but real docs are never the whole truth. Probe it. Trust what you observe. Fill in the blanks.
>
> ```
> POST https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json
> Authorization: Bearer <any-token>
> Content-Type: application/json
> ```
>
> [Open the guide → /spec]   [↓ PDF → /reporting-api-guide.pdf]
>
> **✦ Field procedure**
>
> 1. **Figure it out.** No docs (or shaky docs) is just Tuesday. Infer the units, don't wait for perfect info, and be upfront about what you assumed.
> 2. **Lean forward.** Build what the user actually needs — not only what's literally typed in the email.
> 3. **Own your calls.** Cut a corner to hit the deadline? Fine — just tell us, and tell us what you'd do next.
>
> **⇢ Submit as evidence**
>
> 1. A running app — a deployed link, or a repo we can spin up with one command.
> 2. A short **README**: how to run it, what you built, what you assumed, what's next.
> 3. The code.
>
> *Treat it like the one-night sprint it is. We're not grading polish — we're watching how you think when the map runs out, how you prioritize when the clock's loud, and whether the thing you ship actually helps the client.*
>
> **The case is yours.**
> Go find out what the endpoint knows.

## `/spec` page content (verbatim) — "Reporting API — Quick start guide"

> # Reporting API
> How to request report data — a quick start guide.
>
> ## 1. The endpoint
>
> Send a **POST** request with a JSON body to:
>
> `POST https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json`
>
> The response is a JSON object with your requested metrics, described in section 5.
>
> ## 2. Authentication & headers
>
> Authenticate with an API key sent as a Bearer token.
>
> | Header | Value |
> |---|---|
> | `Authorization` | `Bearer <your API key>` |
> | `Content-Type` | `application/json` |
> | `Accept` | `application/json` |
>
> ## 3. The request body
>
> The body tells the API *what* to measure, *over what period*, and *for which mailboxes/people*.
>
> | Field | Required | Description |
> |---|---|---|
> | `community_id` | **Yes** | Your workspace / community ID. |
> | `event_types` | **Yes** | List of metrics to return, e.g. `["resolved","new_tickets"]`. See 3a. |
> | `time_type` | **Yes** | Period preset: `today`, `yesterday`, `all`, `custom`, or a dynamic value like `7d`. |
> | `time_unit` | **Yes** | Bucket size: `minute`, `hour`, `day`, `week`, or `month`. |
> | `time_period` | **Yes** | How many time_units per bucket (usually `1`). |
> | `from_date` | **Yes** | Start of the window (ISO 8601 UTC), e.g. `2026-07-18T04:00:00.000Z`. |
> | `to_date` | **Yes** | End of the window (ISO 8601 UTC). |
> | `timezone` | **Yes** | IANA timezone used to align buckets, e.g. `America/New_York`. |
> | `scope` | No | The main set of mailboxes/people to report on. See 3b. |
> | `filters` | No | Additional filters, same shape as scope. Empty list `[]` for none. |
>
> ### 3a. Available metrics (event_types)
>
> Pass any combination of these values. Counts are whole numbers; time metrics are in seconds.
>
> ```
> actioned_emails, resolved, new_tickets, open, replies, new_emails,
> replies_to_resolve, resolve_time, response_time, time_to_first_reply,
> resolve_time_business_hours, response_time_business_hours,
> time_to_first_reply_business_hours, sla_breaches, handle_time
> ```
>
> ### 3b. Scope & filters
>
> A scope (or filter) narrows the report to specific mailboxes, tags, people, or customers. It has an `id` (what to filter on), an `operator`, and a list of `values`:
>
> ```json
> "scope": {
>   "id": "mailboxes",
>   "operator": { "id": "is" },
>   "values": [
>     { "id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns" },
>     { "id": "ACqMGljMqLCOAZJ9ZYNz4oNZkF91D0T", "name": "Partnerships" }
>   ]
> }
> ```
>
> | Filter id | Operator id |
> |---|---|
> | `user`, `labels`, `topics`, `categories`, `allMailboxes`, `mailbox`, `mailboxes`, `privateMailboxes`, `customerEmail`, `customerDomain` | `is`, `is_not`, `or`, `or_not`, `and`, `and_not` |
>
> ## 4. Full example request
>
> Resolved tickets for a custom inbox:
>
> ```json
> {
>   "community_id": "demo-community",
>   "event_types": ["resolved"],
>   "time_type": "today",
>   "time_unit": "day",
>   "time_period": 1,
>   "timezone": "America/New_York",
>   "from_date": "2026-07-18T04:00:00.000Z",
>   "to_date":   "2026-07-20T03:59:59.999Z",
>   "filters": [],
>   "scope": {
>     "id": "mailboxes",
>     "operator": { "id": "is" },
>     "values": [
>       { "id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns" }
>     ]
>   }
> }
> ```
>
> ### 4b. Example: year-to-date scorecard
>
> A custom date range for replies, resolved and handle time, across several shared inboxes. Agent-level numbers come back in the `actors` array.
>
> ```json
> {
>   "community_id": "demo-community",
>   "event_types": ["replies", "resolved", "handle_time"],
>   "time_type": "custom",
>   "time_unit": "day",
>   "time_period": 1,
>   "timezone": "America/New_York",
>   "from_date": "2026-07-10T05:00:00.000Z",
>   "to_date":   "2026-07-23T03:59:59.999Z",
>   "filters": [],
>   "scope": {
>     "id": "mailboxes",
>     "operator": { "id": "is" },
>     "values": [
>       { "id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns" },
>       { "id": "ACqMGljMqLCOAZJ9ZYNz4oNZkF91D0T", "name": "Partnerships" },
>       { "id": "ACpw3ge04EDYzOsUMhVHgYGqpn2wq0T", "name": "Compliance" },
>       { "id": "ACn0hYoSiro8YwtJVsN48DFDtyHyQ0T", "name": "Fax" },
>       { "id": "ACSzkQ6eDUuigSwb0AFR4r7Z19wog0T", "name": "Outbound" }
>     ]
>   }
> }
> ```
>
> ## 5. Understanding the response
>
> The response contains a `ticks` array (bucket boundaries) and one array per requested metric. Each value sits *between* two ticks, so there is always **one more tick than there are metric values**. Time metrics also return a matching `<metric>_count` array so you can compute weighted averages.
>
> ```json
> {
>   "ticks": ["2026-07-16T22:00:00Z", "2026-07-17T22:00:00Z"],
>   "resolved": [3],
>   "new_tickets": [5],
>   "actors": [ ... per-user breakdown ... ],
>   "mailbox": [ ... per-inbox breakdown ... ]
> }
> ```
>
> Alongside the top-level totals, the response breaks the same metrics down by `actors` (people) and `mailbox`.
>
> *Tip: all dates are UTC (ISO 8601). Use the `timezone` field to control how days and weeks are bucketed for your team.*

## API endpoints discovered (empirical probing — no openapi.json available)

Only one real endpoint found; probing confirmed and extended what the guide says:

### `POST /reporting_api/v1/reporting/stats/json`

- **Auth**: `Authorization: Bearer <any string>` — token value is NOT validated (any non-empty bearer token is accepted). Missing header → `{"error":"No auth provided"}`.
- **Method enforcement**: GET on the same path → `404`.
- **Body validation**: strict/required-field checked server-side. Omitting a required field (e.g. `from_date`) returns a Rust/serde-style error string: `Failed to deserialize the JSON body into the target type: missing field \`from_date\``. `community_id` value is NOT validated against a real workspace (`"demo-community"` worked with no error and returned data) — the backend appears to synthesize/mock a fixed dataset regardless of `community_id` or the specific mailbox IDs given.
- **Response shape**, confirmed live with a 14-day request (`event_types: resolved, replies, handle_time`, `time_unit: day`):
  - `ticks`: array of ISO8601 bucket-boundary timestamps (N+1 of them for N buckets — confirmed 15 ticks for 14 daily buckets).
  - One array per requested `event_type`, but the live response actually returned **ALL** known metrics regardless of what was requested in `event_types` (requested only `resolved, replies, handle_time` but response included `actioned_emails`, `new_tickets`, `open`, `new_emails`, `replies_to_resolve` (+`_count`), `resolve_time` (+`_count`), `response_time` (+`_count`), `time_to_first_reply` (+`_count`), `resolve_time_business_hours` (+`_count`), `response_time_business_hours` (+`_count`), `time_to_first_reply_business_hours` (+`_count`), `sla_breaches`, `handle_time` (+`_count`)). This suggests `event_types` filtering may not actually be implemented server-side (or only partially) — worth flagging as an observed discrepancy vs the docs.
  - Metrics that are "time" metrics (`resolve_time`, `response_time`, `time_to_first_reply`, and their `_business_hours` variants, `handle_time`) each have a companion `<metric>_count` array as documented, for weighted-average computation. Values appear to be **totals in seconds** per bucket (need to divide by `_count` to get an average handle time etc.), not seconds-per-ticket directly — e.g. `handle_time: [7.99, ...]` with `handle_time_count: [569, ...]` for one bucket implies handle_time is actually being reported in some aggregate unit — likely **hours**, not seconds, once divided out (7.99 / 569 ≈ 0.014, too small to be a per-ticket seconds average; but the raw numbers being small floats like 7.99 rather than large numbers like ~340000 (569 tickets * ~600s) suggests handle_time may already be pre-aggregated in **hours** rather than seconds as the doc states — this is a discrepancy worth noting/assuming explicitly in the README).
  - `open` metric returned all zeros across all 14 days in the sample — possibly always 0, or only meaningful for "current state" style queries (not a time-bucketed delta).
  - `actors`: array of per-user objects. Each object repeats ALL the same metric arrays as the top level (per-day arrays), plus `user_id`, `id`, `name` (e.g. `{"user_id":"user_yoJRgsMu","name":"Support","id":"user_yoJRgsMu", "resolved":[...], "new_tickets":[...], ...}`). Many users showed all-zero arrays for most metrics but nonzero for a few (e.g. `new_tickets`), suggesting actor-level breakdown is sparse/partial for some metrics in the mock data.
  - A `mailbox` breakdown array is documented (5. Understanding the response) but was not visible in the truncated sample fetched (response was cut off at 6000 chars); likely present further in the payload, structured like `actors` but keyed by mailbox.
- **CORS**: fully open (`*`), `OPTIONS` supported — endpoint is callable directly from browser JS.

## PDF guide

`/reporting-api-guide.pdf` (530,705 bytes, `application/pdf`, last-modified 2026-07-23) — appears to be the same "Quick start guide" content as `/spec`, exported to PDF. Not parsed in detail (only headers fetched); content is presumed to mirror the HTML `/spec` page based on identical title/framing, though the assignment explicitly warns "real docs are never the whole truth" so it may contain additional or differing details worth diffing against `/spec` if time allows.
