"""output.redact / max_field_length."""

from __future__ import annotations

from vectorsmith_core.compilepkg.compiler import ExecutionPlan
from vectorsmith_core.execute.output import apply_output_policy
from vectorsmith_core.tds.models import OutputRedactRule, RedactPattern


def _plan(**kwargs: object) -> ExecutionPlan:
    return ExecutionPlan(
        kind="search",
        connection="main",
        collection="invoices",
        query_param=None,
        query_required=False,
        mode="dense",
        alpha=0.5,
        embedding=None,
        fetch_k_param="limit",
        overfetch_factor=10,
        max_candidates=2000,
        projection=None,
        limit_default=10,
        limit_max=50,
        include_score=True,
        **kwargs,  # type: ignore[arg-type]
    )


def test_omit_removes_field() -> None:
    plan = _plan(output_redact=[OutputRedactRule(path="email", mode="omit")])
    rows = apply_output_policy([{"id": "1", "email": "a@b.com"}], plan)
    assert rows == [{"id": "1"}]


def test_max_field_length_truncates() -> None:
    plan = _plan(max_field_length=8, truncate_suffix="…")
    rows = apply_output_policy([{"body": "abcdefghijklmnop"}], plan)
    assert rows[0]["body"].endswith("…")
    assert len(rows[0]["body"]) <= 8


def test_pattern_redact() -> None:
    plan = _plan(
        output_redact=[
            OutputRedactRule(
                path="body",
                mode="pattern",
                patterns=[
                    RedactPattern(regex=r"\b[\w.-]+@[\w.-]+\.\w+\b", replacement="[email]")
                ],
            )
        ]
    )
    rows = apply_output_policy([{"body": "write to a@b.com please"}], plan)
    assert "[email]" in rows[0]["body"]
    assert "a@b.com" not in rows[0]["body"]
