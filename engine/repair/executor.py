"""
Generation 4
Repair Engine: Executor
EXECUTOR — ただし許可リストに載っている1アクションのみ実行可能。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ALLOWED_ACTIONS = {
    ("ollama", "START_SERVICE"),
    ("proxy_process", "START_SERVICE"),
}


def confirm(action_dict: dict) -> bool:
    print()
    print("-" * 72)
    print("EXECUTION CONFIRMATION REQUIRED")
    print("-" * 72)
    c = action_dict.get("component")
    cl = action_dict.get("classification")
    rc = action_dict.get("root_cause")
    pa = action_dict.get("planned_action")
    rk = action_dict.get("risk_class")
    print(f"component        : {c}")
    print(f"classification   : {cl}")
    print(f"root_cause       : {rc}")
    print(f"planned_action   : {pa}")
    print(f"risk_class       : {rk}")
    print("-" * 72)
    answer = input("この操作を実行しますか？ [yes/NO]: ").strip().lower()
    return answer == "yes"


def _start_ollama_service() -> dict:
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"started": True, "error": None}
    except FileNotFoundError as e:
        return {"started": False, "error": f"ollama executable not found: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"started": False, "error": str(e)}


def _verify_ollama() -> dict:
    from engine.diagnosis.diagnostic_engine import check_ollama

    result = check_ollama()
    return {"ok": result.ok, "detail": result.detail}


def _start_proxy_service() -> dict:
    project_root = Path(__file__).resolve().parents[2]
    proxy_path = project_root / "surgical_proxy_v2" / "proxy.py"

    if not proxy_path.exists():
        return {"started": False, "error": f"proxy script not found: {proxy_path}"}

    try:
        subprocess.Popen(
            [sys.executable, str(proxy_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"started": True, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"started": False, "error": str(e)}


def _verify_proxy_process() -> dict:
    import os
    import urllib.request

    port = int(os.environ.get("SURGICAL_PROXY_PORT", "18082"))
    endpoint = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(endpoint, timeout=5) as resp:
            ok = resp.status == 200
            return {"ok": ok, "detail": f"HTTP {resp.status} from {endpoint}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


EXECUTORS = {
    ("ollama", "START_SERVICE"): {
        "run": _start_ollama_service,
        "verify": _verify_ollama,
        "wait_seconds": 3,
    },
    ("proxy_process", "START_SERVICE"): {
        "run": _start_proxy_service,
        "verify": _verify_proxy_process,
        "wait_seconds": 3,
    },
}


def load_repair_plan(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8", errors="replace"))


def find_latest_repair_plan(project_path: Path) -> Path:
    plans_dir = project_path / "self_evolution" / "state" / "repair_plans"
    candidates = sorted(plans_dir.glob("repair_plan_gen*.json"))
    if not candidates:
        raise FileNotFoundError(f"No repair plan found under: {plans_dir}")
    return candidates[-1]


def run_executor(project_path: Path, plan_path: Optional[Path] = None) -> Path:
    if plan_path is None:
        plan_path = find_latest_repair_plan(project_path)

    plan = load_repair_plan(plan_path)
    execution_log = []

    print()
    print("=" * 72)
    print(" GENERATION 4 - EXECUTOR (ALLOWLIST ONLY)")
    print("=" * 72)
    print()
    print("Plan file:", plan_path)
    print("Allowed actions:", sorted(ALLOWED_ACTIONS))

    for action in plan["actions"]:
        key = (action["component"], action["planned_action"])

        if key not in ALLOWED_ACTIONS:
            execution_log.append(
                {
                    "component": action["component"],
                    "planned_action": action["planned_action"],
                    "status": "SKIPPED_NOT_IN_ALLOWLIST",
                }
            )
            continue

        approved = confirm(action)
        if not approved:
            execution_log.append(
                {
                    "component": action["component"],
                    "planned_action": action["planned_action"],
                    "status": "DECLINED_BY_HUMAN",
                }
            )
            print("→ 実行をスキップしました。")
            continue

        executor_def = EXECUTORS[key]
        print(f"→ 実行中: {key}")
        run_result = executor_def["run"]()

        time.sleep(executor_def.get("wait_seconds", 0))

        verify_result = executor_def["verify"]()

        status = "SUCCESS" if verify_result.get("ok") else "EXECUTED_BUT_VERIFICATION_FAILED"

        execution_log.append(
            {
                "component": action["component"],
                "planned_action": action["planned_action"],
                "status": status,
                "run_result": run_result,
                "verify_result": verify_result,
            }
        )
        print(f"→ 結果: {status}")

    out_dir = project_path / "self_evolution" / "state" / "repair_executions"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_path = out_dir / f"execution_gen4_{ts}.json"
    out_path.write_text(
        json.dumps(
            {
                "plan_file": str(plan_path),
                "executions": execution_log,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("Execution log saved:", out_path)
    return out_path
