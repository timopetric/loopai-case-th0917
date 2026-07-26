"""`exporters.to_csv` unit tests (issue 10).

The CSV is read back with Python's own `csv` module — a plain consumer, not
the raw string — because the point of "pure data" is that a standard reader
needs no special handling. Content is checked against a `ReportTable` built
by hand (not through `engine.execute`) so these tests describe the exporter's
contract in isolation from aggregation correctness, which `test_engine.py`
already covers.
"""

import csv
import io
import json

from app.engine import execute
from app.exporters import to_csv
from app.models import ColumnMeta, Metric, ReportRow, ReportSpec, ReportTable
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset


def _spec(**overrides) -> ReportSpec:
    body = dict(
        metrics=["resolved"],
        date_from="2026-07-10",
        date_to="2026-07-23",
        granularity="day",
        group_by="none",
    )
    body.update(overrides)
    return ReportSpec(**body)


def _read_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_csv_parses_with_a_standard_reader_and_has_a_header_plus_one_row_per_report_row() -> None:
    table = ReportTable(
        columns=[ColumnMeta(key="resolved", label="Resolved", kind="counter", unit="count")],
        rows=[
            ReportRow(
                bucket="2026-07-10", group_key=None, group_label=None, values={"resolved": 5}
            ),
            ReportRow(
                bucket="2026-07-11", group_key=None, group_label=None, values={"resolved": 7}
            ),
        ],
        totals={"resolved": 12},
    )

    text = to_csv(_spec(), table)
    rows = _read_csv(text)

    # header, two data rows, one totals row — no preamble above the header.
    assert len(rows) == 4
    assert rows[0][0] == "Day"
    assert rows[1] == ["2026-07-10", "5"]
    assert rows[2] == ["2026-07-11", "7"]
    assert rows[3] == ["Total", "12"]


def test_a_duration_metric_column_header_names_its_unit() -> None:
    table = ReportTable(
        columns=[
            ColumnMeta(key="resolve_time", label="Resolve time", kind="duration", unit="hours")
        ],
        rows=[
            ReportRow(
                bucket="2026-07-10", group_key=None, group_label=None, values={"resolve_time": 1.5}
            )
        ],
        totals={"resolve_time": 1.5},
    )

    rows = _read_csv(to_csv(_spec(metrics=["resolve_time"]), table))

    assert rows[0] == ["Day", "Resolve time (h)"]


def test_a_withheld_total_renders_as_an_empty_field_not_a_dash_and_not_zero() -> None:
    """The non-additive rule (architecture.md "Table semantics"): `actioned_emails`
    totalled across Actors is withheld (`None`). In CSV — the machine-readable
    format — that renders as an empty field, not the on-screen dash: an
    em dash in a numeric column forces a script's parser to treat the whole
    column as text (user story 33, architecture.md §12). Never a lying `0`
    either way."""
    table = ReportTable(
        columns=[
            ColumnMeta(key="actioned_emails", label="Actioned emails", kind="counter", unit="count")
        ],
        rows=[
            ReportRow(
                bucket="2026-07-10",
                group_key="a1",
                group_label="Alice",
                values={"actioned_emails": 3},
            )
        ],
        totals={"actioned_emails": None},
    )

    rows = _read_csv(to_csv(_spec(metrics=["actioned_emails"], group_by="agent"), table))

    assert rows[0] == ["Day", "Actor", "Actioned emails"]
    assert rows[1] == ["2026-07-10", "Alice", "3"]
    totals_row = rows[-1]
    assert totals_row[-1] == ""
    assert totals_row[-1] != "—"
    assert totals_row[-1] != "0"


def test_a_zero_count_duration_average_in_an_ordinary_data_row_is_an_empty_field() -> None:
    """The withheld sentinel isn't only a totals-row concern: a zero-ticket
    Actor's Duration Metric average is `None` on an ordinary data row too
    (`engine._display_value`), and that is exactly where 47 of 108 rows
    carried a stray dash before this fix — the totals row alone never
    exercised that path."""
    table = ReportTable(
        columns=[
            ColumnMeta(key="resolved", label="Resolved", kind="counter", unit="count"),
            ColumnMeta(key="resolve_time", label="Resolve time", kind="duration", unit="hours"),
        ],
        rows=[
            ReportRow(
                bucket="total",
                group_key="a1",
                group_label="Idle Actor",
                values={"resolved": 0, "resolve_time": None},
            ),
            ReportRow(
                bucket="total",
                group_key="a2",
                group_label="Busy Actor",
                values={"resolved": 4, "resolve_time": 2.5},
            ),
        ],
        totals={"resolved": 4, "resolve_time": 2.5},
    )

    rows = _read_csv(
        to_csv(_spec(metrics=["resolved", "resolve_time"], group_by="agent"), table)
    )

    idle_row = next(r for r in rows if r[1] == "Idle Actor")
    busy_row = next(r for r in rows if r[1] == "Busy Actor")
    assert idle_row[-1] == ""
    assert busy_row[-1] == "2.5"


