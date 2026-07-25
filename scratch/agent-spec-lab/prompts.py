"""Helper to render the report-agent system prompt for tests / the real loop."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import METRIC_DESCRIPTIONS, TIME_METRICS, Metric, ReportSpec

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_env = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    autoescape=select_autoescape(disabled_extensions=(".jinja",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_system_prompt(spec: ReportSpec, data_window: tuple) -> str:
    template = _env.get_template("report_agent_system.jinja")
    win_from, win_to = data_window
    return template.render(
        spec_json=spec.model_dump_json(indent=2),
        data_window_from=win_from,
        data_window_to=win_to,
        metrics=list(Metric),
        time_metrics=TIME_METRICS,
        time_metrics_list=", ".join(m.value for m in TIME_METRICS),
        descriptions=METRIC_DESCRIPTIONS,
    )
