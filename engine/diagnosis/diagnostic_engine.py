"""
Generation 2 - Diagnostic Engine
行うことは「観測」と「分類」のみ。結果は self_evolution/state/diagnosis_reports/ に保存する。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .models import CheckResult, DiagnosisResult, DiagnosisReport, Classification
from . import classifier as clf

# ----------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_ENDPOINT = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags"

# Proxyの待受ポート。実際の起動コードと同じ環境変数から読む。
PROXY_PORT = int(os.environ.get("SURGICAL_PROXY_PORT", "18082"))

HTTP_TIMEOUT_SECONDS = 3.0

REPAIRABLE_MAP = {
    "TOOL_NOT_ON_PATH": {"action": "INSTALL_OR_CONFIGURE_PATH", "confidence": 0.9, "repairable": True},
    "PROXY_UNREACHABLE": {"action": "START_SERVICE", "confidence": 0.6, "repairable": True},
    "PORT_IN_USE": {"action": "FREE_PORT_OR_RECONFIGURE", "confidence": 0.6, "repairable": True},
}


def check_python() -> CheckResult:
    return CheckResult(ok=True, component="python", detail=sys.version.split()[0],
                        raw={"version": sys.version, "executable": sys.executable})


def check_git() -> CheckResult:
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        return CheckResult(ok=r.returncode == 0, component="git", detail=r.stdout.strip(),
                            raw={"returncode": r.returncode})
    except Exception as e:
        return CheckResult(ok=False, component="git", detail=str(e))


def check_claude_cli() -> CheckResult:
    path = shutil.which("claude")
    if path:
        return CheckResult(ok=True, component="claude_cli", detail=f"found at {path}", raw={"path": path})
    return CheckResult(ok=False, component="claude_cli", detail="claude executable not found on PATH")


def check_ollama() -> CheckResult:
    try:
        req = urllib.request.Request(OLLAMA_ENDPOINT)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return CheckResult(ok=resp.status == 200, component="ollama", detail=f"HTTP {resp.status}",
                                raw={"endpoint": OLLAMA_ENDPOINT, "status": resp.status, "body_preview": body[:200]})
    except Exception as e:
        return CheckResult(ok=False, component="ollama", detail=str(e), raw={"endpoint": OLLAMA_ENDPOINT})


def check_port(port: int, host: str = "127.0.0.1") -> CheckResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(HTTP_TIMEOUT_SECONDS)
    result = sock.connect_ex((host, port))
    sock.close()
    ok = result == 0
    return CheckResult(ok=ok, component=f"port_{port}",
                        detail="open" if ok else f"closed (errno={result})",
                        raw={"host": host, "port": port})


def check_proxy_process() -> CheckResult:
    port_result = check_port(PROXY_PORT)
    return CheckResult(
        ok=port_result.ok,
        component="proxy_process",
        detail=f"proxy port {PROXY_PORT}: {port_result.detail}",
        raw=port_result.raw,
    )


def check_golden_proxy(project_path: Path) -> CheckResult:
    golden = project_path / "self_evolution" / "backups" / "golden_proxy.py"
    runtime = project_path / "surgical_proxy_v2" / "proxy.py"
    if not golden.exists() or not runtime.exists():
        return CheckResult(ok=False, component="golden_proxy", detail="golden or runtime file missing")
    gh = hashlib.sha256(golden.read_bytes()).hexdigest()
    rh = hashlib.sha256(runtime.read_bytes()).hexdigest()
    return CheckResult(ok=gh == rh, component="golden_proxy",
                        detail="matches golden" if gh == rh else "MISMATCH from golden",
                        raw={"proxy_sha256": rh, "golden_sha256": gh})


def check_json_state(project_path: Path, rel_path: str, component: str) -> CheckResult:
    p = project_path / rel_path
    if not p.exists():
        return CheckResult(ok=False, component=component, detail=f"{rel_path} not found")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return CheckResult(ok=True, component=component,
                            detail=f"generation={data.get('generation', '?')}" if "generation" in data else "loaded",
                            raw={"data": data})
    except Exception as e:
        return CheckResult(ok=False, component=component, detail=str(e))


def run_full_diagnosis(project_path: str | Path, generation: int = 2) -> DiagnosisReport:
    project = Path(project_path)
    checks = [
        check_python(),
        check_git(),
        check_claude_cli(),
        check_ollama(),
        check_proxy_process(),
        check_golden_proxy(project),
        check_json_state(project, "self_evolution/state/engine_state.json", "engine_state"),
        check_json_state(project, "self_evolution/state/tool_registry.json", "tool_registry"),
    ]

    results = []
    for c in checks:
        diag = clf.classify(c, REPAIRABLE_MAP)
        results.append(diag.to_dict())

    return DiagnosisReport(generation=generation, timestamp=time.time(), results=results)


def save_report(report: DiagnosisReport, project_path: str | Path) -> Path:
    project = Path(project_path)
    out_dir = project / "self_evolution" / "state" / "diagnosis_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(report.timestamp))
    out_path = out_dir / f"diagnosis_gen{report.generation}_{ts}.json"
    out_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
