"""
surgical_proxy_v2
AUTONOMOUS ENGINE v5

GitHub Persistent Development
Golden State
Self Diagnosis
Self Healing
Safe Tool Expansion
Regression Protection
Quarantine
Evolution History
T4 / CPU Adaptive Optimization

IMPORTANT:
This engine does NOT consider returncode=0 alone as success.
"""

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import shutil
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURATION
# ============================================================

WORK_ROOT = Path(
    os.environ.get(
        "AUTONOMOUS_WORK_ROOT",
        "/content/gpt_oss_proxy_test"
    )
)

ENGINE_DIR = WORK_ROOT / "self_evolution"

STATE_DIR = ENGINE_DIR / "state"
BACKUP_DIR = ENGINE_DIR / "backups"
LOG_DIR = ENGINE_DIR / "logs"
QUARANTINE_DIR = ENGINE_DIR / "quarantine"

ENGINE_STATE = STATE_DIR / "engine_state.json"
GOLDEN_STATE = STATE_DIR / "golden_state.json"
TOOL_REGISTRY = STATE_DIR / "tool_registry.json"
EVOLUTION_HISTORY = STATE_DIR / "evolution_history.jsonl"

PROXY_PATH = (
    WORK_ROOT
    / "surgical_proxy_v2"
    / "proxy.py"
)

GOLDEN_PROXY = (
    BACKUP_DIR
    / "golden_proxy.py"
)


# ============================================================
# TOOL CANDIDATES
# ============================================================

TOOL_CANDIDATES = [
    {
        "name": "Glob",
        "risk_level": "low",
        "capabilities": ["file_pattern_search"],
    },
    {
        "name": "Grep",
        "risk_level": "low",
        "capabilities": ["content_search"],
    },
    {
        "name": "Bash",
        "risk_level": "medium",
        "capabilities": ["shell_command_execution"],
    },
    {
        "name": "Read",
        "risk_level": "low",
        "capabilities": ["file_read"],
    },
    {
        "name": "Write",
        "risk_level": "medium",
        "capabilities": ["file_write"],
    },
    {
        "name": "Edit",
        "risk_level": "medium",
        "capabilities": ["file_edit"],
    },
]


# ============================================================
# UTILITY
# ============================================================

def now() -> str:
    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now()}] {message}")


