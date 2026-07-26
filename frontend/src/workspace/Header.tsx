import { AssumptionsModal } from "../AssumptionsModal";
import type { AssumptionNote } from "../lib/assumptions";
import type { Meta } from "../lib/meta";
import type { Preset } from "../lib/report";
import { useThemeStore } from "../store/themeStore";
import { SegmentedControl } from "../ui/SegmentedControl";

/**
 * The workspace header (issue 02: frontend-rework) — product name, the
 * Coverage Window, the assumptions link, the presets and the export
 * actions, exactly the list the issue names. Everything here is either
 * fetch-derived state owned by `WorkspaceShell` (`meta`, `assumptions`) or a
 * callback into it (`onApplyPreset`, `onExport`) — this component holds no
 * Report Spec state of its own, only the `showAssumptions` toggle for its
 * own modal.
 *
 * The old `App.tsx`'s developer-only status paragraph is gone — the PRD
 * requires the status line users used to see removed entirely.
 */
/**
 * The explicit theme override (issue 07: frontend-rework, architecture.md
 * §7) — a three-way choice between following the operating system and
 * pinning either theme for the session. Kept local to `Header.tsx` (not a
 * `ui/` primitive): it is a one-off composition of the existing
 * `SegmentedControl` primitive plus `store/themeStore.ts`, specific to
 * this one chrome element, rather than a reusable building block other
 * panes reach for the way `Chip`/`TextInput`/`SectionHeader` are.
 *
 * `SegmentedControl` is generic over a string union, so the store's `null`
 * ("follow the OS") is represented here as the literal `"system"` and
 * translated back to `null` in `onChange` — the store itself never sees
 * the string `"system"`.
 */
function ThemeToggle() {
  const override = useThemeStore((state) => state.override);
  const setOverride = useThemeStore((state) => state.setOverride);
  const value = override ?? "system";

  return (
    <div className="w-48">
      <SegmentedControl
        name="Theme"
        value={value}
        onChange={(next) => setOverride(next === "system" ? null : next)}
        options={[
          { value: "system", label: "System" },
          { value: "light", label: "Light" },
          { value: "dark", label: "Dark" },
        ]}
      />
    </div>
  );
}

export function Header({
  meta,
  assumptions,
  showAssumptions,
  onShowAssumptions,
  onCloseAssumptions,
  presets,
  onApplyPreset,
  onExportCsv,
  onExportXlsx,
  exportDisabled,
  urlWarning,
  exportError,
}: {
  meta: Meta | null;
  assumptions: AssumptionNote[] | null;
  showAssumptions: boolean;
  onShowAssumptions: () => void;
  onCloseAssumptions: () => void;
  presets: Preset[];
  onApplyPreset: (preset: Preset) => void;
  onExportCsv: () => void;
  onExportXlsx: () => void;
  exportDisabled: boolean;
  urlWarning: string | null;
  exportError: string | null;
}) {
  return (
    <header className="border-b border-hairline bg-cream-soft px-4 py-3">
      {meta?.dev_fake_upstream && (
        <p
          role="status"
          className="mb-2 rounded-md border border-beige-deep bg-cream px-3 py-2 text-body-sm-medium font-semibold text-ink-tint"
        >
          DEV_FAKE_UPSTREAM is on — this report is built from the committed fixture, not live
          data.
        </p>
      )}
      {meta?.dev_fake_llm && (
        <p
          role="status"
          className="mb-2 rounded-md border border-beige-deep bg-cream px-3 py-2 text-body-sm-medium font-semibold text-ink-tint"
        >
          DEV_FAKE_LLM is on — the Assistant runs a scripted conversation, not a real model.
        </p>
      )}
      {urlWarning && (
        <p role="alert" className="mb-2 text-body-sm text-danger">
          {urlWarning}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-heading-3 text-ink">loopai</h1>
          {meta && (
            <p className="text-body-sm text-steel">
              Coverage Window: {meta.coverage_window.from_date} – {meta.coverage_window.to_date}
              {" · "}
              <button
                type="button"
                onClick={onShowAssumptions}
                disabled={!assumptions}
                className="cursor-pointer border-none bg-transparent p-0 text-body-sm text-primary underline underline-offset-2 disabled:cursor-default disabled:text-muted"
              >
                What assumptions does this report make?
              </button>
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ThemeToggle />
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => onApplyPreset(preset)}
              className="h-11 rounded-md border border-hairline-strong bg-canvas px-3 text-body-sm text-ink hover:bg-cream-soft"
            >
              {preset.label}
            </button>
          ))}
          <button
            type="button"
            onClick={onExportCsv}
            disabled={exportDisabled}
            className="h-11 rounded-md bg-primary px-3 text-body-sm-medium font-medium text-on-primary hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-hairline-strong disabled:text-muted"
          >
            Download CSV
          </button>
          <button
            type="button"
            onClick={onExportXlsx}
            disabled={exportDisabled}
            className="h-11 rounded-md bg-primary px-3 text-body-sm-medium font-medium text-on-primary hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-hairline-strong disabled:text-muted"
          >
            Download Excel
          </button>
        </div>
      </div>

      {exportError && (
        <p role="alert" className="mt-2 text-body-sm text-danger">
          {exportError}
        </p>
      )}

      {showAssumptions && assumptions && (
        <AssumptionsModal notes={assumptions} onClose={onCloseAssumptions} />
      )}
    </header>
  );
}
