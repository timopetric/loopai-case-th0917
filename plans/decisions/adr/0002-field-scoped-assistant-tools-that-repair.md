# Field-scoped Assistant tools that repair rather than reject

The Assistant edits a Report Spec through tool calls, and the choice was between one atomic
`update_spec(patch)` and several field-scoped tools. We chose **field-scoped tools**, each
covering a cohesive unit (`set_date_range`, `set_metrics`, `set_grouping`, `set_sort`,
`set_columns`, `set_chart`, `set_layout`) plus the read-only `run_report` and `get_meta`.
Each call applies immediately and emits its own `spec` event, so the builder controls visibly
move one step at a time — the deciding factor, since a single atomic patch makes the whole
report snap into place in one frame, which reads as a page refresh rather than as an
assistant doing work.

When a call invalidates an earlier field — `set_metrics` dropping the metric that
`chart_metric` or `sort` referenced — the backend **repairs** the spec and reports what it
adjusted in the tool result, rather than returning a validation error. Genuine input errors
(bad enum, bad date) still error and get one retry.

## Considered Options

- **One atomic `update_spec(patch)`** — never transiently invalid, and compound requests cost
  a single Tool Step. Rejected for the progressive-rendering reason above; the Tool Step
  argument also weakened once the budget moved from 8 to 20.
- **Raw per-field tools** (`set_date_from` / `set_date_to`) — rejected because they permit an
  inverted range mid-sequence, manufacturing a validation error from a perfectly valid user
  intent. Hence "cohesive unit", not "one field per tool".
- **Erroring on cross-field drift** — rejected: it burns a Tool Step on bookkeeping the model
  shouldn't have to reason about, and risks thrashing.

## Consequences

- `architecture.md`'s earlier "exactly three tools" note is superseded. The scratch lab's 63
  tests proved **patch semantics over full replacement**, which field-scoped tools also
  satisfy; they did not settle granularity.
- Repair is silent to validation but *not* silent to the user: adjustments surface in the
  tool result (so the Assistant can mention them in prose) and in `ReportTable.warnings` (so
  they appear as banners and in the exported notes row).
- Repairs are reported with **batch reconciliation**: within one model message, an adjustment
  to a field is discarded if a later call in the same batch explicitly sets that field.
  Otherwise the Assistant narrates repairs that didn't survive the turn. See
  `architecture.md` §5 for the full repair-vs-error taxonomy.
- The repair rules are the most state-heavy part of the Assistant and are currently
  specified rather than exhaustively tested. A proper state design and test suite is required
  before this is production-grade.
