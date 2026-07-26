"""`to_csv(spec, table) -> str` — CSV export from a `ReportTable` (issue 10,
architecture.md §3 the `exporters` row).

Pure function, same as `engine.execute`: no I/O, no re-aggregation. It reads
the exact `ReportTable` the preview renders — the same columns, the same
rows, the same totals — so the file and the screen structurally cannot
disagree (PRD "Exports", user story 34). Layout mirrors
`frontend/src/ReportTable.tsx` deliberately: a Day column (long layout only),
a group column (Actor/Mailbox, shown whenever the report is grouped, or
whenever the layout is pivot), then one column per `table.columns` entry,
then a totals row.

**CSV is pure data** (issue 10): the file begins at the header row. No
preamble, no comment lines, no notes rows — anything above the header
breaks naive parsing. Context (Coverage Window, the hours-not-seconds note,
`ReportTable.warnings`) travels in the Excel export instead (issue 11).

**Units are baked into the header**, not a separate row: a Duration Metric's
`ColumnMeta.label` gets an `" (h)"` suffix, exactly the same string
`ReportTable.tsx` appends on screen (`column.unit === "hours" ? " (h)" :
""`) — so a header can never say something different in the file than it
says in the browser.

**A withheld `None` renders as an empty field in CSV — deliberately NOT
the em dash the screen and the (issue 11) XLSX data sheet use, and
deliberately never `0`.** CSV is the machine-readable format (PRD
"Exports"): an empty field is the conventional, unambiguous NA marker a
consumer's own tooling already understands (`pandas.read_csv` parses an
empty cell to `NaN` and leaves the column numeric; a stray `"—"` forces the
whole column to `object` dtype and breaks `.astype(float)` — user story 33's
"loads into a spreadsheet or a script without hand-editing", architecture.md
§12). A dash is still right where a *human* is reading the value directly —
the on-screen table (`ReportTable.tsx`: `value === null ? "—" : value`,
unchanged) and the XLSX data sheet issue 11 will add — because there the
caveat travels with the cell. Do not "fix" this back to a dash for
consistency with those: the two encodings solve two different problems for
two different readers, and a single dash in one CSV cell is enough to
poison a whole column's dtype for a script that never sees the screen.
`0` is never used either way: it would be a lie (`engine.py` module
docstring; `ReportSpec` "Table semantics").
"""

import csv
import io

from app.models import ColumnMeta, ReportSpec, ReportTable

WITHHELD = ""
"""The sentinel a withheld (`None`) cell renders as — see module docstring."""

_GROUP_COLUMN_LABELS = {"agent": "Actor", "mailbox": "Mailbox"}


def to_csv(spec: ReportSpec, table: ReportTable) -> str:
    """Render `table` as CSV text, laid out the way `spec` says the report is
    laid out (`layout`, `group_by`) — see module docstring for the exact
    correspondence with `ReportTable.tsx`."""
    is_pivot = spec.layout == "pivot"
    has_groups = spec.group_by != "none" and any(
        row.group_label is not None for row in table.rows
    )
    show_group_column = has_groups or is_pivot
    group_column_label = _GROUP_COLUMN_LABELS.get(spec.group_by, "") if has_groups else ""

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    header: list[str] = []
    if not is_pivot:
        header.append("Day")
    if show_group_column:
        header.append(group_column_label)
    header.extend(_column_header(column) for column in table.columns)
    writer.writerow(header)

    for row in table.rows:
        line: list[str] = []
        if not is_pivot:
            line.append(row.bucket)
        if show_group_column:
            line.append(row.group_label if has_groups else "")
        line.extend(_render(row.values.get(column.key)) for column in table.columns)
        writer.writerow(line)

    totals_line: list[str] = []
    if not is_pivot:
        totals_line.append("Total")
    if show_group_column:
        totals_line.append("Total" if is_pivot else "")
    totals_line.extend(_render(table.totals.get(column.key)) for column in table.columns)
    writer.writerow(totals_line)

    return buffer.getvalue()


def _column_header(column: ColumnMeta) -> str:
    suffix = " (h)" if column.unit == "hours" else ""
    return f"{column.label}{suffix}"


def _render(value: float | None) -> str:
    """`None` -> the withheld sentinel. A whole-number float renders without
    a trailing `.0` — `ReportRow.values`/`ReportTable.totals` are typed
    `float` even for Counters (a `resolved` count arrives as `16372.0`), but
    the browser's `JSON.parse` + JS number formatting drops that trailing
    `.0` on screen; rendering `str(value)` verbatim here would print
    `16372.0` in the file for a number that reads as `16372` on screen,
    breaking the "file matches the screen" guarantee this exporter exists
    for. A genuine fractional Duration Metric average still prints in full."""
    if value is None:
        return WITHHELD
    if value.is_integer():
        return str(int(value))
    return str(value)
