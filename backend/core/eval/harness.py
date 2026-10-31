"""
Eval harness — pytest-based, per-LLM-step golden sets.

Rules (rules.md rules 41-43, design doc 14.8):
  - A module cannot ship an LLM step without golden examples.
  - Suites run on every prompt/recipe/threshold/logic_version change.
  - Record item count with every score.
  - LLM judges: calibrated against human labels, different model family from generator.

This module provides:
  - EvalCase / EvalResult dataclasses
  - run_suite(): runs a named suite and saves to EvalRun
  - save_result(): writes one metric row
  - Threshold helper for regression detection
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class EvalCase:
    """One labeled example in a golden set."""

    id: str                          # Unique within the suite
    input: dict[str, Any]            # Whatever the component under test receives
    expected: Any                    # Ground-truth label / expected output
    tags: list[str] = dataclasses.field(default_factory=list)  # e.g. ["unanswerable", "adversarial"]
    notes: str = ""


@dataclasses.dataclass
class EvalResult:
    """Result for one case."""

    case_id: str
    passed: bool
    score: float                     # 0.0 – 1.0 where applicable
    actual: Any = None
    details: str = ""


@dataclasses.dataclass
class SuiteResult:
    """Aggregated result for a full suite run."""

    suite: str
    module: str
    logic_version: str
    metric: str
    value: float
    n_items: int
    results: list[EvalResult] = dataclasses.field(default_factory=list)
    judge_model: str = ""
    judge_human_agreement: float | None = None


def run_suite(
    *,
    suite: str,
    module: str,
    logic_version: str,
    cases: list[EvalCase],
    metric: str,
    scorer: Callable[[EvalCase], EvalResult],
    threshold: float | None = None,
    judge_model: str = "",
    save: bool = True,
) -> SuiteResult:
    """
    Run every case through the scorer, compute the metric, optionally save to DB.

    Parameters
    ----------
    suite:         Suite name (e.g. "summarizer_golden_v1")
    module:        App module name (e.g. "research")
    logic_version: Recipe logic_version being evaluated
    cases:         List of EvalCase instances (the golden set)
    metric:        Metric name (e.g. "entity_support_rate")
    scorer:        Function that takes an EvalCase and returns EvalResult
    threshold:     If provided and result.value < threshold, logs a warning.
                   The harness never blocks — that's the CI gate's job.
    judge_model:   If an LLM judge was used, record its name.
    save:          Whether to write to the EvalRun table.

    Returns
    -------
    SuiteResult with all per-case results and the aggregate metric value.
    """
    if not cases:
        raise ValueError(f"Suite {suite!r} has 0 cases. Write golden examples first.")

    results: list[EvalResult] = []
    for case in cases:
        try:
            result = scorer(case)
        except Exception as exc:
            logger.error("Eval case %r raised: %s", case.id, exc, exc_info=True)
            result = EvalResult(
                case_id=case.id,
                passed=False,
                score=0.0,
                details=f"Exception: {exc}",
            )
        results.append(result)

    n = len(results)
    value = sum(r.score for r in results) / n if n > 0 else 0.0
    pass_rate = sum(1 for r in results if r.passed) / n if n > 0 else 0.0

    logger.info(
        "Eval suite=%r module=%r logic_version=%r metric=%r value=%.3f pass_rate=%.3f n=%d",
        suite,
        module,
        logic_version,
        metric,
        value,
        pass_rate,
        n,
    )

    if threshold is not None and value < threshold:
        logger.warning(
            "Eval BELOW THRESHOLD: suite=%r metric=%r value=%.3f < threshold=%.3f (n=%d)",
            suite,
            metric,
            value,
            threshold,
            n,
        )

    suite_result = SuiteResult(
        suite=suite,
        module=module,
        logic_version=logic_version,
        metric=metric,
        value=value,
        n_items=n,
        results=results,
        judge_model=judge_model,
    )

    if save:
        _save_to_db(suite_result)

    return suite_result


def _save_to_db(suite_result: SuiteResult) -> None:
    """Write one EvalRun row. Never raises."""
    try:
        from core.models import EvalRun  # lazy

        EvalRun.objects.create(
            module=suite_result.module,
            suite=suite_result.suite,
            logic_version=suite_result.logic_version,
            metric=suite_result.metric,
            value=suite_result.value,
            n_items=suite_result.n_items,
            judge_model=suite_result.judge_model,
            judge_human_agreement=suite_result.judge_human_agreement,
        )
    except Exception as exc:
        logger.error("Failed to save EvalRun: %s", exc)


def assert_above_threshold(suite_result: SuiteResult, threshold: float) -> None:
    """
    Raise AssertionError if the suite result is below threshold.
    Call this from pytest tests to gate releases.
    """
    assert suite_result.value >= threshold, (
        f"Eval suite {suite_result.suite!r} metric={suite_result.metric!r} "
        f"value={suite_result.value:.3f} is below threshold={threshold:.3f} "
        f"(n={suite_result.n_items})"
    )
