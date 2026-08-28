from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

from .models import RepairAction
from .policy import resolve_policy


def find_latest_diagnosis_report(project_path: Path) -> Path:
    reports_dir = project_path / "self_evolution" / "state" / "diagnosis_reports"
    if not reports_dir.exists():
        raise FileNotFoundError(f"diagnosis_reports directory not found: {reports_dir}")
    candidates = sorted(reports_dir.glob("diagnosis_gen*.json"))
    if not candidates:
        raise FileNotFoundError(f"No diagnosis report found under: {reports_dir}")
    return candidates[-1]


def load_diagnosis_report(report_path: Path) -> dict:
    data = json.loads(report_path.read_text(encoding="utf-8", errors="replace"))
    if "results" not in data:
        raise ValueError(f"Invalid diagnosis report (missing 'results'): {report_path}")
    return data


def build_repair_plan(report: dict, project_path: Path | None = None) -> List[RepairAction]:
    actions = []
    for result in report["results"]:
        if result.get("classification") == "HEALTHY":
            action = RepairAction(
                component=result["component"],
                classification=result["classification"],
                root_cause=result.get("root_cause", "N/A"),
                planned_action="NONE",
                confidence=result.get("confidence", 1.0),
                risk_class="NONE",
                requires_human_approval=False,
                execution_allowed=False,
                detail=result.get("detail", ""),
            )
        else:
            policy = resolve_policy(result.get("root_cause", "UNKNOWN"))
            planned_action = result.get("recommended_action", "NONE")

            detail_text = result.get("detail", "")
            if project_path is not None:
                from engine.learning.experience_memory import annotate_action_with_history
                history = annotate_action_with_history(project_path, result["component"], planned_action)
                if history["escalate_to_human"]:
                    detail_text += f" [履歴警告] {history['note']}"

            action = RepairAction(
                component=result["component"],
                classification=result["classification"],
                root_cause=result.get("root_cause", "UNKNOWN"),
                planned_action=planned_action,
                confidence=result.get("confidence", 0.0),
                risk_class=policy.risk_class,
                requires_human_approval=policy.requires_human_approval,
                execution_allowed=False,  # Gen3は計画のみ。実行は一切しない。
                detail=detail_text,
            )
        actions.append(action)
    return actions


def save_repair_plan(actions: List[RepairAction], project_path: Path, generation: int = 3) -> Path:
    out_dir = project_path / "self_evolution" / "state" / "repair_plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_path = out_dir / f"repair_plan_gen{generation}_{ts}.json"
    out_path.write_text(
        json.dumps({"actions": [a.to_dict() for a in actions]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path
