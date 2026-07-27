"""
LLM smoke test for OpenRouter model against the real 10-tool report-builder Assistant surface
(app/agent/tools.py's build_tool_definitions(), app/agent/llm.py's _system_prompt() rendering
the real app/agent/prompts/report_agent_system.jinja against the committed fixture dataset).

Updated for issue 08 (system-prompt XML conversion + tool-description rewrite + set_filter):
runs the same T1-T8 battery as before, plus a new T9 covering set_filter, against **two**
system-prompt variants that share identical content and differ only in section structure:

  - "xml":      the real, currently-shipped app/agent/prompts/report_agent_system.jinja render
                (<coverage_window>, <metric_catalogue>, <tools>, ... tags)
  - "markdown": the same rendered content with each XML tag pair mechanically rewritten to a
                `## Heading` (see `xml_to_markdown_variant` below) — isolates the structural
                question (XML tags vs markdown headings) from the content rewrite, which is
                identical in both variants.

This is the acceptance-criterion test that empirically settles issue 08's open XML-vs-markdown
question (architecture.md / PRD: "the strongest evidence for XML-tag structuring is
Claude-specific, ... one source explicitly recommends markdown for Qwen-family models").

Writes results to scratch/fresh-eyes/llm-smoke-results.json (both variants, keyed by name).
NEVER prints the API key.
"""
import os
import re
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

sys.path.insert(0, "/home/timop/work/loopai")
from app.agent.llm import _system_prompt  # noqa: E402
from app.agent.tools import build_tool_definitions  # noqa: E402
from app.models import Metric, ReportSpec  # noqa: E402
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset  # noqa: E402

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")
DATASET = _normalise_dataset(FIXTURE_RAW, WINDOW)
SPEC = ReportSpec.model_validate(
    {
        "metrics": [Metric.RESOLVED],
        "date_from": "2026-07-10",
        "date_to": "2026-07-16",
        "group_by": "none",
    }
)

TOOLS = build_tool_definitions()
METRIC_ENUM = [m.value for m in Metric]

_XML_TAG_TO_HEADING = {
    "coverage_window": "Coverage Window",
    "metric_catalogue": "Metric catalogue",
    "current_spec": "Current Report Spec",
    "tools": "Tools",
    "response_style": "Response style",
}


def xml_to_markdown_variant(xml_prompt: str) -> str:
    """Mechanically rewrite each `<tag>...</tag>` section to `## Heading` +
    body, dropping the closing tag — same content, markdown-heading
    structure instead of XML tags. Isolates the structural variable this
    smoke test is measuring."""
    out = xml_prompt
    for tag, heading in _XML_TAG_TO_HEADING.items():
        out = out.replace(f"<{tag}>\n", f"## {heading}\n\n")
        out = out.replace(f"</{tag}>\n", "\n")
        out = out.replace(f"<{tag}>", f"## {heading}\n")
        out = out.replace(f"</{tag}>", "")
    # Defensive: fail loudly if any tag survived the rewrite (keeps this
    # script honest if the jinja template's tag set ever changes).
    leftover = re.findall(r"</?[a-z_]+>", out)
    if leftover:
        raise RuntimeError(f"xml_to_markdown_variant left tags behind: {leftover}")
    return out


XML_SYSTEM_PROMPT = _system_prompt(SPEC, DATASET)
MARKDOWN_SYSTEM_PROMPT = xml_to_markdown_variant(XML_SYSTEM_PROMPT)

VARIANTS = {"xml": XML_SYSTEM_PROMPT, "markdown": MARKDOWN_SYSTEM_PROMPT}

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


