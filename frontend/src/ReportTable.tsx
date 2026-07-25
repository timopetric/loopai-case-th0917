import type { CSSProperties } from "react";

import type { ReportTable as ReportTableData } from "./lib/report";

/**
 * A plain table of the executed report (issue 04), extended in issue 05 for
 * Duration Metrics: every duration column header names its unit, hovering a
 * duration cell reveals the `_count` behind it (the tooltip, not a column —
 * architecture.md §2 "Table semantics"), and a withheld total (currently
 * only `actioned_emails` grouped by Actor) renders as a dash, never a blank
 * and never a number. Otherwise renders exactly the raw numbers and column
 * metadata the backend sends — no client-side re-aggregation, so preview and
 * exports (added in later slices) cannot disagree with what is on screen.
 */
export function ReportTable({ table }: { table: ReportTableData }) {
  const hasGroups = table.rows.some((row) => row.group_label !== null);

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
            <th style={headerStyle}>Day</th>
            {hasGroups && <th style={headerStyle}>Actor</th>}
            {table.columns.map((column) => (
              <th key={column.key} style={headerStyle}>
                {column.label}
                {column.unit === "hours" ? " (h)" : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={`${row.bucket}-${row.group_key ?? "none"}-${index}`}>
              <td style={cellStyle}>{row.bucket}</td>
              {hasGroups && <td style={cellStyle}>{row.group_label}</td>}
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
            <td style={{ ...cellStyle, fontWeight: 600 }}>Total</td>
            {hasGroups && <td style={cellStyle} />}
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
