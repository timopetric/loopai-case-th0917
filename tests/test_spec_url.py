"""`app/spec_url.py` (issue 13): `ReportSpec` <-> URL query parameters.

The core property the issue names: **every field that affects what is
displayed survives serialise-then-deserialise unchanged.**
`test_every_report_spec_field_round_trips_when_changed` is parametrized over
`ReportSpec.model_fields.keys()` rather than a hand-typed list, so a field
added to the model later without teaching `_ALTERNATE_VALUES` (and, in
practice, `encode_spec`/`decode_spec`) about it fails this test immediately
— it cannot silently ship as a link that drops the field.
"""

from datetime import date

import pytest

from app.models import Metric, ReportSpec, SortSpec
from app.spec_url import InvalidSpecQueryError, decode_spec, encode_spec, spec_from_query_or_default


def _full_spec() -> ReportSpec:
    """A spec with every optional field populated and set to a NON-default
    value, so a round trip that silently fell back to a default would be
    caught by simple equality rather than by luck."""
    return ReportSpec(
        metrics=[Metric.RESOLVED, Metric.NEW_TICKETS],
        date_from=date(2026, 7, 11),
        date_to=date(2026, 7, 20),
        granularity="total",
        group_by="mailbox",
        duration_display="total",
        sort=SortSpec(column="resolved", direction="asc"),
        columns_order=["new_tickets", "resolved"],
        layout="pivot",
        chart_metric=Metric.NEW_TICKETS,
    )


def test_a_fully_populated_spec_round_trips_unchanged() -> None:
    spec = _full_spec()

    decoded = decode_spec(encode_spec(spec))

    assert decoded == spec


def test_a_minimal_spec_with_only_required_fields_round_trips_to_the_same_defaults() -> None:
    spec = ReportSpec(metrics=[Metric.RESOLVED], date_from="2026-07-10", date_to="2026-07-23")

    decoded = decode_spec(encode_spec(spec))

    assert decoded == spec
    assert decoded.sort is None
    assert decoded.columns_order is None
    assert decoded.chart_metric is None


# One alternate, non-default value per `ReportSpec` field, used to prove that
# field specifically survives the round trip. `metrics` is handled specially
# in `_mutate_field` below because changing it can invalidate `sort`/
# `chart_metric` on the base spec (both must stay ∈ `metrics`).
_ALTERNATE_VALUES: dict[str, object] = {
    "date_from": date(2026, 7, 12),
    "date_to": date(2026, 7, 19),
    "granularity": "day",
    "group_by": "agent",
    "duration_display": "avg",
    "sort": SortSpec(column="new_tickets", direction="desc"),
    "columns_order": ["resolved"],
    "layout": "long",
    "chart_metric": Metric.RESOLVED,
    "entity_filter": "theo",
}


def _mutate_field(base: ReportSpec, field: str) -> ReportSpec:
    if field == "metrics":
        return base.model_copy(
            update={"metrics": [Metric.SLA_BREACHES], "sort": None, "chart_metric": None}
        )
    if field not in _ALTERNATE_VALUES:
        raise NotImplementedError(
            f"ReportSpec grew a field ({field!r}) that tests/test_spec_url.py doesn't know an "
            "alternate value for yet — teach _ALTERNATE_VALUES (and, most likely, "
            "app/spec_url.py's encode_spec/decode_spec) about it before this can pass."
        )
    return base.model_copy(update={field: _ALTERNATE_VALUES[field]})


@pytest.mark.parametrize("field", sorted(ReportSpec.model_fields.keys()))
def test_every_report_spec_field_round_trips_when_changed(field: str) -> None:
    base = _full_spec()
    mutated = _mutate_field(base, field)

    decoded = decode_spec(encode_spec(mutated))

    assert getattr(decoded, field) == getattr(
        mutated, field
    ), f"ReportSpec.{field} did not survive a URL query-parameter round trip"


def test_decode_rejects_a_missing_required_field() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec({"date_from": "2026-07-10", "date_to": "2026-07-23"})


def test_decode_rejects_an_empty_metrics_list() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec({"metrics": "", "date_from": "2026-07-10", "date_to": "2026-07-23"})


def test_decode_rejects_an_unknown_metric() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec(
            {"metrics": "not_a_real_metric", "date_from": "2026-07-10", "date_to": "2026-07-23"}
        )


def test_decode_rejects_an_inverted_date_range() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec({"metrics": "resolved", "date_from": "2026-07-23", "date_to": "2026-07-10"})


def test_decode_rejects_a_chart_metric_not_among_metrics() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec(
            {
                "metrics": "resolved",
                "date_from": "2026-07-10",
                "date_to": "2026-07-23",
                "chart_metric": "new_tickets",
            }
        )


def test_decode_rejects_a_sort_column_not_among_metrics() -> None:
    with pytest.raises(InvalidSpecQueryError):
        decode_spec(
            {
                "metrics": "resolved",
                "date_from": "2026-07-10",
                "date_to": "2026-07-23",
                "sort_column": "new_tickets",
            }
        )


def test_decode_never_raises_a_bare_pydantic_or_key_error() -> None:
    """The route (and, in spirit, the frontend restore path) only ever has
    to catch one exception type."""
    bad_inputs: list[dict[str, str]] = [
        {},
        {"metrics": "resolved"},
        {"metrics": "resolved", "date_from": "not-a-date", "date_to": "2026-07-23"},
        {"metrics": "resolved", "date_from": "2026-07-10", "date_to": "2026-07-23",
         "granularity": "week"},
    ]
    for params in bad_inputs:
        try:
            decode_spec(params)
        except InvalidSpecQueryError:
            continue
        # decode_spec is allowed to succeed on some of these if a future
        # relaxation makes them valid; it must never leak a different
        # exception type.


class TestSpecFromQueryOrDefault:
    """The product behaviour (issue 13 acceptance criteria): no params is a
    plain visit (silent default); bad params fall back to the default WITH
    a Warning rather than raising."""

    def _default(self) -> ReportSpec:
        return ReportSpec(metrics=[Metric.RESOLVED], date_from="2026-07-10", date_to="2026-07-23")

    def test_no_params_returns_the_default_with_no_warning(self) -> None:
        spec, warnings = spec_from_query_or_default({}, self._default())

        assert spec == self._default()
        assert warnings == []

    def test_a_valid_link_is_used_as_is_with_no_warning(self) -> None:
        wanted = _full_spec()

        spec, warnings = spec_from_query_or_default(encode_spec(wanted), self._default())

        assert spec == wanted
        assert warnings == []

    def test_an_invalid_link_falls_back_to_the_default_with_a_warning(self) -> None:
        spec, warnings = spec_from_query_or_default(
            {"metrics": "not_a_real_metric", "date_from": "2026-07-10", "date_to": "2026-07-23"},
            self._default(),
        )

        assert spec == self._default()
        assert len(warnings) == 1
        assert "default" in warnings[0].lower()

    def test_a_stale_link_with_an_inverted_range_falls_back_with_a_warning(self) -> None:
        spec, warnings = spec_from_query_or_default(
            {"metrics": "resolved", "date_from": "2026-07-23", "date_to": "2026-07-10"},
            self._default(),
        )

        assert spec == self._default()
        assert len(warnings) == 1
