# ============================================================
# Kgo Autonomous Engine
# state_manager.py
#
# Autonomous Engine v4.2+
# SAFE STATE MANAGEMENT
# GOLDEN STATE
# TOOL REGISTRY
# EVOLUTION HISTORY
# QUARANTINE
# ATOMIC PERSISTENCE
# SHA256 VALIDATION
# ============================================================

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# VERSION
# ============================================================

STATE_MANAGER_VERSION = "1.0.0"
STATE_SCHEMA_VERSION = "engine-state-1"


# ============================================================
# DEFAULT PATHS
# ============================================================

PROJECT_ROOT = Path(
    os.environ.get(
        "KGO_ROOT",
        "/content/gpt_oss_proxy_test"
    )
)

SELF_EVOLUTION_DIR = PROJECT_ROOT / "self_evolution"
STATE_DIR = SELF_EVOLUTION_DIR / "state"
BACKUP_DIR = SELF_EVOLUTION_DIR / "backups"

ENGINE_STATE_PATH = STATE_DIR / "engine_state.json"
TOOL_REGISTRY_PATH = STATE_DIR / "tool_registry.json"
GOLDEN_STATE_PATH = STATE_DIR / "golden_state.json"
EVOLUTION_HISTORY_PATH = STATE_DIR / "evolution_history.jsonl"
RECOVERY_STATE_PATH = STATE_DIR / "recovered_state.json"

QUARANTINE_PATH = STATE_DIR / "quarantine.json"


# ============================================================
# BASIC UTILITIES
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def ensure_directories() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def atomic_write_json(
    path: Path,
    data: Dict[str, Any]
) -> None:

    ensure_directories()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent)
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

            f.write("\n")

            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_name, path)

    except Exception:

        try:
            os.unlink(tmp_name)
        except OSError:
            pass

        raise


