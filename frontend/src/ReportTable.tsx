import type { CSSProperties } from "react";

import type { ReportTable as ReportTableData, SortSpec } from "./lib/report";

/**
 * The group column header must follow the selected grouping (issue 06) —
 * this used to be hardcoded to "Actor" from when `group_by` could only ever
 * be "agent" (issue 04). The wire value stays `"agent"` (CONTEXT.md — the
 * upstream/spec spelling is correct and not renamed); only the label
 * shown to the user is "Actor".
 */
function groupColumnLabel(groupBy: "none" | "agent" | "mailbox"): string | null {
  if (groupBy === "agent") return "Actor";
  if (groupBy === "mailbox") return "Mailbox";
  return null;
}

/**
 * A plain table of the executed report (issue 04), extended in issue 05 for
 * Duration Metrics, and in issue 07 for the three table-presentation
 * controls — sort, column order, and the pivot layout:
 *
 * - **Sort** is a click on a column header, in the "long" layout only —
 *   pivot's columns are Buckets (dates), not metrics, and `spec.sort` names
 *   a metric, so it has nothing to bind to there (`app/engine.py`'s
 *   `_execute_pivot` docstring). The header shows an arrow for the sorted
 *   column and its direction; the *semantics* (within-Bucket, global only
 *   when the report has collapsed to one Bucket) live entirely in the
 *   engine — this component only reflects state, it never reorders rows
 *   itself, so the table and the exports (issues 10-11, which read the same
 *   `ReportTable.columns`/`rows` the engine already sorted) cannot disagree.
 * - **Column order**: `<`/`>` buttons per header move a column one slot;
 *   `App.tsx` recomputes the order from `table.columns` (the engine's own
 *   output) and resends it as `columns_order`, so the button always acts on
 *   what's actually on screen.
 * - **Pivot**: `layout === "pivot"` means `table.columns` are Buckets, not
 *   metrics, and `table.rows` are keyed by group only — `row.values` is
 *   indexed by Bucket date instead of by metric key. Rendering this through
 *   the *same* `table.columns.map(...)` as the long layout is deliberate:
 *   the column/value contract (`row.values[column.key]`) doesn't change
 *   between layouts, only what a "column" represents does. The one thing
 *   that must NOT happen is the long-layout's Day/metric column headers
 *   leaking into a pivot render (or vice versa) — hence the `layout`-gated
 *   branches below rather than one shared unconditional header.
 *
 * Otherwise renders exactly the raw numbers and column metadata the backend
 * sends — no client-side re-aggregation, so preview and exports cannot
 * disagree with what is on screen. The pivot "chart metric only" statement
 * (user story 17) is *not* re-derived here — it arrives as one of
 * `table.warnings` from `engine._execute_pivot`, the same banner every
 * other Warning already renders through, so there is exactly one place that
 * decides what the message says.
 */
export function ReportTable({
  table,
  groupBy,
  layout,
  sort,
  onSort,
  onMoveColumn,
}: {
  table: ReportTableData;
  groupBy: "none" | "agent" | "mailbox";
  layout: "long" | "pivot";
  sort: SortSpec | null;
  onSort: (columnKey: string) => void;
  onMoveColumn: (columnKey: string, direction: "left" | "right") => void;
}) {
  const groupLabel = groupColumnLabel(groupBy);
  const hasGroups = groupLabel !== null && table.rows.some((row) => row.group_label !== null);
  const isPivot = layout === "pivot";

  return (
    <>
      {table.warnings.length > 0 && (
        <ul role="alert" style={warningsStyle}>
          {table.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            {!isPivot && <th style={headerStyle}>Day</th>}
            {(hasGroups || isPivot) && (
              <th style={headerStyle}>{hasGroups ? groupLabel : ""}</th>
            )}
            {table.columns.map((column, index) => (
              <th key={column.key} style={headerStyle}>
                {isPivot ? (
                  <>
                    {column.label}
                    {column.unit === "hours" ? " (h)" : ""}
                  </>
                ) : (
                  <>
                    <button type="button" onClick={() => onSort(column.key)} style={sortButtonStyle}>
                      {column.label}
                      {column.unit === "hours" ? " (h)" : ""}
                      {sort?.column === column.key ? (sort.direction === "desc" ? " ▼" : " ▲") : ""}
                    </button>
                    <span style={moveButtonsStyle}>
                      <button
                        type="button"
                        disabled={index === 0}
                        onClick={() => onMoveColumn(column.key, "left")}
                        aria-label={`Move ${column.label} left`}
                        style={moveButtonStyle}
                      >
                        {"<"}
                      </button>
                      <button
                        type="button"
                        disabled={index === table.columns.length - 1}
                        onClick={() => onMoveColumn(column.key, "right")}
                        aria-label={`Move ${column.label} right`}
                        style={moveButtonStyle}
                      >
                        {">"}
                      </button>
                    </span>
                  </>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={`${row.bucket}-${row.group_key ?? "none"}-${index}`}>
              {!isPivot && <td style={cellStyle}>{row.bucket}</td>}
              {(hasGroups || isPivot) && (
                <td style={cellStyle}>{hasGroups ? row.group_label : ""}</td>
              )}
              {table.columns.map((column) => {
                const value = row.values[column.key];
                const count = row.counts[column.key];
                return (
                  <td
                    key={column.key}
                    style={cellStyle}
                    title={count !== undefined ? `${count} ticket${count === 1 ? "" : "s"}` : undefined}
                  >
                    {value === null ? "—" : value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            {!isPivot && <td style={{ ...cellStyle, fontWeight: 600 }}>Total</td>}
            {(hasGroups || isPivot) && (
              <td style={{ ...cellStyle, fontWeight: 600 }}>{isPivot ? "Total" : ""}</td>
            )}
            {table.columns.map((column) => {
              const value = table.totals[column.key];
              const count = table.total_counts[column.key];
              return (
                <td
                  key={column.key}
                  style={{ ...cellStyle, fontWeight: 600 }}
                  title={count !== undefined ? `${count} ticket${count === 1 ? "" : "s"}` : undefined}
                >
                  {value === null ? "—" : value}
                </td>
              );
            })}
          </tr>
        </tfoot>
      </table>
    </>
  );
}

const warningsStyle: CSSProperties = {
  background: "#fff3cd",
  color: "#664d03",
  border: "1px solid #ffe69c",
  borderRadius: 4,
  padding: "0.5rem 1rem",
  margin: "0 0 1rem 0",
};

const headerStyle: CSSProperties = {
  textAlign: "left",
  borderBottom: "2px solid #ccc",
  padding: "0.25rem 0.5rem",
  position: "sticky",
  top: 0,
  background: "white",
};

const cellStyle: CSSProperties = {
  borderBottom: "1px solid #eee",
  padding: "0.25rem 0.5rem",
};

const sortButtonStyle: CSSProperties = {
  background: "none",
  border: "none",
  font: "inherit",
  fontWeight: "inherit",
  color: "inherit",
  cursor: "pointer",
  padding: 0,
};

const moveButtonsStyle: CSSProperties = {
  display: "inline-block",
  marginLeft: "0.35rem",
};

const moveButtonStyle: CSSProperties = {
  border: "1px solid #ccc",
  background: "white",
  cursor: "pointer",
  fontSize: "0.7rem",
  lineHeight: 1,
  padding: "1px 4px",
  marginLeft: "2px",
};
