"""The single source of every assumption stated about the upstream data (issue 09).

The brief grades transparency about assumptions as a product feature, not a
documentation chore (PRD "Grading context"). This module is the ONE place
that text is written down. The coverage-banner modal
(`app/api/v1/routers/assumptions.py`) reads it at request time; the future
Excel "Report info" sheet (issue 11) must do the same rather than keep a
second copy — that is what makes the two structurally incapable of drifting
apart, not merely written to match today.

`build_assumptions()` is a pure function of the `CoverageWindow` (no I/O):
the partial-final-day note names the window's actual last day, so it stays
correct if the upstream's coverage ever moves, without anyone editing prose.
Everything else here is a fact about the upstream contract itself
(api-report-fresh.md) and does not vary with the window.
"""

from dataclasses import dataclass

from app.upstream import CoverageWindow


@dataclass(frozen=True)
class AssumptionNote:
    """One assumption, in the exact words shown to the user and, later, the
    exporter. `id` is a stable machine key (e.g. for anchors/testing);
    `title` and `body` are the only text either consumer renders."""

    id: str
    title: str
    body: str


def build_assumptions(coverage: CoverageWindow) -> list[AssumptionNote]:
    """Every stated assumption about the upstream data, in display order.

    Order follows the issue's own list: the units finding first (it is the
    one a reviewer is explicitly grading for evidence, not assertion), then
    the two other hard structural limits (buckets, cross-tab), then the two
    metric-level caveats, then the two hygiene notes.
    """
    return [
        AssumptionNote(
            id="units_hours",
            title="Duration metrics are in hours, not the documented seconds",
            body=(
                "The upstream documentation states time metrics are in seconds. That claim "
                "does not survive arithmetic, so we do not take it at face value. We found "
                "actor-days where a duration metric's `_count` companion equals exactly 1 — "
                "meaning the reported value is one single ticket's duration, with no averaging "
                "involved to obscure the scale. Read as seconds, the median single-ticket "
                "resolve time is 1.1s and the median handle time is 0.014s: neither is a "
                "physically plausible duration for a human support interaction. Read as hours, "
                "the same samples give a median resolve time of 1.06h, a median first-reply "
                "time of 1.42h, and a median handle time of about 50 seconds — magnitudes that "
                "are simultaneously plausible for every duration metric at once, which no other "
                "reading achieves. We therefore treat every duration metric's value as a SUM "
                "expressed in hours over its bucket, with the `_count` array as its denominator, "
                "and aggregate it as Σvalue / Σcount — never by averaging the "
                "per-bucket averages, which cannot reproduce the same number."
            ),
        ),
        AssumptionNote(
            id="daily_utc_buckets",
            title="Buckets are whole UTC calendar days, and no other granularity exists",
            body=(
                "The request fields that claim to control granularity or timezone "
                "(`time_unit`, `time_period`, `timezone`) are accepted but silently ignored: "
                "every value we tried, including `hour`, `week`, `month`, and non-UTC "
                "timezones, returned byte-identical daily-bucketed data anchored to UTC "
                "midnight. There is no hourly, weekly, or monthly view, and no way to align "
                "buckets to a non-UTC working day. We do not offer a granularity or timezone "
                "control that would silently do nothing."
            ),
        ),
        AssumptionNote(
            id="no_actor_by_mailbox_crosstab",
            title="There is no Actor-by-Mailbox cross-tab, and it cannot be produced at any price",
            body=(
                "The upstream returns two independent breakdowns of the same totals — by "
                "Actor and by Mailbox — but never both together. Breakdown entries carry no "
                "field linking an Actor to the Mailboxes they worked in, so a question like "
                "“how many tickets did this Actor resolve in this Mailbox” cannot be "
                "answered from this data, no matter how the request is shaped. A Report Spec can "
                "group by Actor or by Mailbox, never both at once, so this limit is structural "
                "rather than a validation error you might work around."
            ),
        ),
        AssumptionNote(
            id="actioned_emails_not_additive_across_actors",
            title="actioned_emails cannot be summed across Actors",
            body=(
                "Every metric reconciles exactly between the top-level totals and both "
                "breakdowns, with one exception: summing `actioned_emails` across all Actors "
                "overshoots the true total by about 52% (28,941 versus 19,024), because an "
                "email actioned by more than one Actor is credited to each of them. The same "
                "metric reconciles exactly (0% residual) when summed across Mailboxes instead, "
                "so the double-count is specific to the Actor breakdown. We show "
                "`actioned_emails` per Actor — it is a legitimate figure for one person — "
                "but withhold any “all Actors” total for it rather than publish a wrong "
                "number."
            ),
        ),
        AssumptionNote(
            id="open_metric_hidden",
            title="The open metric is always empty upstream and is hidden from the picker",
            body=(
                "`open` is reported as zero in every bucket, for the top-level totals and for "
                "all 108 Actors and 103 Mailboxes, under every date range and query we tried. "
                "There is nothing to report, so it is left out of the metric picker entirely "
                "rather than offered as a column that can only ever show zero — a report "
                "built from it would look real and be silently empty."
            ),
        ),
        AssumptionNote(
            id="partial_final_day",
            title="The final day in the window holds partial data",
            body=(
                f"The last day of the Coverage Window ({coverage.to_date}) has markedly lower "
                "volume than the days before it — in the reference window, about an eighth of "
                "the preceding day's ticket count (330 against 2,534) — consistent with the "
                "data having been "
                "captured partway through that day rather than the whole thing. Any trailing "
                "average or “last N days” view that includes this day will be dragged down "
                "by an incomplete count, not a real drop in activity. We flag it here, and "
                "wherever it could mislead a trend, rather than silently including it as if it "
                "were a full day."
            ),
        ),
        AssumptionNote(
            id="actor_list_mixes_people_and_role_accounts",
            title="The Actor list mixes real people with role accounts",
            body=(
                "The 108 Actors returned upstream include what look like real individuals "
                "(e.g. “Elena Kaur”) alongside shared role or system accounts such as "
                "“Support” and “Billing”. Nothing in the data marks the difference — "
                "there is no role, team, or active-user flag on an Actor entry. We surface this "
                "rather than filter it, so a shared queue's activity is not read as one person's "
                "individual performance."
            ),
        ),
    ]