def load_json(
    path: Path,
    default: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    if default is None:
        default = {}

    path = Path(path)

    if not path.exists():
        return copy.deepcopy(default)

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return copy.deepcopy(default)

        return data

    except (
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError
    ):

        return copy.deepcopy(default)


# ============================================================
# SHA256
# ============================================================

def sha256_file(path: Path) -> Optional[str]:

    path = Path(path)

    if not path.exists():
        return None

    sha = hashlib.sha256()

    try:

        with open(path, "rb") as f:

            while True:

                chunk = f.read(1024 * 1024)

                if not chunk:
                    break

                sha.update(chunk)

        return sha.hexdigest()

    except OSError:

        return None


# ============================================================
# DEFAULT ENGINE STATE
# ============================================================

def default_engine_state() -> Dict[str, Any]:

    return {

        "schema_version": STATE_SCHEMA_VERSION,

        "manager_version": STATE_MANAGER_VERSION,

        "created_at": utc_now(),

        "updated_at": utc_now(),

        "generation": 0,

        "engine_cycle": 0,

        "status": "INITIALIZED",

        "verified_tools": [],

        "tool_count": 0,

        "quarantined": [],

        "evolution_history_count": 0,

        "last_candidate": None,

        "last_evolution_id": None,

        "last_status": None,

        "last_error": None,

        "golden_state": {

            "status": "UNINITIALIZED",

            "valid": False,

            "proxy_path": None,

            "golden_proxy": None,

            "proxy_hash": None,

            "version": "golden-1",

        },

        "metrics": {

            "tool_attempts": 0,

            "tool_successes": 0,

            "tool_failures": 0,

            "repair_attempts": 0,

            "repair_successes": 0,

            "repair_failures": 0,

            "evolution_attempts": 0,

            "evolution_successes": 0,

            "evolution_failures": 0,

        },

        "adaptive_policy": {

            "success_rate": 0.0,

            "tool_success_rate": 0.0,

            "repair_success_rate": 0.0,

            "evolution_success_rate": 0.0,

        },

        "recovery": {

            "last_recovery_at": None,

            "recovered_from_github": False,

            "recovery_source": None,

        },

    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_engine_state(
    state: Optional[Dict[str, Any]]
) -> Dict[str, Any]:

    base = default_engine_state()

    if not isinstance(state, dict):
        return base

    merged = copy.deepcopy(base)

    # --------------------------------------------------------
    # Top-level values
    # --------------------------------------------------------

    for key in merged:

        if key in state:

            if isinstance(
                merged[key],
                dict
            ):

                if isinstance(
                    state[key],
                    dict
                ):

                    merged[key].update(
                        state[key]
                    )

            else:

                merged[key] = state[key]

    # --------------------------------------------------------
    # Lists
    # --------------------------------------------------------

    if not isinstance(
        merged.get("verified_tools"),
        list
    ):

        merged["verified_tools"] = []

    if not isinstance(
        merged.get("quarantined"),
        list
    ):

        merged["quarantined"] = []

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    metrics = merged.get("metrics")

    if not isinstance(metrics, dict):
        metrics = {}

    default_metrics = (
        default_engine_state()["metrics"]
    )

    for key, value in default_metrics.items():

        metrics[key] = safe_int(
            metrics.get(key),
            value
        )

    merged["metrics"] = metrics

    # --------------------------------------------------------
    # Adaptive policy
    # --------------------------------------------------------

    policy = merged.get("adaptive_policy")

    if not isinstance(policy, dict):
        policy = {}

    default_policy = (
        default_engine_state()["adaptive_policy"]
    )

    for key, value in default_policy.items():

        policy[key] = safe_float(
            policy.get(key),
            value
        )

    merged["adaptive_policy"] = policy

    # --------------------------------------------------------
    # Golden state
    # --------------------------------------------------------

    golden = merged.get("golden_state")

    if not isinstance(golden, dict):
        golden = {}

    default_golden = (
        default_engine_state()["golden_state"]
    )

    for key, value in default_golden.items():

        if key not in golden:
            golden[key] = value

    golden["valid"] = bool(
        golden.get("valid", False)
    )

    merged["golden_state"] = golden

    # --------------------------------------------------------
    # Numeric normalization
    # --------------------------------------------------------

    merged["generation"] = safe_int(
        merged.get("generation"),
        0
    )

    merged["engine_cycle"] = safe_int(
        merged.get("engine_cycle"),
        0
    )

    merged["tool_count"] = len(
        merged["verified_tools"]
    )

    return merged


# ============================================================
# ENGINE STATE LOAD
# ============================================================

def load_engine_state() -> Dict[str, Any]:

    state = load_json(
        ENGINE_STATE_PATH,
        default_engine_state()
    )

    state = normalize_engine_state(state)

    return state


# ============================================================
# ENGINE STATE SAVE
# ============================================================

def save_engine_state(
    state: Dict[str, Any]
) -> Dict[str, Any]:

    state = normalize_engine_state(state)

    state["updated_at"] = utc_now()

    atomic_write_json(
        ENGINE_STATE_PATH,
        state
    )

    # --------------------------------------------------------
    # Immediate read-back verification
    # --------------------------------------------------------

    verification = load_json(
        ENGINE_STATE_PATH,
        {}
    )

    verification = normalize_engine_state(
        verification
    )

    if (
        verification.get("generation")
        != state.get("generation")
    ):

        raise RuntimeError(
            "Engine state verification failed."
        )

    return verification


# ============================================================
# TOOL REGISTRY
# ============================================================

def default_tool_registry() -> Dict[str, Any]:

    return {

        "schema_version": "tool-registry-1",

        "updated_at": utc_now(),

        "tools": [],

        "tool_count": 0,

    }


def load_tool_registry() -> Dict[str, Any]:

    registry = load_json(
        TOOL_REGISTRY_PATH,
        default_tool_registry()
    )

    if not isinstance(
        registry.get("tools"),
        list
    ):

        registry["tools"] = []

    registry["tool_count"] = len(
        registry["tools"]
    )

    return registry


def save_tool_registry(
    registry: Dict[str, Any]
) -> Dict[str, Any]:

    if not isinstance(registry, dict):
        registry = default_tool_registry()

    if not isinstance(
        registry.get("tools"),
        list
    ):

        registry["tools"] = []

    registry["tool_count"] = len(
        registry["tools"]
    )

    registry["updated_at"] = utc_now()

    atomic_write_json(
        TOOL_REGISTRY_PATH,
        registry
    )

    return load_tool_registry()


# ============================================================
# TOOL REGISTRATION
# ============================================================

def register_verified_tool(
    tool: Dict[str, Any]
) -> Dict[str, Any]:

    if not isinstance(tool, dict):
        raise ValueError(
            "Tool must be a dictionary."
        )

    name = str(
        tool.get("name", "")
    ).strip()

    if not name:
        raise ValueError(
            "Tool name is required."
        )

    if not bool(
        tool.get("verified", False)
    ):

        raise ValueError(
            f"Tool '{name}' cannot be registered "
            "without verified=True."
        )

    registry = load_tool_registry()

    tools = registry["tools"]

    # --------------------------------------------------------
    # Replace existing tool safely
    # --------------------------------------------------------

    replaced = False

    for index, existing in enumerate(tools):

        if (
            isinstance(existing, dict)
            and existing.get("name") == name
        ):

            tools[index] = copy.deepcopy(tool)
            replaced = True
            break

    if not replaced:

        tools.append(
            copy.deepcopy(tool)
        )

    registry["tools"] = tools

    return save_tool_registry(
        registry
    )


# ============================================================
# QUARANTINE
# ============================================================

def default_quarantine() -> Dict[str, Any]:

    return {

        "schema_version": "quarantine-1",

        "updated_at": utc_now(),

        "tools": [],

    }


def load_quarantine() -> Dict[str, Any]:

    data = load_json(
        QUARANTINE_PATH,
        default_quarantine()
    )

    if not isinstance(
        data.get("tools"),
        list
    ):

        data["tools"] = []

    return data


def quarantine_tool(
    tool_name: str,
    reason: str,
    observation: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    quarantine = load_quarantine()

    record = {

        "name": tool_name,

        "reason": reason,

        "observation": observation or {},

        "quarantined_at": utc_now(),

    }

    quarantine["tools"].append(
        record
    )

    quarantine["updated_at"] = utc_now()

    atomic_write_json(
        QUARANTINE_PATH,
        quarantine
    )

    return quarantine


# ============================================================
# EVOLUTION HISTORY
# ============================================================

def append_evolution_history(
    record: Dict[str, Any]
) -> bool:

    ensure_directories()

    if not isinstance(record, dict):
        raise ValueError(
            "Evolution history record must be a dict."
        )

    record = copy.deepcopy(record)

    record.setdefault(
        "timestamp",
        utc_now()
    )

    record.setdefault(
        "manager_version",
        STATE_MANAGER_VERSION
    )

    with open(
        EVOLUTION_HISTORY_PATH,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
        )

        f.write("\n")

        f.flush()

        os.fsync(
            f.fileno()
        )

    return True


def load_evolution_history() -> List[Dict[str, Any]]:

    if not EVOLUTION_HISTORY_PATH.exists():
        return []

    records = []

    try:

        with open(
            EVOLUTION_HISTORY_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:

                    record = json.loads(
                        line
                    )

                    if isinstance(
                        record,
                        dict
                    ):

                        records.append(
                            record
                        )

                except json.JSONDecodeError:

                    # One broken line must not
                    # destroy the entire history.
                    continue

    except OSError:

        return []

    return records


# ============================================================
# GOLDEN STATE
# ============================================================

def default_golden_state() -> Dict[str, Any]:

    return {

        "version": "golden-1",

        "created_at": utc_now(),

        "updated_at": utc_now(),

        "proxy_path": None,

        "golden_proxy": None,

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

        "status": "UNINITIALIZED",

    }


def load_golden_state() -> Dict[str, Any]:

    golden = load_json(
        GOLDEN_STATE_PATH,
        default_golden_state()
    )

    base = default_golden_state()

    for key, value in base.items():

        if key not in golden:

            golden[key] = copy.deepcopy(
                value
            )

    if not isinstance(
        golden.get("tools"),
        list
    ):

        golden["tools"] = []

    golden["tool_count"] = len(
        golden["tools"]
    )

    return golden


def validate_golden_state() -> Dict[str, Any]:

    golden = load_golden_state()

    proxy_path = golden.get(
        "golden_proxy"
    )

    expected_hash = golden.get(
        "proxy_hash"
    )

    result = {

        "valid": False,

        "exists": False,

        "hash": None,

        "expected_hash": expected_hash,

    }

    if not proxy_path:
        return result

    path = Path(proxy_path)

    if not path.exists():
        return result

    result["exists"] = True

    actual_hash = sha256_file(path)

    result["hash"] = actual_hash

    if (
        expected_hash
        and actual_hash == expected_hash
    ):

        result["valid"] = True

    return result


def create_golden_state(
    proxy_path: str,
    golden_proxy_path: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    health: Optional[Dict[str, bool]] = None,
    tests: Optional[Dict[str, bool]] = None
) -> Dict[str, Any]:

    ensure_directories()

    source = Path(proxy_path)
    destination = Path(
        golden_proxy_path
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Proxy does not exist: {source}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        source,
        destination
    )

    proxy_hash = sha256_file(
        destination
    )

    if not proxy_hash:

        raise RuntimeError(
            "Golden proxy hash could not be calculated."
        )

    golden = default_golden_state()

    golden.update({

        "created_at": utc_now(),

        "updated_at": utc_now(),

        "proxy_path": str(source),

        "golden_proxy": str(destination),

        "proxy_hash": proxy_hash,

        "tools": copy.deepcopy(
            tools or []
        ),

        "tool_count": len(
            tools or []
        ),

        "health": copy.deepcopy(
            health or {}
        ),

        "tests": copy.deepcopy(
            tests or {}
        ),

        "status": "VALID",

    })

    atomic_write_json(
        GOLDEN_STATE_PATH,
        golden
    )

    return load_golden_state()


# ============================================================
# METRICS
# ============================================================

def update_metrics(
    state: Dict[str, Any]
) -> Dict[str, Any]:

    state = normalize_engine_state(
        state
    )

    metrics = state["metrics"]

    attempts = safe_int(
        metrics.get("tool_attempts")
    )

    successes = safe_int(
        metrics.get("tool_successes")
    )

    failures = safe_int(
        metrics.get("tool_failures")
    )

    repair_attempts = safe_int(
        metrics.get("repair_attempts")
    )

    repair_successes = safe_int(
        metrics.get("repair_successes")
    )

    evolution_attempts = safe_int(
        metrics.get("evolution_attempts")
    )

    evolution_successes = safe_int(
        metrics.get("evolution_successes")
    )

    metrics["tool_attempts"] = attempts
    metrics["tool_successes"] = successes
    metrics["tool_failures"] = failures

    metrics["repair_attempts"] = repair_attempts
    metrics["repair_successes"] = repair_successes

    metrics["evolution_attempts"] = evolution_attempts
    metrics["evolution_successes"] = evolution_successes

    if attempts > 0:

        state["adaptive_policy"][
            "tool_success_rate"
        ] = successes / attempts

    if repair_attempts > 0:

        state["adaptive_policy"][
            "repair_success_rate"
        ] = (
            repair_successes
            / repair_attempts
        )

    if evolution_attempts > 0:

        state["adaptive_policy"][
            "evolution_success_rate"
        ] = (
            evolution_successes
            / evolution_attempts
        )

    total_attempts = (
        attempts
        + repair_attempts
        + evolution_attempts
    )

    total_successes = (
        successes
        + repair_successes
        + evolution_successes
    )

    if total_attempts > 0:

        state["adaptive_policy"][
            "success_rate"
        ] = (
            total_successes
            / total_attempts
        )

    return state


# ============================================================
# EVOLUTION TRANSACTION
# ============================================================

def begin_evolution(
    state: Dict[str, Any],
    candidate: str,
    evolution_id: str
) -> Dict[str, Any]:

    state = normalize_engine_state(
        state
    )

    state["engine_cycle"] += 1

    state["metrics"][
        "evolution_attempts"
    ] += 1

    state["last_candidate"] = candidate

    state["last_evolution_id"] = evolution_id

    state["last_status"] = "RUNNING"

    state["status"] = "EVOLVING"

    return save_engine_state(
        state
    )


def finish_evolution(
    state: Dict[str, Any],
    success: bool,
    candidate: Optional[str] = None,
    evolution_id: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:

    state = normalize_engine_state(
        state
    )

    if candidate is not None:
        state["last_candidate"] = candidate

    if evolution_id is not None:
        state["last_evolution_id"] = (
            evolution_id
        )

    if success:

        state["metrics"][
            "evolution_successes"
        ] += 1

        state["last_status"] = "SUCCESS"

        state["status"] = "EVOLVED"

    else:

        state["metrics"][
            "evolution_failures"
        ] += 1

        state["last_status"] = "FAILED"

        state["last_error"] = error

        state["status"] = "EVOLUTION_FAILED"

    state["generation"] += 1

    state = update_metrics(
        state
    )

    result = save_engine_state(
        state
    )

    append_evolution_history({

        "evolution_id":
            state.get(
                "last_evolution_id"
            ),

        "candidate":
            state.get(
                "last_candidate"
            ),

        "cycle":
            state.get(
                "engine_cycle"
            ),

        "generation":
            state.get(
                "generation"
            ),

        "status":
            state.get(
                "last_status"
            ),

        "success":
            success,

        "error":
            error,

        "timestamp":
            utc_now(),

    })

    return result


# ============================================================
# RECOVERY
# ============================================================

def build_recovery_snapshot(
    github_available: bool = False,
    recovery_source: Optional[str] = None
) -> Dict[str, Any]:

    state = load_engine_state()

    registry = load_tool_registry()

    quarantine = load_quarantine()

    history = load_evolution_history()

    golden = load_golden_state()

    golden_validation = (
        validate_golden_state()
    )

    state["tool_count"] = len(
        registry.get(
            "tools",
            []
        )
    )

    state["verified_tools"] = [
        tool.get("name")
        for tool in registry.get(
            "tools",
            []
        )
        if isinstance(tool, dict)
        and tool.get("verified") is True
    ]

    state["quarantined"] = [
        item.get("name")
        for item in quarantine.get(
            "tools",
            []
        )
        if isinstance(item, dict)
    ]

    state[
        "evolution_history_count"
    ] = len(history)

    state["golden_state"] = {

        "status":
            golden.get(
                "status",
                "UNKNOWN"
            ),

        "valid":
            golden_validation[
                "valid"
            ],

        "proxy_path":
            golden.get(
                "proxy_path"
            ),

        "golden_proxy":
            golden.get(
                "golden_proxy"
            ),

        "proxy_hash":
            golden_validation[
                "hash"
            ],

        "version":
            golden.get(
                "version",
                "golden-1"
            ),

    }

    state["recovery"] = {

        "last_recovery_at":
            utc_now(),

        "recovered_from_github":
            bool(github_available),

        "recovery_source":
            recovery_source,

    }

    state = normalize_engine_state(
        state
    )

    atomic_write_json(
        RECOVERY_STATE_PATH,
        state
    )

    return state


# ============================================================
# CONSISTENCY CHECK
# ============================================================

def consistency_check() -> Dict[str, Any]:

    state = load_engine_state()

    registry = load_tool_registry()

    quarantine = load_quarantine()

    history = load_evolution_history()

    golden = validate_golden_state()

    registry_tools = registry.get(
        "tools",
        []
    )

    verified_tools = [

        tool.get("name")

        for tool in registry_tools

        if isinstance(tool, dict)
        and tool.get("verified") is True

    ]

    quarantined = [

        item.get("name")

        for item in quarantine.get(
            "tools",
            []
        )

        if isinstance(item, dict)

    ]

    return {

        "state_exists":
            ENGINE_STATE_PATH.exists(),

        "registry_exists":
            TOOL_REGISTRY_PATH.exists(),

        "history_exists":
            EVOLUTION_HISTORY_PATH.exists(),

        "golden_exists":
            GOLDEN_STATE_PATH.exists(),

        "golden_valid":
            golden["valid"],

        "history_records":
            len(history),

        "verified_tools":
            verified_tools,

        "tool_count":
            len(verified_tools),

        "quarantined":
            quarantined,

        "generation":
            state.get(
                "generation",
                0
            ),

        "engine_cycle":
            state.get(
                "engine_cycle",
                0
            ),

        "last_candidate":
            state.get(
                "last_candidate"
            ),

        "last_status":
            state.get(
                "last_status"
            ),

        "consistent":
            (
                state.get(
                    "tool_count",
                    0
                )
                == len(verified_tools)
            ),

    }


# ============================================================
# INITIALIZE
# ============================================================

def initialize_state() -> Dict[str, Any]:

    ensure_directories()

    state = load_engine_state()

    registry = load_tool_registry()

    quarantine = load_quarantine()

    # --------------------------------------------------------
    # Synchronize registry → engine state
    # --------------------------------------------------------

    verified_tools = [

        tool.get("name")

        for tool in registry.get(
            "tools",
            []
        )

        if isinstance(tool, dict)
        and tool.get("verified") is True

    ]

    state["verified_tools"] = (
        verified_tools
    )

    state["tool_count"] = len(
        verified_tools
    )

    state["quarantined"] = [

        item.get("name")

        for item in quarantine.get(
            "tools",
            []
        )

        if isinstance(item, dict)

    ]

    state = update_metrics(
        state
    )

    save_engine_state(
        state
    )

    return state


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [

    "PROJECT_ROOT",

    "SELF_EVOLUTION_DIR",

    "STATE_DIR",

    "BACKUP_DIR",

    "ENGINE_STATE_PATH",

    "TOOL_REGISTRY_PATH",

    "GOLDEN_STATE_PATH",

    "EVOLUTION_HISTORY_PATH",

    "RECOVERY_STATE_PATH",

    "QUARANTINE_PATH",

    "STATE_MANAGER_VERSION",

    "default_engine_state",

    "normalize_engine_state",

    "load_engine_state",

    "save_engine_state",

    "load_tool_registry",

    "save_tool_registry",

    "register_verified_tool",

    "load_quarantine",

    "quarantine_tool",

    "append_evolution_history",

    "load_evolution_history",

    "load_golden_state",

    "validate_golden_state",

    "create_golden_state",

    "update_metrics",

    "begin_evolution",

    "finish_evolution",

    "build_recovery_snapshot",

    "consistency_check",

    "initialize_state",

]


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        " Kgo Autonomous Engine "
        "STATE MANAGER SELF TEST"
    )
    print("=" * 70)

    ensure_directories()

    state = initialize_state()

    print(
        "[OK] State initialized"
    )

    print(
        f"Generation : "
        f"{state.get('generation', 0)}"
    )

    print(
        f"Cycle      : "
        f"{state.get('engine_cycle', 0)}"
    )

    print(
        f"Tools      : "
        f"{state.get('verified_tools', [])}"
    )

    result = consistency_check()

    print()
    print(
        "[CONSISTENCY]"
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    print()
    print(
        "=" * 70
    )

    if result["consistent"]:

        print(
            "STATE MANAGER SELF TEST: PASS"
        )

    else:

        print(
            "STATE MANAGER SELF TEST: FAIL"
        )

    print("=" * 70)
