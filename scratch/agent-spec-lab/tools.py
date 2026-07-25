"""
OpenAI-compatible tool schemas, generated from the pydantic models.

Only 3 tools, deliberately:

- `get_spec`   — read current state. No args. Lets the agent re-orient after
                 a multi-turn conversation without us re-stuffing the full
                 spec into every system/user message.
- `update_spec`— the *only* mutator. Takes a `SpecPatch`. We expose patch
                 semantics (not full ReportSpec replacement) as the tool
                 argument shape specifically so the LLM only has to name the
                 fields it wants to change ("switch the columns around"
                 should not require it to restate metrics/dates/filters it
                 isn't touching). See FINDINGS.md for what goes wrong if you
                 use full-replacement instead.
- `run_report` — executes the current spec against the data engine and
                 returns a compact table summary (not the full row set) so
                 the agent can sanity-check its own edits ("who resolved the
                 most" needs the agent to actually see numbers, not just
                 blindly set group_by/sort and hope).

We deliberately do NOT expose separate tools per field (set_metrics,
set_date_range, set_group_by, ...) — that would multiply tool-call round
trips for compound requests ("group by agent and sort by resolved and only
last week") and multiply the chance of the model emitting a sequence of
partially-invalid intermediate specs. One patch tool keeps a compound edit
atomic: it's validated and applied as a single merge.
"""
from __future__ import annotations

from models import ReportSpec, SpecPatch

_SPEC_PATCH_SCHEMA = SpecPatch.model_json_schema()
_REPORT_SPEC_SCHEMA = ReportSpec.model_json_schema()


def _strip_titles(schema: dict) -> dict:
    """Trim pydantic's auto 'title' noise so the tool schema stays compact
    (models are read from $defs too)."""
    def strip(node):
        if isinstance(node, dict):
            node.pop("title", None)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)
    strip(schema)
    return schema


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_spec",
            "description": (
                "Return the current ReportSpec as JSON. Call this if you are "
                "unsure what the report currently looks like before editing it."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_spec",
            "description": (
                "Apply a partial update (patch) to the current ReportSpec. "
                "Only include fields you want to change — omitted fields are "
                "left exactly as they are. This is merged onto the existing "
                "spec and re-validated as a whole (e.g. date_from<=date_to "
                "must hold after the merge). Returns the resulting full spec "
                "or a validation error message to correct and retry."
            ),
            "parameters": _strip_titles(_SPEC_PATCH_SCHEMA),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_report",
            "description": (
                "Execute the current ReportSpec against the data engine and "
                "return a compact summary (columns, row count, up to 8 sample "
                "rows, and any data-quality warnings). Use this to check your "
                "work after editing the spec, e.g. to confirm sort order or "
                "that a filter produced a non-empty result."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def tool_by_name(name: str) -> dict | None:
    for t in TOOLS:
        if t["function"]["name"] == name:
            return t
    return None