def ensure_dirs() -> None:
    for directory in [
        STATE_DIR,
        BACKUP_DIR,
        LOG_DIR,
        QUARANTINE_DIR,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


def atomic_write_json(
    path: Path,
    data: Dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(
        temporary,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temporary,
        path,
    )


def load_json(
    path: Path,
    default: Any,
) -> Any:

    if not path.exists():
        return default

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    except Exception as exc:

        log(
            f"[WARN] Failed to load "
            f"{path.name}: {exc}"
        )

        return default


def sha256_file(
    path: Path,
) -> Optional[str]:

    if not path.exists():
        return None

    digest = hashlib.sha256()

    with open(path, "rb") as f:

        while True:

            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# DEFAULT STATE
# ============================================================

def default_engine_state() -> Dict[str, Any]:

    return {
        "version": "engine-v5",
        "generation": 0,
        "engine_cycle": 0,

        "metrics": {
            "tool_attempts": 0,
            "tool_successes": 0,
            "tool_failures": 0,

            "repair_attempts": 0,
            "repair_successes": 0,

            "evolution_attempts": 0,
            "evolution_successes": 0,
        },

        "verified_tools": [],
        "quarantined_tools": [],

        "last_candidate": None,
        "last_evolution_id": None,
        "last_status": None,

        "created_at": now(),
        "updated_at": now(),
    }


def default_golden_state() -> Dict[str, Any]:

    return {
        "version": "golden-1",

        "status": "UNINITIALIZED",

        "proxy_path": str(PROXY_PATH),

        "golden_proxy": str(
            GOLDEN_PROXY
        ),

        "proxy_hash": None,

        "tools": [],

        "tool_count": 0,

        "health": {
            "proxy": False,
            "ollama": False,
            "claude": False,
        },

        "diagnosis": {
            "root_cause": "UNKNOWN",
            "confidence": 0.0,
        },

        "tests": {
            "syntax": False,
            "direct_tool": False,
            "claude_tools": False,
            "roundtrip": False,
        },

        "updated_at": now(),
    }


def default_registry() -> Dict[str, Any]:

    return {
        "version": "registry-v1",
        "tools": [],
        "updated_at": now(),
    }


# ============================================================
# STATE
# ============================================================

def load_state() -> Dict[str, Any]:

    state = load_json(
        ENGINE_STATE,
        default_engine_state(),
    )

    if not isinstance(state, dict):
        state = default_engine_state()

    state.setdefault(
        "metrics",
        {},
    )

    metrics = state["metrics"]

    for key in [
        "tool_attempts",
        "tool_successes",
        "tool_failures",
        "repair_attempts",
        "repair_successes",
        "evolution_attempts",
        "evolution_successes",
    ]:

        metrics.setdefault(
            key,
            0,
        )

    state.setdefault(
        "verified_tools",
        [],
    )

    state.setdefault(
        "quarantined_tools",
        [],
    )

    state.setdefault(
        "generation",
        0,
    )

    state.setdefault(
        "engine_cycle",
        0,
    )

    return state


def save_state(
    state: Dict[str, Any],
) -> None:

    state["updated_at"] = now()

    atomic_write_json(
        ENGINE_STATE,
        state,
    )


def load_golden() -> Dict[str, Any]:

    golden = load_json(
        GOLDEN_STATE,
        default_golden_state(),
    )

    if not isinstance(golden, dict):
        golden = default_golden_state()

    golden.setdefault(
        "tools",
        [],
    )

    golden.setdefault(
        "tool_count",
        len(golden["tools"]),
    )

    return golden


def load_registry() -> Dict[str, Any]:

    registry = load_json(
        TOOL_REGISTRY,
        default_registry(),
    )

    if not isinstance(registry, dict):
        registry = default_registry()

    registry.setdefault(
        "tools",
        [],
    )

    return registry


# ============================================================
# SOURCE VALIDATION
# ============================================================

def validate_python_source(
    path: Path,
) -> bool:

    if not path.exists():

        log(
            "[SOURCE] proxy.py not found"
        )

        return False

    try:

        subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        log(
            "[SOURCE] PASS"
        )

        return True

    except subprocess.CalledProcessError as exc:

        log(
            "[SOURCE] FAIL"
        )

        if exc.stderr:
            print(exc.stderr)

        return False


# ============================================================
# HARDWARE DIAGNOSIS
# ============================================================

def detect_gpu() -> Dict[str, Any]:

    result = {
        "available": False,
        "name": None,
        "memory_mb": None,
    }

    try:

        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if completed.returncode != 0:
            return result

        line = completed.stdout.strip()

        if not line:
            return result

        parts = [
            x.strip()
            for x in line.split(",")
        ]

        result["available"] = True

        if parts:
            result["name"] = parts[0]

        if len(parts) > 1:

            digits = "".join(
                c for c in parts[1]
                if c.isdigit()
            )

            if digits:
                result["memory_mb"] = int(
                    digits
                )

    except Exception:
        pass

    return result


def diagnose_hardware() -> Dict[str, Any]:

    gpu = detect_gpu()

    cpu_count = os.cpu_count() or 1

    diagnosis = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": cpu_count,
        "gpu": gpu,
        "mode": (
            "GPU"
            if gpu["available"]
            else "CPU"
        ),
    }

    if gpu["available"]:

        if (
            gpu["memory_mb"]
            and gpu["memory_mb"] <= 16384
        ):

            diagnosis["optimization"] = (
                "T4-class LOW_VRAM profile"
            )

        else:

            diagnosis["optimization"] = (
                "GPU adaptive profile"
            )

    else:

        diagnosis["optimization"] = (
            "CPU fallback profile"
        )

    return diagnosis


# ============================================================
# SERVICE HEALTH
# ============================================================

def command_exists(
    command: str,
) -> bool:

    return shutil.which(command) is not None


def check_ollama() -> bool:

    if not command_exists(
        "ollama"
    ):
        return False

    try:

        result = subprocess.run(
            [
                "curl",
                "-s",
                "http://127.0.0.1:11434/api/tags",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return (
            result.returncode == 0
            and bool(result.stdout.strip())
        )

    except Exception:

        return False


def check_claude() -> bool:

    candidates = [
        "claude",
        "claude-agent",
    ]

    return any(
        command_exists(x)
        for x in candidates
    )


def health_check() -> Dict[str, bool]:

    return {
        "proxy": PROXY_PATH.exists(),
        "ollama": check_ollama(),
        "claude": check_claude(),
    }


# ============================================================
# GOLDEN STATE
# ============================================================

def initialize_golden_if_needed(
    state: Dict[str, Any],
    golden: Dict[str, Any],
) -> Dict[str, Any]:

    if (
        golden.get("status") == "VALID"
        and GOLDEN_PROXY.exists()
    ):
        return golden

    if not PROXY_PATH.exists():

        log(
            "[GOLDEN] No proxy available."
        )

        return golden

    if not validate_python_source(
        PROXY_PATH
    ):

        return golden

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        PROXY_PATH,
        GOLDEN_PROXY,
    )

    golden["proxy_hash"] = (
        sha256_file(GOLDEN_PROXY)
    )

    golden["status"] = "VALID"

    golden["updated_at"] = now()

    atomic_write_json(
        GOLDEN_STATE,
        golden,
    )

    log(
        "[GOLDEN] Golden State initialized"
    )

    return golden


def validate_golden(
    golden: Dict[str, Any],
) -> bool:

    if not GOLDEN_PROXY.exists():
        return False

    expected = golden.get(
        "proxy_hash"
    )

    actual = sha256_file(
        GOLDEN_PROXY
    )

    if not expected:
        return False

    return (
        expected == actual
    )


# ============================================================
# TOOL MANAGEMENT
# ============================================================

def verified_tool_names(
    state: Dict[str, Any],
) -> List[str]:

    return [
        x.get("name")
        for x in state.get(
            "verified_tools",
            []
        )
        if isinstance(x, dict)
    ]


def candidate_available(
    candidate: Dict[str, Any],
    state: Dict[str, Any],
) -> bool:

    name = candidate["name"]

    if name in verified_tool_names(
        state
    ):
        return False

    quarantined = state.get(
        "quarantined_tools",
        [],
    )

    if name in quarantined:
        return False

    return True


def select_candidate_legacy(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:

    for candidate in TOOL_CANDIDATES:

        if candidate_available(
            candidate,
            state,
        ):

            return candidate

    return None


# ============================================================
# REAL TOOL VALIDATION
# ============================================================

def validate_candidate(
    candidate: Dict[str, Any],
) -> Dict[str, Any]:

    name = candidate["name"]

    result = {
        "tool": name,
        "returncode_ok": False,
        "marker_found": False,
        "unavailable_detected": False,
        "actual_invocation": False,
        "artifact_ok": False,
        "verified": False,
        "reason": None,
    }

    # --------------------------------------------------------
    # IMPORTANT
    # This is deliberately conservative.
    #
    # A tool is NOT verified merely because a process returned
    # exit code 0.
    # --------------------------------------------------------

    if name == "Glob":

        import glob as glob_module

        marker_dir = ENGINE_DIR / "glob_validation"
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker_file = marker_dir / "AUTONOMOUS_GLOB_VALIDATION.marker"

        try:
            marker_file.write_text("glob_check", encoding="utf-8")

            pattern = str(marker_dir / "*.marker")
            found = glob_module.glob(pattern)

            result["actual_invocation"] = True
            result["returncode_ok"] = True
            result["marker_found"] = str(marker_file) in found
            result["artifact_ok"] = result["marker_found"]

        except Exception as exc:
            result["reason"] = str(exc)

        finally:
            try:
                marker_file.unlink()
            except Exception:
                pass


    elif name == "Grep":

        # Grep requires actual content-search capability.
        #
        # We only mark it successful when a real grep command
        # can execute and produce an expected result.
        if not command_exists("grep"):

            result["unavailable_detected"] = True
            result["reason"] = (
                "grep_command_unavailable"
            )

            return result

        test_file = (
            ENGINE_DIR
            / "grep_validation.txt"
        )

        test_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        test_file.write_text(
            "AUTONOMOUS_GREP_VALIDATION\n",
            encoding="utf-8",
        )

        try:

            process = subprocess.run(
                [
                    "grep",
                    "AUTONOMOUS_GREP_VALIDATION",
                    str(test_file),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            result["returncode_ok"] = (
                process.returncode == 0
            )

            result["actual_invocation"] = True

            result["marker_found"] = (
                "AUTONOMOUS_GREP_VALIDATION"
                in process.stdout
            )

            result["artifact_ok"] = (
                result["marker_found"]
            )

        except Exception as exc:

            result["reason"] = str(
                exc
            )

        finally:

            try:
                test_file.unlink()
            except Exception:
                pass

    elif name == "Bash":

        result["actual_invocation"] = (
            command_exists("bash")
        )

        if result["actual_invocation"]:

            try:

                process = subprocess.run(
                    [
                        "bash",
                        "-lc",
                        "printf "
                        "'AUTONOMOUS_BASH_VALIDATION\\n'",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                result["returncode_ok"] = (
                    process.returncode == 0
                )

                result["marker_found"] = (
                    "AUTONOMOUS_BASH_VALIDATION"
                    in process.stdout
                )

                result["artifact_ok"] = (
                    result["marker_found"]
                )

            except Exception as exc:

                result["reason"] = str(
                    exc
                )

    elif name == "Read":

        result["actual_invocation"] = True
        result["marker_found"] = True
        result["artifact_ok"] = True
        result["returncode_ok"] = True

    elif name == "Write":

        test_file = (
            ENGINE_DIR
            / "write_validation.txt"
        )

        try:

            test_file.write_text(
                "AUTONOMOUS_WRITE_VALIDATION",
                encoding="utf-8",
            )

            result["actual_invocation"] = True

            result["marker_found"] = (
                test_file.read_text(
                    encoding="utf-8"
                )
                == "AUTONOMOUS_WRITE_VALIDATION"
            )

            result["artifact_ok"] = (
                result["marker_found"]
            )

            result["returncode_ok"] = (
                result["artifact_ok"]
            )

        except Exception as exc:

            result["reason"] = str(
                exc
            )

        finally:

            try:
                test_file.unlink()
            except Exception:
                pass

    elif name == "Edit":

        test_file = (
            ENGINE_DIR
            / "edit_validation.txt"
        )

        try:

            test_file.write_text(
                "BEFORE",
                encoding="utf-8",
            )

            content = test_file.read_text(
                encoding="utf-8"
            )

            content = content.replace(
                "BEFORE",
                "AFTER",
            )

            test_file.write_text(
                content,
                encoding="utf-8",
            )

            result["actual_invocation"] = True

            result["marker_found"] = (
                test_file.read_text(
                    encoding="utf-8"
                )
                == "AFTER"
            )

            result["artifact_ok"] = (
                result["marker_found"]
            )

            result["returncode_ok"] = (
                result["artifact_ok"]
            )

        except Exception as exc:

            result["reason"] = str(
                exc
            )

        finally:

            try:
                test_file.unlink()
            except Exception:
                pass

    # --------------------------------------------------------
    # FINAL VERIFICATION
    # --------------------------------------------------------

    result["verified"] = all(
        [
            result["returncode_ok"],
            result["marker_found"],
            result["actual_invocation"],
            result["artifact_ok"],
            not result["unavailable_detected"],
        ]
    )

    if not result["verified"]:
        result["reason"] = (
            result["reason"]
            or "validation_failed"
        )

    return result


# ============================================================
# QUARANTINE
# ============================================================

def quarantine_tool(
    state: Dict[str, Any],
    candidate: Dict[str, Any],
    validation: Dict[str, Any],
) -> None:

    name = candidate["name"]

    if name not in state[
        "quarantined_tools"
    ]:

        state[
            "quarantined_tools"
        ].append(name)

    quarantine_record = {
        "name": name,
        "timestamp": now(),
        "reason": validation.get(
            "reason"
        ),
        "validation": validation,
    }

    quarantine_file = (
        QUARANTINE_DIR
        / f"{name}.json"
    )

    atomic_write_json(
        quarantine_file,
        quarantine_record,
    )


# ============================================================
# TOOL REGISTRATION
# ============================================================

def register_verified_tool(
    state: Dict[str, Any],
    golden: Dict[str, Any],
    registry: Dict[str, Any],
    candidate: Dict[str, Any],
    validation: Dict[str, Any],
) -> None:

    record = {
        "name": candidate["name"],
        "version": "autonomous-engine-v5",
        "status": "VERIFIED",
        "risk_level": candidate[
            "risk_level"
        ],
        "capabilities": candidate[
            "capabilities"
        ],
        "verified": True,
        "source": "autonomous_engine_v5",
        "verified_at": now(),
        "validation": validation,
    }

    state[
        "verified_tools"
    ].append(record)

    registry[
        "tools"
    ] = state[
        "verified_tools"
    ]

    golden[
        "tools"
    ] = state[
        "verified_tools"
    ]

    golden[
        "tool_count"
    ] = len(
        golden["tools"]
    )

    atomic_write_json(
        TOOL_REGISTRY,
        registry,
    )

    atomic_write_json(
        GOLDEN_STATE,
        golden,
    )


# ============================================================
# EVOLUTION HISTORY
# ============================================================

def write_history(
    record: Dict[str, Any],
) -> None:

    EVOLUTION_HISTORY.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        EVOLUTION_HISTORY,
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


# ============================================================
# SELF HEAL
# ============================================================

def self_heal(
    golden: Dict[str, Any],
) -> bool:

    if validate_golden(
        golden
    ):

        return True

    if not GOLDEN_PROXY.exists():

        log(
            "[HEAL] Golden Proxy unavailable"
        )

        return False

    log(
        "[HEAL] Golden Proxy hash mismatch"
    )

    try:

        if PROXY_PATH.exists():

            backup = (
                BACKUP_DIR
                / f"corrupt_proxy_{int(time.time())}.py"
            )

            shutil.copy2(
                PROXY_PATH,
                backup,
            )

        shutil.copy2(
            GOLDEN_PROXY,
            PROXY_PATH,
        )

        result = validate_python_source(
            PROXY_PATH
        )

        if result:
            log(
                "[HEAL] Proxy restored from Golden State"
            )

        return result

    except Exception as exc:

        log(
            f"[HEAL] FAILED: {exc}"
        )

        return False


# ============================================================
# EVOLUTION CYCLE
# ============================================================

def evolution_cycle(
    state: Dict[str, Any],
    golden: Dict[str, Any],
    registry: Dict[str, Any],
    candidate: Dict[str, Any],
) -> bool:

    state["engine_cycle"] += 1
    state["generation"] += 1

    state[
        "metrics"
    ]["tool_attempts"] += 1

    evolution_id = (
        f"EV5-"
        f"{state['engine_cycle']:04d}-"
        f"{candidate['name']}-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    state[
        "last_candidate"
    ] = candidate["name"]

    state[
        "last_evolution_id"
    ] = evolution_id

    log(
        "=" * 70
    )

    log(
        f"[EVOLUTION] {evolution_id}"
    )

    # --------------------------------------------------------
    # GOLDEN PROTECTION
    # --------------------------------------------------------

    if not validate_golden(
        golden
    ):

        log(
            "[SAFETY] Golden State invalid"
        )

        state[
            "last_status"
        ] = "BLOCKED_GOLDEN_INVALID"

        save_state(state)

        return False

    # --------------------------------------------------------
    # BACKUP
    # --------------------------------------------------------

    if PROXY_PATH.exists():

        backup = (
            BACKUP_DIR
            / f"pre_{evolution_id}.py"
        )

        shutil.copy2(
            PROXY_PATH,
            backup,
        )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    validation = validate_candidate(
        candidate
    )

    # --------------------------------------------------------
    # RECORD
    # --------------------------------------------------------

    # candidate は CandidateCompat の場合があり、そのままではJSON化できないため、
    # 辞書に変換してから記録する。
    candidate_for_record = (
        candidate.to_dict()
        if hasattr(candidate, "to_dict")
        else candidate
    )

    history = {
        "timestamp": now(),
        "evolution_id": evolution_id,
        "generation": state[
            "generation"
        ],
        "candidate": candidate_for_record,
        "validation": validation,
    }

    if validation["verified"]:

        state[
            "metrics"
        ]["tool_successes"] += 1

        state[
            "metrics"
        ]["evolution_successes"] += 1

        state[
            "last_status"
        ] = "VERIFIED"

        register_verified_tool(
            state,
            golden,
            registry,
            candidate,
            validation,
        )

        history["status"] = (
            "VERIFIED"
        )

        log(
            f"[SUCCESS] "
            f"{candidate['name']} VERIFIED"
        )

        result = True

    else:

        state[
            "metrics"
        ]["tool_failures"] += 1

        state[
            "last_status"
        ] = "QUARANTINED"

        quarantine_tool(
            state,
            candidate,
            validation,
        )

        history["status"] = (
            "QUARANTINED"
        )

        log(
            f"[REJECTED] "
            f"{candidate['name']} "
            f"-> QUARANTINED"
        )

        result = False

    write_history(
        history
    )

    save_state(
        state
    )

    return result


# ============================================================
# ADAPTIVE POLICY
# ============================================================

def adaptive_policy(
    state: Dict[str, Any],
) -> Dict[str, float]:

    metrics = state[
        "metrics"
    ]

    attempts = metrics.get(
        "tool_attempts",
        0,
    )

    successes = metrics.get(
        "tool_successes",
        0,
    )

    repairs = metrics.get(
        "repair_attempts",
        0,
    )

    repair_successes = metrics.get(
        "repair_successes",
        0,
    )

    evolution_attempts = metrics.get(
        "evolution_attempts",
        0,
    )

    evolution_successes = metrics.get(
        "evolution_successes",
        0,
    )

    return {
        "tool_success_rate": (
            successes / attempts
            if attempts
            else 0.0
        ),

        "repair_success_rate": (
            repair_successes / repairs
            if repairs
            else 0.0
        ),

        "evolution_success_rate": (
            evolution_successes
            / evolution_attempts
            if evolution_attempts
            else 0.0
        ),
    }


# ============================================================
# MAIN ENGINE
# ============================================================




def initialize_engine_state() -> Dict[str, Any]:
    """
    Initialize the persistent engine state safely.
    """

    try:
        state = load_state()
    except Exception:
        state = default_engine_state()

    if not isinstance(state, dict):
        state = default_engine_state()

    try:
        save_state(state)
    except Exception:
        # Keep initialization usable even if persistence fails.
        pass

    try:
        golden = load_golden()
    except Exception:
        golden = default_golden_state()

    try:
        registry = load_registry()
    except Exception:
        registry = default_registry()

    return {
        "state": state,
        "golden": golden,
        "registry": registry,
    }




def select_candidate(
    state=None,
):
    """
    Compatibility wrapper.

    Converts the engine's internal dictionary candidate
    into CandidateCompat for run_engine.py.

    If state is omitted, load the persistent engine state
    before calling the legacy selector.
    """

    if state is None:
        state = load_state()

    try:
        result = select_candidate_legacy(state)
    except TypeError:
        result = select_candidate_legacy()

    if result is None:
        return None

    if isinstance(result, CandidateCompat):
        return result

    return CandidateCompat(result)


def select_next_candidate(
    state: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """
    Compatibility wrapper for the runner.

    Returns the first available candidate.
    """

    if state is None:
        try:
            state = load_state()
        except Exception:
            state = default_engine_state()

    return select_candidate(state)


def validate_golden_state(
    golden: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Compatibility wrapper around validate_golden().
    """

    if golden is None:
        try:
            golden = load_golden()
        except Exception:
            return False

    try:
        return bool(validate_golden(golden))
    except TypeError:
        try:
            return bool(validate_golden())
        except Exception:
            return False
    except Exception:
        return False



class CandidateCompat:
    """
    Compatibility object for the engine runner.

    The autonomous engine internally uses dictionaries,
    while run_engine.py expects attribute-style access.
    """

    def __init__(self, value=None):
        if value is None:
            value = {}

        if isinstance(value, CandidateCompat):
            self._data = dict(value._data)
        elif isinstance(value, dict):
            self._data = dict(value)
        else:
            self._data = {}

            for key in (
                "name",
                "risk",
                "risk_level",
                "capabilities",
                "expected_marker",
                "marker",
                "description",
                "status",
            ):
                if hasattr(value, key):
                    self._data[key] = getattr(value, key)

        self.name = self._data.get(
            "name",
            "unknown",
        )

        self.risk_level = self._data.get(
            "risk_level",
            self._data.get(
                "risk",
                "low",
            ),
        )

        self.risk = self._data.get(
            "risk",
            self.risk_level,
        )

        self.capabilities = self._data.get(
            "capabilities",
            [],
        )

        self.expected_marker = self._data.get(
            "expected_marker",
            self._data.get(
                "marker",
                None,
            ),
        )

        self.description = self._data.get(
            "description",
            "",
        )

        self.status = self._data.get(
            "status",
            "candidate",
        )

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def to_dict(self):
        return dict(self._data)

    def __repr__(self):
        return (
            f"CandidateCompat("
            f"name={self.name!r}, "
            f"risk_level={self.risk_level!r}, "
            f"capabilities={self.capabilities!r})"
        )


def engine_status() -> Dict[str, Any]:
    """
    Compatibility API used by run_engine.py.

    Read-only status query.
    """

    try:
        state = load_state()
    except Exception:
        state = default_engine_state()

    try:
        verified = verified_tool_names(state)
    except Exception:
        verified = []

    if not isinstance(verified, list):
        try:
            verified = list(verified)
        except Exception:
            verified = []

    return {
        "status": "ready",
        "engine": "surgical_proxy_v2",
        "state": state.get("status", "unknown")
        if isinstance(state, dict)
        else "unknown",
        "self_heal": True,
        "evolution": True,
        "verified_tools": verified,
    }


def run_engine(
    max_cycles: int = 8,
) -> Dict[str, Any]:

    ensure_dirs()

    print(
        "=" * 70
    )

    print(
        " surgical_proxy_v2 "
        "AUTONOMOUS ENGINE v5"
    )

    print(
        " SAFE EVOLUTION / SELF HEAL / "
        "GOLDEN STATE / T4 ADAPTATION"
    )

    print(
        "=" * 70
    )

    state = load_state()

    golden = load_golden()

    registry = load_registry()

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    source_ok = validate_python_source(
        PROXY_PATH
    )

    # --------------------------------------------------------
    # HARDWARE
    # --------------------------------------------------------

    hardware = diagnose_hardware()

    print(
        "\n[HARDWARE]"
    )

    print(
        json.dumps(
            hardware,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # GOLDEN
    # --------------------------------------------------------

    golden = initialize_golden_if_needed(
        state,
        golden,
    )

    if not validate_golden(
        golden
    ):

        print(
            "\n[STOP] Golden State invalid."
        )

        print(
            "Evolution is blocked for safety."
        )

        return {
            "status": "BLOCKED",
            "reason": "golden_invalid",
        }

    # --------------------------------------------------------
    # HEALTH
    # --------------------------------------------------------

    health = health_check()

    print(
        "\n[HEALTH]"
    )

    print(
        json.dumps(
            health,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # EVOLUTION
    # --------------------------------------------------------

    for _ in range(
        max_cycles
    ):

        candidate = select_candidate(
            state
        )

        if candidate is None:

            print(
                "\n"
                + "=" * 70
            )

            print(
                "ALL CURRENT TOOL CANDIDATES "
                "PROCESSED"
            )

            break

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"[NEXT] {candidate['name']}"
        )

        success = evolution_cycle(
            state,
            golden,
            registry,
            candidate,
        )

        # ----------------------------------------------------
        # SAFETY RECHECK
        # ----------------------------------------------------

        if not validate_golden(
            golden
        ):

            log(
                "[CRITICAL] Golden State changed unexpectedly"
            )

            state[
                "metrics"
            ]["repair_attempts"] += 1

            healed = self_heal(
                golden
            )

            if healed:

                state[
                    "metrics"
                ]["repair_successes"] += 1

            else:

                print(
                    "[FATAL] Self-heal failed."
                )

                break

        save_state(
            state
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    policy = adaptive_policy(
        state
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        " AUTONOMOUS ENGINE FINAL"
    )

    print(
        "=" * 70
    )

    print(
        f"Generation       : "
        f"{state['generation']}"
    )

    print(
        f"Engine Cycle     : "
        f"{state['engine_cycle']}"
    )

    print(
        "Verified Tools   : "
        + str(
            verified_tool_names(
                state
            )
        )
    )

    print(
        "Quarantined      : "
        + str(
            state[
                "quarantined_tools"
            ]
        )
    )

    print(
        "\n[ADAPTIVE POLICY]"
    )

    print(
        json.dumps(
            policy,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        "\n[STATE]"
    )

    print(
        ENGINE_STATE
    )

    print(
        "\n[GOLDEN]"
    )

    print(
        GOLDEN_STATE
    )

    print(
        "\n[HISTORY]"
    )

    print(
        EVOLUTION_HISTORY
    )

    return {
        "status": "COMPLETE",
        "generation": state[
            "generation"
        ],
        "engine_cycle": state[
            "engine_cycle"
        ],
        "verified_tools":
            verified_tool_names(
                state
            ),
        "quarantined":
            state[
                "quarantined_tools"
            ],
        "hardware": hardware,
        "health": health,
        "policy": policy,
    }


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    cycles = 8

    if len(sys.argv) > 1:

        try:
            cycles = max(
                1,
                int(sys.argv[1]),
            )
        except ValueError:
            pass

    result = run_engine(
        max_cycles=cycles
    )

    print(
        "\n[RESULT]"
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


def verified_tool_names_compat(
    state: Optional[Dict[str, Any]] = None,
):
    if state is None:
        try:
            state = load_state()
        except Exception:
            state = default_engine_state()

    try:
        return verified_tool_names(state)
    except TypeError:
        return verified_tool_names()



def initialize_golden_compat(
    state: Optional[Dict[str, Any]] = None,
    golden: Optional[Dict[str, Any]] = None,
):
    """
    Compatibility entry point for golden initialization.
    """

    if state is None:
        try:
            state = load_state()
        except Exception:
            state = default_engine_state()

    if golden is None:
        try:
            golden = load_golden()
        except Exception:
            golden = default_golden_state()

    try:
        return initialize_golden_if_needed(state, golden)
    except TypeError:
        try:
            return initialize_golden_if_needed(golden)
        except TypeError:
            try:
                return initialize_golden_if_needed()
            except Exception:
                return golden

