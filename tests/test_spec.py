"""ReportSpec validation (issue 04).

The load-bearing behaviour: `group_by` is a single scalar, so a report
grouped by Actor *and* Mailbox at once cannot be constructed at all — not
merely rejected by a validator (CONTEXT.md, architecture.md §2).
"""

import pytest
from pydantic import ValidationError

from app.models import Metric, ReportSpec

_VALID_KWARGS = dict(
    metrics=[Metric.RESOLVED],
    date_from="2026-07-10",
    date_to="2026-07-23",
)


def test_a_report_spec_can_be_constructed_with_a_single_group_by() -> None:
    spec = ReportSpec(**_VALID_KWARGS, group_by="agent")

    assert spec.group_by == "agent"


def test_group_by_both_agent_and_mailbox_cannot_be_constructed() -> None:
    """`group_by` only accepts one of "none"/"agent"/"mailbox" — there is no
    way to pass both. A list, a dict, or an unknown combined value must all
    fail validation, proving the impossible cross-tab is unrepresentable
    rather than merely disallowed."""
    for impossible_value in (["agent", "mailbox"], "agent+mailbox", {"agent", "mailbox"}):
        with pytest.raises(ValidationError):
            ReportSpec(**_VALID_KWARGS, group_by=impossible_value)


def test_group_by_defaults_to_none() -> None:
    spec = ReportSpec(**_VALID_KWARGS)

    assert spec.group_by == "none"


def test_date_from_after_date_to_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ReportSpec(metrics=[Metric.RESOLVED], date_from="2026-07-23", date_to="2026-07-10")


def test_metrics_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        ReportSpec(metrics=[], date_from="2026-07-10", date_to="2026-07-23")


def test_unknown_metric_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ReportSpec(metrics=["not_a_real_metric"], date_from="2026-07-10", date_to="2026-07-23")
