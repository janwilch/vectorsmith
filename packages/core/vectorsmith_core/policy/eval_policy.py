"""Evaluate builtin policy packs; require OPA for custom ``.rego`` files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from vectorsmith_core.tds.models import TDSFile


def _issue(code: str, message: str, *, severity: str = "error") -> Any:
    from vectorsmith_core.api import Issue

    return Issue(severity=severity, code=code, message=message)


def eval_policies(
    tds: TDSFile,
    *,
    policy_path: Path | None = None,
    builtin: str | None = None,
) -> list[Any]:
    issues: list[Any] = []
    if policy_path is not None:
        if shutil.which("opa") is None:
            issues.append(
                _issue(
                    "POL000",
                    "OPA is not installed; install the opa CLI to use --policy "
                    f"({policy_path})",
                )
            )
            return issues
        issues.append(
            _issue("POL000", "custom --policy requires opa eval (not run in-process)")
        )
    for name in (p.strip() for p in (builtin or "").split(",") if p.strip()):
        if name == "enterprise":
            from vectorsmith_core.compilepkg.enterprise import enterprise_issues

            issues.extend(enterprise_issues(tds))
        elif name == "pci":
            issues.extend(_pci(tds))
        elif name == "soc2":
            issues.extend(_soc2(tds))
        else:
            issues.append(_issue("POL001", f"unknown policy pack '{name}'"))
    return issues


def _pci(tds: TDSFile) -> list[Any]:
    banned = {"pan", "cvv", "ssn"}
    issues: list[Any] = []
    for tool in tds.tools:
        fields = set(tool.output.fields or [])
        redacted = {r.path for r in tool.output.redact}
        for name in banned & fields - redacted:
            issues.append(
                _issue("POL001", f"PCI: tool '{tool.name}' returns unredacted '{name}'")
            )
    return issues


def _soc2(tds: TDSFile) -> list[Any]:
    issues: list[Any] = []
    if not tds.observability.audit.enabled:
        issues.append(_issue("POL001", "SOC2: observability.audit.enabled must be true"))
    return issues
