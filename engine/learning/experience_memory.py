"""
Experience Memory
==================
過去の repair_execution 結果を蓄積し、次回の Repair Plan 生成時に
「このアクションは過去どれくらい成功/失敗しているか」を参照できるようにする。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


def _memory_path(project_path: Path) -> Path:
    p = project_path / "self_evolution" / "state" / "experience_memory.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record_execution(project_path: Path, execution_log_path: Path) -> None:
    data = json.loads(Path(execution_log_path).read_text(encoding="utf-8"))
    mem_path = _memory_path(project_path)

    with open(mem_path, "a", encoding="utf-8") as f:
        for entry in data.get("executions", []):
            record = {
                "component": entry.get("component"),
                "planned_action": entry.get("planned_action"),
                "status": entry.get("status"),
                "timestamp": time.time(),
                "source_execution_log": str(execution_log_path),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_history(project_path: Path) -> List[Dict[str, Any]]:
    mem_path = _memory_path(project_path)
    if not mem_path.exists():
        return []

    records = []
    with open(mem_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_action_stats(project_path: Path, component: str, planned_action: str) -> Dict[str, Any]:
    history = load_history(project_path)
    relevant = [
        r for r in history
        if r.get("component") == component and r.get("planned_action") == planned_action
    ]

    attempts = len(relevant)
    successes = sum(1 for r in relevant if r.get("status") == "SUCCESS")
    failures = attempts - successes

    # SKIPPED_NOT_IN_ALLOWLIST は「実行を試みていない」だけなので、
    # 成功/失敗の判定対象から除外する(誤った履歴警告を防ぐため)。
    attempted = [r for r in relevant if r.get("status") != "SKIPPED_NOT_IN_ALLOWLIST"]

    consecutive_failures = 0
    for r in reversed(attempted):
        if r.get("status") != "SUCCESS":
            consecutive_failures += 1
        else:
            break

    success_rate = (successes / attempts) if attempts > 0 else None

    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "consecutive_failures": consecutive_failures,
        "success_rate": success_rate,
    }


CONSECUTIVE_FAILURE_THRESHOLD = 3


def annotate_action_with_history(project_path: Path, component: str, planned_action: str) -> Dict[str, Any]:
    stats = get_action_stats(project_path, component, planned_action)
    escalate = stats["consecutive_failures"] >= CONSECUTIVE_FAILURE_THRESHOLD

    return {
        **stats,
        "escalate_to_human": escalate,
        "note": (
            f"直近{stats['consecutive_failures']}回連続失敗。"
            f"単純な{planned_action}では解決しない可能性が高い。人間による調査を推奨。"
            if escalate else "特に異常な履歴なし。"
        ),
    }
