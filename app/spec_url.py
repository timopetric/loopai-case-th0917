"""`ReportSpec` <-> URL query parameters (issue 13, architecture.md §2, §7).

Sharing is by URL — there is no database (architecture.md D3) — so the whole
feature is "serialise the spec into the query string, restore it on load".
The interesting part is what "restore" means: `decode_spec` reuses exactly
the validation `ReportSpec` already enforces everywhere else (builder UI,
Assistant tools, this module), so a hand-edited or stale link can raise
`InvalidSpecQueryError` but can never construct a `ReportSpec` a human
couldn't reach through the controls. `spec_from_query_or_default` is the one
call site that turns that error into the product behaviour the issue asks
for: fall back to the default report with a Warning, never a 500 or a blank
page.

Where this logic actually runs in the browser: `frontend/src/lib/specUrl.ts`
is a hand-mirrored TypeScript port (same pattern `report.ts` already uses for
the `ReportSpec` *type* — this project does not unit-test the frontend, so
the property that must never regress silently — every field round-trips —
is proven here, in Python, once, and enumerated from `ReportSpec.model_
fields` so a field added to the model without being taught to this encoder
fails the test in `tests/test_spec_url.py` rather than shipping a link that
silently drops it. `app/api/v1/routers/spec.py` exposes `decode_spec`/
`spec_from_query_or_default` over real HTTP so the round trip is also proven
through actual Starlette query-string parsing, not just in-process function
calls (PRD's API-level test list: "a Report Spec survives a round-trip
through URL query parameters").
"""

from collections.abc import Mapping

from pydantic import ValidationError

from app.models import ReportSpec

_LIST_SEP = ","


class InvalidSpecQueryError(ValueError):
    """Raised by `decode_spec` when query params cannot be turned into a
    valid `ReportSpec` — a hand-edited or stale link (issue 13). Callers use
    `spec_from_query_or_default` rather than letting this propagate."""


def encode_spec(spec: ReportSpec) -> dict[str, str]:
    """`ReportSpec` -> a flat `dict[str, str]` suitable for `URLSearchParams`
    / `urlencode`. Every field that affects what is displayed is present
    (architecture.md §2's full field list) — optional fields (`sort`,
    `columns_order`, `chart_metric`, `entity_filter`) are omitted, not
    encoded as empty strings, so `decode_spec` can tell "absent" from
    "explicitly cleared" using the same `None`-means-default rule
    `ReportSpec` itself uses.
    """
    params: dict[str, str] = {
        "metrics": _LIST_SEP.join(m.value for m in spec.metrics),
        "date_from": spec.date_from.isoformat(),
        "date_to": spec.date_to.isoformat(),
        "granularity": spec.granularity,
        "group_by": spec.group_by,
        "duration_display": spec.duration_display,
        "layout": spec.layout,
    }
    if spec.sort is not None:
        params["sort_column"] = spec.sort.column
        params["sort_direction"] = spec.sort.direction
    if spec.columns_order is not None:
        params["columns_order"] = _LIST_SEP.join(spec.columns_order)
    if spec.chart_metric is not None:
        params["chart_metric"] = spec.chart_metric.value
    if spec.entity_filter is not None:
        params["entity_filter"] = spec.entity_filter
    return params


def decode_spec(params: Mapping[str, str]) -> ReportSpec:
    """The inverse of `encode_spec`, going through `ReportSpec`'s own
    pydantic validators — restoration is not a bespoke parser that happens
    to accept less than the model does, it constructs the exact same model
    every other caller constructs. Raises `InvalidSpecQueryError` (never a
    bare `pydantic.ValidationError` or `KeyError`) on anything a hand-edited
    or stale link could contain: a missing required field, an unknown enum
    value, an empty metric list, a `sort`/`chart_metric` not among
    `metrics`, or an inverted date range.
    """
    try:
        payload: dict[str, object] = {
            "metrics": [m for m in params["metrics"].split(_LIST_SEP) if m],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
        }
        if "granularity" in params:
            payload["granularity"] = params["granularity"]
        if "group_by" in params:
            payload["group_by"] = params["group_by"]
        if "duration_display" in params:
            payload["duration_display"] = params["duration_display"]
        if "layout" in params:
            payload["layout"] = params["layout"]
        if "sort_column" in params:
            payload["sort"] = {
                "column": params["sort_column"],
                "direction": params.get("sort_direction", "desc"),
            }
        if "columns_order" in params:
            value = params["columns_order"]
            payload["columns_order"] = [c for c in value.split(_LIST_SEP) if c]
        if "chart_metric" in params:
            payload["chart_metric"] = params["chart_metric"]
        if "entity_filter" in params:
            payload["entity_filter"] = params["entity_filter"]

        return ReportSpec(**payload)
    except KeyError as exc:
        raise InvalidSpecQueryError(f"missing required field: {exc}") from exc
    except ValidationError as exc:
        raise InvalidSpecQueryError(str(exc)) from exc


def spec_from_query_or_default(
    params: Mapping[str, str], default: ReportSpec
) -> tuple[ReportSpec, list[str]]:
    """The product-level behaviour the issue asks for: no query params at
    all (a plain visit, not a shared link) restores `default` silently; an
    invalid or stale link also restores `default`, but with a Warning
    explaining why, never a failure. Only a link that decodes cleanly is
    used as-is."""
    if not params:
        return default, []
    try:
        return decode_spec(params), []
    except InvalidSpecQueryError as exc:
        return default, [
            f"That link's report definition could not be restored ({exc}); "
            "showing the default report instead."
        ]