def test_every_value_in_a_numeric_column_is_empty_or_parses_as_a_float() -> None:
    """The §12 property directly, without adding pandas as a dependency:
    `float()` over every non-empty cell in a metric column must not raise —
    the same guarantee `pandas.read_csv(...)[col].astype(float)` depends on.
    A mix of real numbers and a withheld zero-count average in the same
    column is exactly the shape that broke before this fix."""
    table = ReportTable(
        columns=[
            ColumnMeta(key="resolve_time", label="Resolve time", kind="duration", unit="hours")
        ],
        rows=[
            ReportRow(
                bucket="total", group_key="a1", group_label="Idle", values={"resolve_time": None}
            ),
            ReportRow(
                bucket="total", group_key="a2", group_label="Busy", values={"resolve_time": 3.25}
            ),
        ],
        totals={"resolve_time": None},
    )

    rows = _read_csv(to_csv(_spec(metrics=["resolve_time"], group_by="agent"), table))

    header, *data_and_totals = rows
    column_index = header.index("Resolve time (h)")
    cells = [r[column_index] for r in data_and_totals]

    assert cells == ["", "3.25", ""]
    for cell in cells:
        if cell != "":
            float(cell)  # must not raise


def test_a_group_label_containing_a_comma_and_a_quote_round_trips_through_csv() -> None:
    """CSV correctness failures are usually escaping failures — a group label
    like a real Actor name can contain a comma or an embedded quote, and the
    stdlib `csv` reader must hand back the exact original string."""
    tricky_name = 'Smith, Jane "JJ"'
    table = ReportTable(
        columns=[ColumnMeta(key="resolved", label="Resolved", kind="counter", unit="count")],
        rows=[
            ReportRow(
                bucket="2026-07-10", group_key="a1", group_label=tricky_name, values={"resolved": 2}
            )
        ],
        totals={"resolved": 2},
    )

    rows = _read_csv(to_csv(_spec(group_by="agent"), table))

    assert rows[1][1] == tricky_name


def test_column_order_follows_report_table_columns_not_metrics_order() -> None:
    """`engine._ordered_metrics` already applies `columns_order` to build
    `ReportTable.columns` (issue 07) — the exporter just has to read that
    list in the order given, not re-derive an order of its own."""
    table = ReportTable(
        columns=[
            ColumnMeta(key="new_tickets", label="New tickets", kind="counter", unit="count"),
            ColumnMeta(key="resolved", label="Resolved", kind="counter", unit="count"),
        ],
        rows=[
            ReportRow(
                bucket="2026-07-10",
                group_key=None,
                group_label=None,
                values={"resolved": 5, "new_tickets": 9},
            )
        ],
        totals={"resolved": 5, "new_tickets": 9},
    )

    rows = _read_csv(to_csv(_spec(metrics=["resolved", "new_tickets"]), table))

    assert rows[0] == ["Day", "New tickets", "Resolved"]
    assert rows[1] == ["2026-07-10", "9", "5"]


def test_csv_content_matches_the_real_report_table_from_the_committed_fixture() -> None:
    """The exporter derives from the same `ReportTable` the preview renders
    (issue 10's core guarantee) — proved here with the real fixture dataset,
    not a hand-built table, going through `engine.execute` exactly as the
    `/report` route does."""
    dataset = _normalise_dataset(
        json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"],
        CoverageWindow(from_date="2026-07-10", to_date="2026-07-23"),
    )
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from="2026-07-10",
        date_to="2026-07-23",
        granularity="total",
        group_by="none",
    )

    table = execute(spec, dataset)
    rows = _read_csv(to_csv(spec, table))

    assert rows[0] == ["Day", "Resolved"]
    assert rows[1] == ["total", str(int(table.rows[0].values["resolved"]))]
    assert rows[1][1] == "16372"
    assert rows[2] == ["Total", "16372"]
