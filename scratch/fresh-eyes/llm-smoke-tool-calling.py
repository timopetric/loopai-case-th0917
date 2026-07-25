"""
LLM smoke test for OpenRouter model against a 9-tool support-analytics agent surface.
Writes results to scratch/fresh-eyes/llm-smoke-results.json
NEVER prints the API key.
"""
import os
import json
import sys
from dotenv import load_dotenv

load_dotenv("/home/timop/work/loopai/.env")

API_KEY = os.environ["OPENROUTER_API_KEY"]
BASE_URL = os.environ["OPENROUTER_BASE_URL"]
MODEL = os.environ["LLM_MODEL"]
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.1"))

from openai import OpenAI

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

METRIC_ENUM = [
    "actioned_emails", "resolved", "new_tickets", "open", "replies",
    "new_emails", "replies_to_resolve", "resolve_time", "response_time",
    "time_to_first_reply", "resolve_time_business_hours",
    "response_time_business_hours", "time_to_first_reply_business_hours",
    "handle_time", "sla_breaches",
]

SYSTEM_PROMPT = (
    "You build support-analytics reports by calling tools that edit a report spec. "
    "Data coverage is 2026-07-10 to 2026-07-23 only. Duration metrics are in hours. "
    "Never invent metric names outside the provided enum."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_date_range",
            "description": "Set the report date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["date_from", "date_to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_metrics",
            "description": "Set which metrics appear in the report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string", "enum": METRIC_ENUM},
                    },
                },
                "required": ["metrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_grouping",
            "description": "Set the grouping dimension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {"type": "string", "enum": ["none", "agent", "mailbox"]},
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_sort",
            "description": "Set sort column and direction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "required": ["column", "direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_columns",
            "description": "Set the column display order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["order"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_chart",
            "description": "Set the metric shown in the chart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": METRIC_ENUM},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_layout",
            "description": "Set report granularity and layout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "granularity": {"type": "string", "enum": ["day", "total"]},
                    "layout": {"type": "string", "enum": ["long", "pivot"]},
                },
                "required": ["granularity", "layout"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_report",
            "description": "Execute the current report spec and return a table summary.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meta",
            "description": "Get available actors/mailboxes/metrics and the data coverage window.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

results = {}
call_count = 0
total_tokens = {"prompt": 0, "completion": 0, "total": 0}


def record_usage(resp):
    global total_tokens
    usage = getattr(resp, "usage", None)
    if usage:
        total_tokens["prompt"] += usage.prompt_tokens or 0
        total_tokens["completion"] += usage.completion_tokens or 0
        total_tokens["total"] += usage.total_tokens or 0


def msg_to_dict(m):
    d = {"role": m.role, "content": m.content}
    if getattr(m, "tool_calls", None):
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in m.tool_calls
        ]
    return d


def chat(messages, tools=TOOLS, tool_choice="auto", max_tokens=400, model=MODEL):
    global call_count
    call_count += 1
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
        )
        record_usage(resp)
        return resp, None
    except Exception as e:
        return None, str(e)


# ---------- T1: slug + auth ----------
print("T1: slug + auth", file=sys.stderr)
resp, err = chat(
    [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "Say OK."}],
    tools=None,
    tool_choice=None,
    max_tokens=10,
)
t1 = {"error": err}
if resp:
    t1["model_echoed"] = resp.model
    t1["content"] = resp.choices[0].message.content
else:
    # try to find correct slug
    try:
        import httpx
        r = httpx.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"}, timeout=20)
        ids = [m["id"] for m in r.json().get("data", []) if "qwen" in m["id"].lower()]
        t1["qwen_models_found"] = ids
    except Exception as e2:
        t1["model_lookup_error"] = str(e2)
results["T1_slug_auth"] = t1

# Use working model going forward (fallback if T1 failed and we found alternatives)
WORKING_MODEL = MODEL
if err and results["T1_slug_auth"].get("qwen_models_found"):
    candidates = results["T1_slug_auth"]["qwen_models_found"]
    plus_candidates = [c for c in candidates if "plus" in c.lower()]
    WORKING_MODEL = (plus_candidates or candidates)[0]
    results["T1_slug_auth"]["fallback_model_used"] = WORKING_MODEL

# ---------- T2: basic tool selection ----------
print("T2: basic tool selection", file=sys.stderr)
t2_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Show me resolved tickets for 13 to 17 July."},
]
resp, err = chat(t2_messages, model=WORKING_MODEL)
t2 = {"error": err}
if resp:
    m = resp.choices[0].message
    t2["message"] = msg_to_dict(m)
results["T2_basic_tool_selection"] = t2

