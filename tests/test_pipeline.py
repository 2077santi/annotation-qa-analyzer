"""End-to-end check: the pipeline must find the problems planted in the synthetic data."""

import pytest

from qa.generate_data import DRIFTERS, OVER_FLAGGER, SELF_HARM_MISSER, generate
from qa.pipeline import run


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    root = tmp_path_factory.mktemp("run")
    generate(root / "data")
    return run(data_dir=root / "data", out_dir=root)


def subjects(result, kind):
    return {f["subject"] for f in result["findings"] if f["kind"] == kind}


def test_finds_every_drifting_annotator_and_no_one_else(result):
    assert subjects(result, "DRIFT") == DRIFTERS


def test_flags_the_missed_self_harm_as_critical(result):
    critical = [f for f in result["findings"] if f["severity"] == "critical"]
    assert [f["subject"] for f in critical] == [SELF_HARM_MISSER]
    assert "SELF_HARM" in critical[0]["evidence"]


def test_finds_the_over_flagger(result):
    assert OVER_FLAGGER in subjects(result, "SYSTEMATIC_BIAS")


def test_blames_the_guideline_for_news_and_sarcasm(result):
    assert {"news_reporting", "sarcasm"} <= subjects(result, "GUIDELINE_AMBIGUITY")


def test_actions_improve_projected_quality(result):
    s = result["summary"]
    assert s["label_quality_after_fixes"] > s["label_quality_now"]
