"""drafts list/reject and approve."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from vectorsmith_core.api import draft_tool, load_project, promote_draft


def _drafts_path() -> Path:
    return Path("tools.drafts.yaml")


def run_drafts(action: str, name: str | None) -> None:
    path = _drafts_path()
    data = {"drafts": []}
    if path.exists():
        loaded = yaml.safe_load(path.read_text()) or {}
        data["drafts"] = loaded.get("drafts") or []
    if action == "list":
        for d in data["drafts"]:
            tool = d.get("tool") or {}
            print(f"{d.get('status', 'pending'):10} {tool.get('name', '?')}", file=sys.stderr)
        return
    if action == "reject" and name:
        for d in data["drafts"]:
            if (d.get("tool") or {}).get("name") == name:
                d["status"] = "rejected"
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        print(f"rejected {name}", file=sys.stderr)
        return
    print("usage: drafts list | reject NAME", file=sys.stderr)
    raise SystemExit(2)


def run_approve(name: str, tools_file: Path) -> None:
    path = _drafts_path()
    if not path.exists():
        print("no tools.drafts.yaml", file=sys.stderr)
        raise SystemExit(2)
    data = yaml.safe_load(path.read_text()) or {}
    drafts = data.get("drafts") or []
    match = next((d for d in drafts if (d.get("tool") or {}).get("name") == name), None)
    if match is None:
        print(f"draft {name} not found", file=sys.stderr)
        raise SystemExit(2)
    project = load_project(tools_file)
    from vectorsmith_core.api import ToolDraft
    from vectorsmith_core.tds.models import ToolSpec

    spec = ToolSpec.model_validate(match["tool"])
    draft = ToolDraft(spec=spec, validator_issues=[], provenance=match)
    promoted = promote_draft(draft, project)
    raw = yaml.safe_load(tools_file.read_text())
    raw.setdefault("tools", []).append(promoted.model_dump(exclude_none=True))
    header = (
        f"# approved {datetime.now(UTC).isoformat()} "
        f"hash={match.get('hash', '')}\n"
    )
    tools_file.write_text(header + yaml.safe_dump(raw, sort_keys=False))
    match["status"] = "approved"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"Approved {name}. Toggle the connector in Claude to load it.", file=sys.stderr)


# draft_tool imported for define_tool serve path
_ = draft_tool