# ---------- T3: parallel tool calls (run twice) ----------
print("T3: parallel tool calls x2", file=sys.stderr)
t3_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Group by agent, add handle time, and sort by handle time descending."},
]
t3_runs = []
for i in range(2):
    resp, err = chat(t3_messages, model=WORKING_MODEL)
    run = {"error": err}
    if resp:
        m = resp.choices[0].message
        run["message"] = msg_to_dict(m)
        run["num_tool_calls"] = len(m.tool_calls) if m.tool_calls else 0
    t3_runs.append(run)
results["T3_parallel_tool_calls"] = t3_runs

# ---------- T4: tool_choice="none" vs "auto" ----------
print("T4: tool_choice none/auto", file=sys.stderr)
t4_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Show me resolved tickets grouped by mailbox for the last week of coverage, then run the report."},
]
resp_none, err_none = chat(t4_messages, tool_choice="none", model=WORKING_MODEL)
resp_auto, err_auto = chat(t4_messages, tool_choice="auto", model=WORKING_MODEL)
t4 = {
    "none": {"error": err_none, "message": msg_to_dict(resp_none.choices[0].message) if resp_none else None},
    "auto": {"error": err_auto, "message": msg_to_dict(resp_auto.choices[0].message) if resp_auto else None},
}
results["T4_tool_choice_none"] = t4

# ---------- T5: enum discipline ----------
print("T5: enum discipline", file=sys.stderr)
t5_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Show me customer satisfaction scores by agent."},
]
resp, err = chat(t5_messages, model=WORKING_MODEL)
t5 = {"error": err}
if resp:
    m = resp.choices[0].message
    t5["message"] = msg_to_dict(m)
results["T5_enum_discipline"] = t5

# ---------- T6: error-feedback retry ----------
print("T6: error-feedback retry", file=sys.stderr)
# Fabricate a prior turn where the model attempted an invalid metric, then feed back a validation error.
fake_tool_call_id = "call_fake_csat_1"
t6_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Show me csat by agent."},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": fake_tool_call_id,
                "type": "function",
                "function": {"name": "set_metrics", "arguments": json.dumps({"metrics": ["csat"]})},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": fake_tool_call_id,
        "content": json.dumps({"error": f"invalid metric 'csat'; valid values are {METRIC_ENUM}"}),
    },
]
resp, err = chat(t6_messages, model=WORKING_MODEL)
t6 = {"error": err}
if resp:
    m = resp.choices[0].message
    t6["message"] = msg_to_dict(m)
results["T6_error_feedback_retry"] = t6

# ---------- T7: out-of-coverage date ----------
print("T7: out-of-coverage date", file=sys.stderr)
t7_messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Show me June 2026."},
]
resp, err = chat(t7_messages, model=WORKING_MODEL)
t7 = {"error": err}
if resp:
    m = resp.choices[0].message
    t7["message"] = msg_to_dict(m)
results["T7_out_of_coverage_date"] = t7

# ---------- T8: streaming tool calls ----------
print("T8: streaming tool calls", file=sys.stderr)
call_count += 1
t8 = {}
try:
    stream = client.chat.completions.create(
        model=WORKING_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Set the date range to July 13 to July 17 2026."},
        ],
        tools=TOOLS,
        tool_choice="auto",
        temperature=TEMPERATURE,
        max_tokens=200,
        stream=True,
    )
    chunks = []
    for chunk in stream:
        d = chunk.model_dump()
        chunks.append(d)
    t8["num_chunks"] = len(chunks)
    t8["chunks_raw_sample"] = chunks[:8]
    # reassemble tool call
    tc_acc = {}
    first_chunk_with_id_and_name = None
    for d in chunks:
        choices = d.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        tcs = delta.get("tool_calls") or []
        for tc in tcs:
            idx = tc.get("index", 0)
            if idx not in tc_acc:
                tc_acc[idx] = {"id": None, "name": None, "arguments": ""}
            if tc.get("id"):
                tc_acc[idx]["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                tc_acc[idx]["name"] = fn["name"]
            if fn.get("arguments"):
                tc_acc[idx]["arguments"] += fn["arguments"]
            if tc_acc[idx]["id"] and tc_acc[idx]["name"] and first_chunk_with_id_and_name is None:
                first_chunk_with_id_and_name = d
    t8["reassembled_tool_calls"] = tc_acc
    t8["id_and_name_in_first_relevant_chunk"] = first_chunk_with_id_and_name is chunks[0] if chunks else None
except Exception as e:
    t8["error"] = str(e)
results["T8_streaming_tool_calls"] = t8

# ---------- write results ----------
results["_meta"] = {
    "model_requested": MODEL,
    "working_model_used": WORKING_MODEL,
    "total_api_calls": call_count,
    "total_tokens": total_tokens,
}

out_path = "/home/timop/work/loopai/scratch/fresh-eyes/llm-smoke-results.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"DONE. calls={call_count} tokens={total_tokens}", file=sys.stderr)
print(json.dumps(results["_meta"], indent=2))
