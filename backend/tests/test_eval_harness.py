"""Tests for eval harness suite runner and EvalRun DB persistence."""

import pytest
from core.eval.harness import EvalCase, EvalResult, run_suite
from core.models import EvalRun


@pytest.mark.django_db
def test_eval_harness_run_suite_and_persist():
    cases = [
        EvalCase(id="case_1", input={"text": "A"}, expected="A"),
        EvalCase(id="case_2", input={"text": "B"}, expected="B"),
    ]

    def mock_scorer(case: EvalCase) -> EvalResult:
        return EvalResult(case_id=case.id, passed=True, score=1.0)

    result = run_suite(
        suite="test_suite_v1",
        module="research",
        logic_version="1.0",
        cases=cases,
        metric="accuracy",
        scorer=mock_scorer,
        save=True,
    )

    assert result.value == 1.0
    assert result.n_items == 2

    # Verify persisted to EvalRun
    eval_row = EvalRun.objects.filter(suite="test_suite_v1").latest("created_at")
    assert eval_row.module == "research"
    assert eval_row.metric == "accuracy"
    assert eval_row.value == 1.0
    assert eval_row.n_items == 2
