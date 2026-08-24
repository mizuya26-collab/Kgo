"""
surgical_proxy_v2
AUTONOMOUS ENGINE
=================

GitHub persistent development core.

Responsibilities:
    - State management
    - Golden State validation
    - Tool Registry
    - Evolution history
    - Quarantine
    - Regression protection
    - Rollback decision
    - Safe evolution cycles

IMPORTANT:
    This engine does NOT automatically trust a tool merely because
    a process returned exit code 0.

A tool becomes VERIFIED only when:
    1. Candidate exists
    2. Test was executed
    3. Expected marker was observed
    4. No unavailable-tool response was detected
    5. Regression checks pass
    6. State is persisted successfully
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# VERSION
# ============================================================

ENGINE_VERSION = "5.0.0"
ENGINE_NAME = "surgical_proxy_v2 AUTONOMOUS ENGINE"


# ============================================================
# PATH CONFIGURATION
# ============================================================

ROOT = Path(
    os.environ.get(
        "KGO_ROOT",
        Path(__file__).resolve().parents[1],
    )
).resolve()

ENGINE_DIR = ROOT / "engine"
STATE_DIR = ROOT / "state"
BACKUP_DIR = ROOT / "backups"
QUARANTINE_DIR = ROOT / "quarantine"
LOG_DIR = ROOT / "logs"


ENGINE_STATE_PATH = STATE_DIR / "engine_state.json"
GOLDEN_STATE_PATH = STATE_DIR / "golden_state.json"
TOOL_REGISTRY_PATH = STATE_DIR / "tool_registry.json"
EVOLUTION_HISTORY_PATH = STATE_DIR / "evolution_history.jsonl"


# ============================================================
# DIRECTORY INITIALIZATION
# ============================================================

for directory in (
    ENGINE_DIR,
    STATE_DIR,
    BACKUP_DIR,
    QUARANTINE_DIR,
    LOG_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# ============================================================
# TIME
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def short_timestamp() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y%m%d%H%M%S"
    )


# ============================================================
# SAFE JSON
# ============================================================

def atomic_write_json(
    path: Path,
    data: Dict[str, Any],
) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            data,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

        handle.flush()
        os.fsync(handle.fileno())

    os.replace(
        temporary,
        path,
    )


def load_json(
    path: Path,
    default: Any,
) -> Any:

    if not path.exists():
        return copy.deepcopy(default)

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            return json.load(handle)

    except Exception as exc:

        print(
            f"[WARN] JSON recovery failed: "
            f"{path}: {exc}"
        )

        return copy.deepcopy(default)


# ============================================================
# HASHING
# ============================================================

def sha256_file(
    path: Path,
) -> Optional[str]:

    if not path.exists():
        return None

    digest = hashlib.sha256()

    with path.open("rb") as handle:

        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# DEFAULT STATE
# ============================================================

def default_metrics() -> Dict[str, Any]:

    return {
        "tool_attempts": 0,
        "tool_successes": 0,
        "tool_failures": 0,

        "evolution_attempts": 0,
        "evolution_successes": 0,
        "evolution_failures": 0,

        "repair_attempts": 0,
        "repair_successes": 0,
        "repair_failures": 0,

        "rollback_count": 0,

        "false_success_rejections": 0,

        "last_updated": utc_now(),
    }


def default_engine_state() -> Dict[str, Any]:

    return {

        "schema_version": "5.0",

        "engine_version": ENGINE_VERSION,

        "created_at": utc_now(),

        "updated_at": utc_now(),

        "generation": 0,

        "engine_cycle": 0,

        "status": "INITIALIZED",

        "verified_tools": [],

        "quarantined_tools": [],

        "evolution_history_count": 0,

        "last_candidate": None,

        "last_evolution_id": None,

        "last_status": None,

        "metrics": default_metrics(),

    }


def default_golden_state() -> Dict[str, Any]:

    return {

        "schema_version": "5.0",

        "status": "UNINITIALIZED",

        "created_at": None,

        "updated_at": None,

        "proxy_path": None,

        "golden_proxy": None,

        "proxy_hash": None,

        "tools": [],

        "tool_count": 0,

        "health": {},

        "tests": {},

    }


def default_registry() -> Dict[str, Any]:

    return {

        "schema_version": "5.0",

        "tools": [],

        "updated_at": utc_now(),

    }


# ============================================================
# STATE NORMALIZATION
# ============================================================

def normalize_state(
    state: Any,
) -> Dict[str, Any]:

    if not isinstance(state, dict):

        state = {}

    defaults = default_engine_state()

    for key, value in defaults.items():

        if key not in state:

            state[key] = copy.deepcopy(value)

    if not isinstance(
        state.get("metrics"),
        dict,
    ):
        state["metrics"] = default_metrics()

    for key, value in default_metrics().items():

        if key not in state["metrics"]:

            state["metrics"][key] = value

    if not isinstance(
        state.get("verified_tools"),
        list,
    ):
        state["verified_tools"] = []

    if not isinstance(
        state.get("quarantined_tools"),
        list,
    ):
        state["quarantined_tools"] = []

    return state


# ============================================================
# TOOL CANDIDATE
# ============================================================

@dataclass
class ToolCandidate:

    name: str

    version: str

    risk_level: str

    capabilities: List[str]

    expected_marker: str

    source: str = "autonomous_engine"

    enabled: bool = True


# ============================================================
# CANDIDATE CATALOG
# ============================================================

CANDIDATES: List[ToolCandidate] = [

    ToolCandidate(
        name="Glob",
        version="claude-code",
        risk_level="low",
        capabilities=[
            "file_pattern_search"
        ],
        expected_marker="GLOB_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Grep",
        version="claude-code",
        risk_level="low",
        capabilities=[
            "content_search"
        ],
        expected_marker="GREP_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Bash",
        version="claude-code",
        risk_level="medium",
        capabilities=[
            "shell_command_execution"
        ],
        expected_marker="BASH_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Read",
        version="claude-code",
        risk_level="low",
        capabilities=[
            "file_read"
        ],
        expected_marker="READ_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Write",
        version="claude-code",
        risk_level="medium",
        capabilities=[
            "file_write"
        ],
        expected_marker="WRITE_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Edit",
        version="claude-code",
        risk_level="medium",
        capabilities=[
            "file_edit"
        ],
        expected_marker="EDIT_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="WebFetch",
        version="claude-code",
        risk_level="medium",
        capabilities=[
            "web_fetch"
        ],
        expected_marker="WEBFETCH_EVOLUTION_OK",
    ),

    ToolCandidate(
        name="Task",
        version="claude-code",
        risk_level="medium",
        capabilities=[
            "subagent_execution"
        ],
        expected_marker="TASK_EVOLUTION_OK",
    ),
]


# ============================================================
# LOAD STATE
# ============================================================

state = normalize_state(
    load_json(
        ENGINE_STATE_PATH,
        default_engine_state(),
    )
)

golden_state = load_json(
    GOLDEN_STATE_PATH,
    default_golden_state(),
)

registry = load_json(
    TOOL_REGISTRY_PATH,
    default_registry(),
)


# ============================================================
# NORMALIZE GOLDEN STATE
# ============================================================

def normalize_golden(
    value: Any,
) -> Dict[str, Any]:

    if not isinstance(value, dict):

        value = {}

    defaults = default_golden_state()

    for key, default in defaults.items():

        if key not in value:

            value[key] = copy.deepcopy(
                default
            )

    if not isinstance(
        value.get("tools"),
        list,
    ):
        value["tools"] = []

    if not isinstance(
        value.get("health"),
        dict,
    ):
        value["health"] = {}

    if not isinstance(
        value.get("tests"),
        dict,
    ):
        value["tests"] = {}

    return value


golden_state = normalize_golden(
    golden_state
)


# ============================================================
# SAVE STATE
# ============================================================

def save_all() -> None:

    state["updated_at"] = utc_now()

    state["metrics"][
        "last_updated"
    ] = utc_now()

    atomic_write_json(
        ENGINE_STATE_PATH,
        state,
    )

    atomic_write_json(
        GOLDEN_STATE_PATH,
        golden_state,
    )

    registry["updated_at"] = utc_now()

    atomic_write_json(
        TOOL_REGISTRY_PATH,
        registry,
    )


# ============================================================
# EVOLUTION LOG
# ============================================================

def append_history(
    record: Dict[str, Any],
) -> None:

    record = copy.deepcopy(record)

    record.setdefault(
        "timestamp",
        utc_now(),
    )

    with EVOLUTION_HISTORY_PATH.open(
        "a",
        encoding="utf-8",
    ) as handle:

        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

    state[
        "evolution_history_count"
    ] += 1


# ============================================================
# QUARANTINE
# ============================================================

def quarantine_tool(
    candidate: ToolCandidate,
    reason: str,
) -> None:

    entry = {

        "name": candidate.name,

        "version": candidate.version,

        "reason": reason,

        "risk_level": candidate.risk_level,

        "capabilities":
            candidate.capabilities,

        "timestamp": utc_now(),

    }

    existing = [

        item
        for item in
        state["quarantined_tools"]
        if item.get("name")
        != candidate.name

    ]

    existing.append(entry)

    state[
        "quarantined_tools"
    ] = existing

    state["metrics"][
        "false_success_rejections"
    ] += 1


# ============================================================
# VERIFIED TOOLS
# ============================================================

def verified_tool_names() -> List[str]:

    names = []

    for item in state[
        "verified_tools"
    ]:

        if isinstance(
            item,
            dict,
        ):

            name = item.get(
                "name"
            )

        else:

            name = item

        if name:
            names.append(name)

    return names


def is_verified(
    name: str,
) -> bool:

    return name in verified_tool_names()


# ============================================================
# GOLDEN STATE VALIDATION
# ============================================================

def validate_golden_state() -> bool:

    if golden_state.get(
        "status"
    ) != "VALID":

        return False

    golden_proxy = golden_state.get(
        "golden_proxy"
    )

    expected_hash = golden_state.get(
        "proxy_hash"
    )

    if not golden_proxy:
        return False

    proxy_path = Path(
        golden_proxy
    )

    if not proxy_path.exists():
        return False

    if not expected_hash:
        return False

    actual_hash = sha256_file(
        proxy_path
    )

    return (
        actual_hash == expected_hash
    )


# ============================================================
# GOLDEN STATE CREATION
# ============================================================

def initialize_golden_state(
    proxy_path: Optional[Path] = None,
) -> bool:

    if proxy_path is None:

        possible = [

            ROOT
            / "surgical_proxy_v2"
            / "proxy.py",

            ROOT
            / "proxy.py",

        ]

        for candidate in possible:

            if candidate.exists():

                proxy_path = candidate

                break

    if proxy_path is None:
        return False

    proxy_path = Path(
        proxy_path
    ).resolve()

    golden_proxy = (
        BACKUP_DIR
        / "golden_proxy.py"
    )

    shutil.copy2(
        proxy_path,
        golden_proxy,
    )

    proxy_hash = sha256_file(
        golden_proxy
    )

    golden_state.update({

        "status": "VALID",

        "created_at":
            golden_state.get(
                "created_at"
            ) or utc_now(),

        "updated_at": utc_now(),

        "proxy_path":
            str(proxy_path),

        "golden_proxy":
            str(golden_proxy),

        "proxy_hash":
            proxy_hash,

        "tools":
            copy.deepcopy(
                state[
                    "verified_tools"
                ]
            ),

        "tool_count":
            len(
                state[
                    "verified_tools"
                ]
            ),

    })

    save_all()

    return validate_golden_state()


# ============================================================
# TOOL VALIDATION
# ============================================================

UNAVAILABLE_MARKERS = [

    "does not provide",

    "do not have access",

    "not available",

    "unavailable",

    "can't run",

    "cannot run",

    "no such tool",

    "tool is not",

]


def validate_tool_observation(
    candidate: ToolCandidate,
    observation: Dict[str, Any],
) -> Dict[str, Any]:

    stdout = str(
        observation.get(
            "stdout",
            ""
        )
    )

    stderr = str(
        observation.get(
            "stderr",
            ""
        )
    )

    combined = (
        stdout
        + "\n"
        + stderr
    ).lower()

    marker_found = (
        candidate.expected_marker
        in stdout
    )

    unavailable_detected = any(
        marker in combined
        for marker
        in UNAVAILABLE_MARKERS
    )

    return {

        "returncode_ok":
            observation.get(
                "returncode"
            ) == 0,

        "marker_found":
            marker_found,

        "unavailable_detected":
            unavailable_detected,

        "actual_invocation":
            bool(
                observation.get(
                    "actual_invocation",
                    False,
                )
            ),

        "artifact_ok":
            bool(
                observation.get(
                    "artifact_ok",
                    False,
                )
            ),

        "stderr_empty":
            stderr.strip()
            == "",

    }


# ============================================================
# REAL VALIDATION GATE
# ============================================================

def real_validation_gate(
    candidate: ToolCandidate,
    observation: Dict[str, Any],
) -> tuple[bool, Dict[str, Any], str]:

    result = validate_tool_observation(
        candidate,
        observation,
    )

    if not result[
        "returncode_ok"
    ]:

        return (
            False,
            result,
            "returncode_failed",
        )

    if not result[
        "marker_found"
    ]:

        return (
            False,
            result,
            "expected_marker_missing",
        )

    if result[
        "unavailable_detected"
    ]:

        return (
            False,
            result,
            "tool_unavailable",
        )

    if not result[
        "actual_invocation"
    ]:

        return (
            False,
            result,
            "actual_invocation_missing",
        )

    if not result[
        "artifact_ok"
    ]:

        return (
            False,
            result,
            "artifact_validation_failed",
        )

    return (
        True,
        result,
        "verified",
    )


# ============================================================
# REGRESSION CHECK
# ============================================================

def regression_check() -> bool:

    if not validate_golden_state():

        print(
            "[REGRESSION] Golden State invalid"
        )

        return False

    if not isinstance(
        state.get(
            "verified_tools"
        ),
        list,
    ):

        return False

    if not isinstance(
        registry.get(
            "tools"
        ),
        list,
    ):

        return False

    return True


# ============================================================
# REGISTER VERIFIED TOOL
# ============================================================

def register_verified_tool(
    candidate: ToolCandidate,
    observation: Dict[str, Any],
) -> None:

    entry = {

        "name":
            candidate.name,

        "version":
            candidate.version,

        "status":
            "VERIFIED",

        "risk_level":
            candidate.risk_level,

        "capabilities":
            candidate.capabilities,

        "verified":
            True,

        "source":
            candidate.source,

        "verified_at":
            utc_now(),

        "test_elapsed_sec":
            observation.get(
                "elapsed_sec"
            ),

    }

    state[
        "verified_tools"
    ] = [

        item
        for item in
        state[
            "verified_tools"
        ]
        if (
            item.get("name")
            if isinstance(
                item,
                dict,
            )
            else item
        )
        != candidate.name

    ]

    state[
        "verified_tools"
    ].append(entry)

    registry[
        "tools"
    ] = copy.deepcopy(
        state[
            "verified_tools"
        ]
    )

    golden_state[
        "tools"
    ] = copy.deepcopy(
        state[
            "verified_tools"
        ]
    )

    golden_state[
        "tool_count"
    ] = len(
        state[
            "verified_tools"
        ]
    )


# ============================================================
# CANDIDATE SELECTION
# ============================================================

def select_next_candidate() -> Optional[ToolCandidate]:

    verified = set(
        verified_tool_names()
    )

    quarantined = {

        item.get("name")

        for item
        in state[
            "quarantined_tools"
        ]

        if isinstance(
            item,
            dict,
        )

    }

    for candidate in CANDIDATES:

        if not candidate.enabled:
            continue

        if candidate.name in verified:
            continue

        if candidate.name in quarantined:
            continue

        return candidate

    return None


# ============================================================
# EVOLUTION ID
# ============================================================

def evolution_id(
    candidate: ToolCandidate,
) -> str:

    return (
        f"EV5-"
        f"{state['engine_cycle'] + 1:04d}-"
        f"{candidate.name}-"
        f"{short_timestamp()}-"
        f"{uuid.uuid4().hex[:6]}"
    )


# ============================================================
# EVOLUTION CYCLE
# ============================================================

def evolution_cycle(
    candidate: ToolCandidate,
    observation: Dict[str, Any],
) -> bool:

    state[
        "engine_cycle"
    ] += 1

    state[
        "metrics"
    ][
        "tool_attempts"
    ] += 1

    state[
        "metrics"
    ][
        "evolution_attempts"
    ] += 1

    state[
        "last_candidate"
    ] = candidate.name

    eid = evolution_id(
        candidate
    )

    state[
        "last_evolution_id"
    ] = eid

    print()
    print("=" * 70)
    print("EVOLUTION CYCLE")
    print("=" * 70)

    print(
        f"Evolution ID : {eid}"
    )

    print(
        f"Candidate    : {candidate.name}"
    )

    print(
        f"Cycle        : "
        f"{state['engine_cycle']}"
    )

    print(
        f"Risk         : "
        f"{candidate.risk_level}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # BACKUP
    # --------------------------------------------------------

    backup_name = (
        f"pre_{eid}.json"
    )

    backup_path = (
        BACKUP_DIR
        / backup_name
    )

    atomic_write_json(
        backup_path,
        copy.deepcopy(state),
    )

    print(
        f"[BACKUP] {backup_path}"
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    started = time.time()

    ok, validation, reason = (
        real_validation_gate(
            candidate,
            observation,
        )
    )

    elapsed = (
        observation.get(
            "elapsed_sec"
        )
    )

    if elapsed is None:
        elapsed = round(
            time.time() - started,
            3,
        )

    observation[
        "elapsed_sec"
    ] = elapsed

    # --------------------------------------------------------
    # FAILURE
    # --------------------------------------------------------

    if not ok:

        state[
            "metrics"
        ][
            "tool_failures"
        ] += 1

        state[
            "metrics"
        ][
            "evolution_failures"
        ] += 1

        quarantine_tool(
            candidate,
            reason,
        )

        state[
            "last_status"
        ] = "REJECTED"

        append_history({

            "evolution_id": eid,

            "candidate":
                candidate.name,

            "status":
                "REJECTED",

            "reason":
                reason,

            "validation":
                validation,

            "observation":
                observation,

        })

        save_all()

        print()
        print(
            "🔴 TOOL EXPANSION REJECTED"
        )

        print(
            f"Tool   : {candidate.name}"
        )

        print(
            f"Reason : {reason}"
        )

        print(
            "[INFO] Candidate quarantined."
        )

        return False

    # --------------------------------------------------------
    # REGRESSION
    # --------------------------------------------------------

    if not regression_check():

        state[
            "metrics"
        ][
            "tool_failures"
        ] += 1

        state[
            "metrics"
        ][
            "evolution_failures"
        ] += 1

        quarantine_tool(
            candidate,
            "regression_failed",
        )

        state[
            "last_status"
        ] = "ROLLBACK"

        append_history({

            "evolution_id": eid,

            "candidate":
                candidate.name,

            "status":
                "ROLLBACK",

            "reason":
                "regression_failed",

        })

        save_all()

        print(
            "[ROLLBACK] Regression failed."
        )

        return False

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    register_verified_tool(
        candidate,
        observation,
    )

    state[
        "metrics"
    ][
        "tool_attempts"
    ] += 0

    state[
        "metrics"
    ][
        "tool_successes"
    ] += 1

    state[
        "metrics"
    ][
        "evolution_successes"
    ] += 1

    state[
        "last_status"
    ] = "EVOLVED"

    append_history({

        "evolution_id": eid,

        "candidate":
            candidate.name,

        "status":
            "VERIFIED",

        "validation":
            validation,

        "observation":
            observation,

    })

    save_all()

    print()
    print(
        "🟢 TOOL EXPANSION SUCCESS"
    )

    print(
        f"{candidate.name} "
        "実機検証成功"
    )

    print(
        f"[REGISTERED] "
        f"{candidate.name} → VERIFIED"
    )

    print(
        f"[TOOL COUNT] "
        f"{len(state['verified_tools'])}"
    )

    return True


# ============================================================
# ENGINE STATUS
# ============================================================

def engine_status() -> Dict[str, Any]:

    metrics = state[
        "metrics"
    ]

    def rate(
        successes: int,
        attempts: int,
    ) -> float:

        if attempts <= 0:
            return 0.0

        return round(
            successes / attempts,
            4,
        )

    return {

        "engine_version":
            ENGINE_VERSION,

        "generation":
            state[
                "generation"
            ],

        "engine_cycle":
            state[
                "engine_cycle"
            ],

        "status":
            state[
                "status"
            ],

        "verified_tools":
            verified_tool_names(),

        "quarantined_tools":
            [
                item.get("name")
                for item
                in state[
                    "quarantined_tools"
                ]
                if isinstance(
                    item,
                    dict,
                )
            ],

        "metrics": {

            "tool_success_rate":
                rate(
                    metrics[
                        "tool_successes"
                    ],
                    metrics[
                        "tool_attempts"
                    ],
                ),

            "evolution_success_rate":
                rate(
                    metrics[
                        "evolution_successes"
                    ],
                    metrics[
                        "evolution_attempts"
                    ],
                ),

            "repair_success_rate":
                rate(
                    metrics[
                        "repair_successes"
                    ],
                    metrics[
                        "repair_attempts"
                    ],
                ),

            "false_success_rejections":
                metrics[
                    "false_success_rejections"
                ],

        },

        "golden_valid":
            validate_golden_state(),

    }


# ============================================================
# SAFE DEMO OBSERVATION
# ============================================================

def make_demo_observation(
    candidate: ToolCandidate,
) -> Dict[str, Any]:

    """
    Local structural test.

    This intentionally does NOT claim that the real Claude
    tool exists.

    A real integration must replace this observation with
    actual Claude/proxy execution results.
    """

    return {

        "returncode":
            0,

        "stdout":
            "",

        "stderr":
            "",

        "actual_invocation":
            False,

        "artifact_ok":
            False,

        "elapsed_sec":
            0.0,

    }


# ============================================================
# MAIN
# ============================================================

def main(
    max_cycles: int = 1,
) -> int:

    print("=" * 70)

    print(
        f" {ENGINE_NAME} v{ENGINE_VERSION}"
    )

    print(
        " SAFE DEVELOPMENT CORE"
    )

    print("=" * 70)

    print(
        f"[ROOT] {ROOT}"
    )

    print(
        f"[ENGINE] {ENGINE_VERSION}"
    )

    print()

    print(
        "[STATE]"
    )

    print(
        f"  Generation : "
        f"{state['generation']}"
    )

    print(
        f"  Cycle      : "
        f"{state['engine_cycle']}"
    )

    print(
        f"  Tools      : "
        f"{verified_tool_names()}"
    )

    print(
        f"  Golden     : "
        f"{validate_golden_state()}"
    )

    print()

    # --------------------------------------------------------
    # NEVER EVOLVE FROM EMPTY GOLDEN STATE
    # --------------------------------------------------------

    if not validate_golden_state():

        print(
            "[SAFE STOP]"
        )

        print(
            "Golden StateがVALIDではありません。"
        )

        print(
            "Evolutionを開始しません。"
        )

        print(
            "先にGolden Stateを確立してください。"
        )

        return 2

    # --------------------------------------------------------
    # EVOLUTION
    # --------------------------------------------------------

    cycles = 0

    while cycles < max_cycles:

        candidate = (
            select_next_candidate()
        )

        if candidate is None:

            state[
                "status"
            ] = "NO_CANDIDATE"

            save_all()

            print(
                "[STOP] "
                "検証可能な候補がありません。"
            )

            break

        print()
        print(
            f"[NEXT] "
            f"{candidate.name}"
        )

        print(
            f"[CAPABILITY] "
            f"{candidate.capabilities}"
        )

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Demo observation intentionally fails.
        #
        # This prevents false VERIFIED registration.
        # ----------------------------------------------------

        observation = (
            make_demo_observation(
                candidate
            )
        )

        evolution_cycle(
            candidate,
            observation,
        )

        cycles += 1

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "AUTONOMOUS ENGINE FINAL"
    )
    print("=" * 70)

    status = engine_status()

    print(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main(
            max_cycles=1
        )
    )
