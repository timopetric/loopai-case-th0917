"""Shared helpers for probing the reporting API."""
import json
import requests

URL = "https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json"
HEADERS = {"Authorization": "Bearer test", "Content-Type": "application/json"}

ALL_EVENT_TYPES = [
    "actioned_emails", "resolved", "new_tickets", "open", "replies", "new_emails",
    "replies_to_resolve", "resolve_time", "response_time", "time_to_first_reply",
    "resolve_time_business_hours", "response_time_business_hours",
    "time_to_first_reply_business_hours", "sla_breaches", "handle_time",
]

MAILBOX_SCOPE = {
    "id": "mailboxes",
    "operator": {"id": "is"},
    "values": [
        {"id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T", "name": "Returns"},
        {"id": "ACqMGljMqLCOAZJ9ZYNz4oNZkF91D0T", "name": "Partnerships"},
        {"id": "ACpw3ge04EDYzOsUMhVHgYGqpn2wq0T", "name": "Compliance"},
        {"id": "ACn0hYoSiro8YwtJVsN48DFDtyHyQ0T", "name": "Fax"},
        {"id": "ACSzkQ6eDUuigSwb0AFR4r7Z19wog0T", "name": "Outbound"},
    ],
}


def base_body(**overrides):
    body = {
        "community_id": "demo-community",
        "event_types": list(ALL_EVENT_TYPES),
        "time_type": "custom",
        "time_unit": "day",
        "time_period": 1,
        "timezone": "America/New_York",
        "from_date": "2026-07-10T05:00:00.000Z",
        "to_date": "2026-07-24T04:59:59.999Z",
        "filters": [],
        "scope": dict(MAILBOX_SCOPE),
    }
    body.update(overrides)
    return body


def call(body, label=None, save_to=None, timeout=60):
    resp = requests.post(URL, headers=HEADERS, json=body, timeout=timeout)
    result = {
        "status_code": resp.status_code,
        "request_body": body,
    }
    try:
        result["response_json"] = resp.json()
    except Exception:
        result["response_text"] = resp.text
    if label:
        print(f"=== {label} === status={resp.status_code}")
    if save_to:
        with open(save_to, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  saved -> {save_to}")
    return resp, result
