import type { CSSProperties } from "react";

import type { ReportTable as ReportTableData } from "./lib/report";

/**
 * A plain table of the executed report (issue 04): day × Actor rows plus a
 * totals row. Renders exactly the raw numbers and column metadata the
 * backend sends — no client-side re-aggregation, so preview and exports
 * (added in later slices) cannot disagree with what is on screen.
 */
export function ReportTable({ table }: { table: ReportTableData }) {
  const hasGroups = table.rows.some((row) => row.group_label !== null);

  return (
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
            {table.columns.map((column) => (
              <td key={column.key} style={cellStyle}>
                {row.values[column.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td style={{ ...cellStyle, fontWeight: 600 }}>Total</td>
          {hasGroups && <td style={cellStyle} />}
          {table.columns.map((column) => (
            <td key={column.key} style={{ ...cellStyle, fontWeight: 600 }}>
              {table.totals[column.key]}
            </td>
          ))}
        </tr>
      </tfoot>
    </table>
  );
}

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
