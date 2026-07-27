"""`app/agent/prompts/report_agent_system.jinja` + `app/agent/tools.py`'s
`_TOOL_DESCRIPTIONS` (issue 08 — system prompt rewrite and tool-schema
description overhaul).

Offline, no model: renders the real Jinja template through `llm.py`'s own
`_system_prompt` helper against the committed fixture dataset, and inspects
`build_tool_definitions()`'s output — the same two things a live Tool Step
actually sends. Assertions are structural/behavioral (all ten tools present,
each substantive, no few-shot transcript, coverage window and metric
catalogue survive rendering) rather than pinning exact prose, so the XML-vs-
markdown empirical call (settled by the live smoke test, not by this file)
can go either way without breaking these tests.
"""

from __future__ import annotations

import json

from app.agent.llm import _system_prompt
from app.agent.tools import TOOL_NAMES, build_tool_definitions
from app.models import Metric, ReportSpec
from app.upstream import _DEV_FIXTURE_PATH, METRIC_CATALOGUE, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


def _dataset():
    return _normalise_dataset(FIXTURE_RAW, WINDOW)


def _spec() -> ReportSpec:
    return ReportSpec.model_validate(
        {
            "metrics": [Metric.RESOLVED],
            "date_from": "2026-07-10",
            "date_to": "2026-07-16",
            "group_by": "none",
        }
    )


class TestSystemPromptRenders:
    def test_renders_without_jinja_errors(self):
        prompt = _system_prompt(_spec(), _dataset())
        assert isinstance(prompt, str)
        assert prompt.strip()

    def test_contains_the_coverage_window(self):
        dataset = _dataset()
        prompt = _system_prompt(_spec(), dataset)
        assert dataset.coverage.from_date in prompt
        assert dataset.coverage.to_date in prompt

    def test_contains_the_full_metric_catalogue(self):
        prompt = _system_prompt(_spec(), _dataset())
        for info in METRIC_CATALOGUE:
            assert info.key in prompt

    def test_contains_the_current_spec_as_json(self):
        spec = _spec()
        prompt = _system_prompt(spec, _dataset())
        assert '"resolved"' in prompt
        assert "2026-07-10" in prompt

    def test_uses_xml_style_section_tags(self):
        # architecture.md / PRD: the prompt's sections are XML tags, not `##`
        # markdown headings — a genuinely open, empirically-settled question
        # (see the live smoke test), but the structure this slice ships with.
        prompt = _system_prompt(_spec(), _dataset())
        assert "<coverage_window>" in prompt
        assert "</coverage_window>" in prompt
        assert "<metric_catalogue>" in prompt
        assert "<tools>" in prompt or "<tool_notes>" in prompt

    def test_no_markdown_heading_sections_remain(self):
        prompt = _system_prompt(_spec(), _dataset())
        assert "## Coverage Window" not in prompt
        assert "## Metric catalogue" not in prompt
        assert "## Tools" not in prompt

    def test_no_few_shot_tool_call_transcript(self):
        prompt = _system_prompt(_spec(), _dataset())
        # No hand-authored user -> tool-call -> answer worked examples: the
        # only fenced JSON block should be the live spec dump, never a
        # transcript role marker or a second/third code fence.
        assert prompt.count("```") == 2  # one opening + one closing fence
        for marker in ("User:", "Assistant:", "Example:", "e.g. call set_"):
            assert marker not in prompt

    def test_mentions_get_meta_before_set_filter_for_uncertain_names(self):
        prompt = _system_prompt(_spec(), _dataset())
        assert "get_meta" in prompt
        assert "set_filter" in prompt

    def test_permits_optional_markdown_table_in_final_prose(self):
        prompt = _system_prompt(_spec(), _dataset())
        assert "table" in prompt.lower()

    def test_never_calls_a_person_an_agent(self):
        prompt = _system_prompt(_spec(), _dataset())
        assert "Actor" in prompt
        assert "Mailbox" in prompt


class TestToolDescriptions:
    def _definitions_by_name(self) -> dict[str, dict]:
        return {d["function"]["name"]: d["function"] for d in build_tool_definitions()}

    def test_all_ten_tools_have_descriptions(self):
        by_name = self._definitions_by_name()
        assert set(by_name) == TOOL_NAMES
        assert len(by_name) == 10

    def test_each_description_is_substantive(self):
        by_name = self._definitions_by_name()
        for name, function in by_name.items():
            description = function["description"]
            # "3-4+ sentences each" (issue) — a loose proxy: long enough and
            # more than one sentence, not a one-liner restating the name.
            assert len(description) >= 200, f"{name} description too short"
            assert description.count(". ") >= 2, f"{name} description too shallow"

    def test_set_filter_description_is_fully_self_sufficient(self):
        by_name = self._definitions_by_name()
        description = by_name["set_filter"]["description"].lower()
        assert "case-insensitive" in description or "case insensitive" in description
        assert "substring" in description
        assert "empty string" in description
        assert "clear" in description
        assert "none" in description  # group_by == "none" behavior
        assert "no effect" in description or "no-op" in description or "ignored" in description

    def test_no_description_contains_a_tool_call_transcript(self):
        by_name = self._definitions_by_name()
        for name, function in by_name.items():
            description = function["description"]
            assert "User:" not in description
            assert "Assistant:" not in description
            assert "```" not in description