def run_battery(variant_name: str, system_prompt: str, working_model: str) -> dict:
    results = {}

    print(f"[{variant_name}] T2: basic tool selection", file=sys.stderr)
    t2_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Show me resolved tickets for 13 to 17 July."},
    ]
    resp, err = chat(t2_messages, model=working_model)
    t2 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t2["message"] = msg_to_dict(m)
    results["T2_basic_tool_selection"] = t2

    print(f"[{variant_name}] T3: parallel tool calls x2", file=sys.stderr)
    t3_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "Group by agent, add handle time, and sort by handle time descending.",
        },
    ]
    t3_runs = []
    for _ in range(2):
        resp, err = chat(t3_messages, model=working_model)
        run = {"error": err}
        if resp:
            m = resp.choices[0].message
            run["message"] = msg_to_dict(m)
            run["num_tool_calls"] = len(m.tool_calls) if m.tool_calls else 0
        t3_runs.append(run)
    results["T3_parallel_tool_calls"] = t3_runs

    print(f"[{variant_name}] T4: tool_choice none/auto", file=sys.stderr)
    t4_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Show me resolved tickets grouped by mailbox for the last week of coverage, "
                "then run the report."
            ),
        },
    ]
    resp_none, err_none = chat(t4_messages, tool_choice="none", model=working_model)
    resp_auto, err_auto = chat(t4_messages, tool_choice="auto", model=working_model)
    results["T4_tool_choice_none"] = {
        "none": {
            "error": err_none,
            "message": msg_to_dict(resp_none.choices[0].message) if resp_none else None,
        },
        "auto": {
            "error": err_auto,
            "message": msg_to_dict(resp_auto.choices[0].message) if resp_auto else None,
        },
    }

    print(f"[{variant_name}] T5: enum discipline", file=sys.stderr)
    t5_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Show me customer satisfaction scores by agent."},
    ]
    resp, err = chat(t5_messages, model=working_model)
    t5 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t5["message"] = msg_to_dict(m)
    results["T5_enum_discipline"] = t5

    print(f"[{variant_name}] T6: error-feedback retry", file=sys.stderr)
    fake_tool_call_id = "call_fake_csat_1"
    t6_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Show me csat by agent."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": fake_tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "set_metrics",
                        "arguments": json.dumps({"metrics": ["csat"]}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": fake_tool_call_id,
            "content": json.dumps(
                {"error": f"invalid metric 'csat'; valid values are {METRIC_ENUM}"}
            ),
        },
    ]
    resp, err = chat(t6_messages, model=working_model)
    t6 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t6["message"] = msg_to_dict(m)
    results["T6_error_feedback_retry"] = t6

    print(f"[{variant_name}] T7: out-of-coverage date", file=sys.stderr)
    t7_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Show me June 2026."},
    ]
    resp, err = chat(t7_messages, model=working_model)
    t7 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t7["message"] = msg_to_dict(m)
    results["T7_out_of_coverage_date"] = t7

    print(f"[{variant_name}] T8: streaming tool calls", file=sys.stderr)
    global call_count
    call_count += 1
    t8 = {}
    try:
        stream = client.chat.completions.create(
            model=working_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Set the date range to July 13 to July 17 2026."},
            ],
            tools=TOOLS,
            tool_choice="auto",
            temperature=TEMPERATURE,
            max_tokens=200,
            stream=True,
        )
        chunks = [chunk.model_dump() for chunk in stream]
        t8["num_chunks"] = len(chunks)
        tc_acc = {}
        for d in chunks:
            choices = d.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                acc = tc_acc.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                if tc.get("id"):
                    acc["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    acc["name"] = fn["name"]
                if fn.get("arguments"):
                    acc["arguments"] += fn["arguments"]
        t8["reassembled_tool_calls"] = tc_acc
    except Exception as e:
        t8["error"] = str(e)
    results["T8_streaming_tool_calls"] = t8

    print(f"[{variant_name}] T9: set_filter (case-insensitive substring, informal name)", file=sys.stderr)
    t9_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Group by agent and filter to just theo's numbers."},
    ]
    resp, err = chat(t9_messages, model=working_model)
    t9 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t9["message"] = msg_to_dict(m)
    results["T9_set_filter"] = t9

    print(f"[{variant_name}] T10: set_filter clear via empty string", file=sys.stderr)
    t10_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Group by agent and filter to just theo's numbers."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_fake_filter_1",
                    "type": "function",
                    "function": {
                        "name": "set_filter",
                        "arguments": json.dumps({"query": "theo"}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_fake_filter_1",
            "content": json.dumps({"ok": True}),
        },
        {"role": "user", "content": "Never mind, remove that filter and show everyone again."},
    ]
    resp, err = chat(t10_messages, model=working_model)
    t10 = {"error": err}
    if resp:
        m = resp.choices[0].message
        t10["message"] = msg_to_dict(m)
    results["T10_set_filter_clear"] = t10

    return results


# ---------- T1: slug + auth (once, not per-variant) ----------
print("T1: slug + auth", file=sys.stderr)
resp, err = chat(
    [{"role": "system", "content": "Say OK."}, {"role": "user", "content": "Say OK."}],
    tools=None,
    tool_choice=None,
    max_tokens=10,
)
t1 = {"error": err}
if resp:
    t1["model_echoed"] = resp.model
    t1["content"] = resp.choices[0].message.content
else:
    try:
        import httpx

        r = httpx.get(
            f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"}, timeout=20
        )
        ids = [m["id"] for m in r.json().get("data", []) if "qwen" in m["id"].lower()]
        t1["qwen_models_found"] = ids
    except Exception as e2:
        t1["model_lookup_error"] = str(e2)

WORKING_MODEL = MODEL
if err and t1.get("qwen_models_found"):
    candidates = t1["qwen_models_found"]
    plus_candidates = [c for c in candidates if "plus" in c.lower()]
    WORKING_MODEL = (plus_candidates or candidates)[0]
    t1["fallback_model_used"] = WORKING_MODEL

results = {"T1_slug_auth": t1}

for variant_name, system_prompt in VARIANTS.items():
    print(f"=== Running battery for variant: {variant_name} ===", file=sys.stderr)
    results[variant_name] = run_battery(variant_name, system_prompt, WORKING_MODEL)

results["_meta"] = {
    "model_requested": MODEL,
    "working_model_used": WORKING_MODEL,
    "total_api_calls": call_count,
    "total_tokens": total_tokens,
    "variants_compared": list(VARIANTS.keys()),
    "prompt_char_lengths": {k: len(v) for k, v in VARIANTS.items()},
}

out_path = "/home/timop/work/loopai/scratch/fresh-eyes/llm-smoke-results.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"DONE. calls={call_count} tokens={total_tokens}", file=sys.stderr)
print(json.dumps(results["_meta"], indent=2))
