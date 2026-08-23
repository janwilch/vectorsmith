"""Evaluate builtin policy packs and custom ``.rego`` via ``opa eval``."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

from vectorsmith_core.tds.models import TDSFile


def _issue(code: str, message: str, *, severity: Literal["error", "warning"] = "error") -> Any:
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
        issues.extend(_eval_rego(tds, policy_path))
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


def _eval_rego(tds: TDSFile, policy_path: Path) -> list[Any]:
    opa = shutil.which("opa")
    if opa is None:
        return [
            _issue(
                "POL000",
                "OPA is not installed; install the opa CLI to use --policy "
                f"({policy_path})",
            )
        ]
    payload = json.dumps({"tds": tds.model_dump(mode="json")})
    try:
        proc = subprocess.run(  # noqa: S603
            [opa, "eval", "-f", "json", "--stdin-input", "-d", str(policy_path), "data"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [_issue("POL000", f"opa eval failed: {exc}")]
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "opa eval failed").strip()
        return [_issue("POL000", f"opa eval failed: {detail}")]
    try:
        body = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return [_issue("POL000", "opa eval returned non-JSON output")]
    denies = _collect_denies(body)
    return [_issue("POL001", msg) for msg in denies]


def _collect_denies(body: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            deny = node.get("deny")
            if isinstance(deny, list):
                found.extend(str(item) for item in deny)
            elif isinstance(deny, str):
                found.append(deny)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(body)
    return found


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
