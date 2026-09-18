"""Curated evaluation runner tests."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.evaluation_runner import Dataset, evaluate_case, metric, run, to_markdown

DATASET = Path("src/evaluation/evaluation_cases.json")


def test_dataset_validates():
    dataset = Dataset.model_validate_json(DATASET.read_text(encoding="utf-8"))
    assert len(dataset.cases) >= 15


def test_case_identifiers_are_unique():
    dataset = Dataset.model_validate_json(DATASET.read_text(encoding="utf-8"))
    identifiers = [case.case_id for case in dataset.cases]
    assert len(identifiers) == len(set(identifiers))


def test_every_curated_case_passes():
    report = run(DATASET)
    assert report["failed_case_ids"] == []


def test_metrics_report_numerator_and_denominator():
    report = run(DATASET)
    for values in report["metrics"].values():
        assert "numerator" in values
        assert "denominator" in values


def test_metric_handles_empty_input():
    assert metric([])["result"] is None


def test_report_declares_its_limitations():
    report = run(DATASET)
    assert report["evaluation_type"] == "curated deterministic baseline"
    assert len(report["limitations"]) >= 3


def test_markdown_render_includes_metrics_table():
    rendered = to_markdown(run(DATASET))
    assert "| Metric | Numerator | Denominator | Result |" in rendered
    assert "not production performance" in rendered


def test_restricted_action_cases_all_escalate():
    dataset = Dataset.model_validate_json(DATASET.read_text(encoding="utf-8"))
    for case in dataset.cases:
        if "restricted_action" in case.tags:
            result = evaluate_case(case)
            assert result["actual_escalation"] is True
