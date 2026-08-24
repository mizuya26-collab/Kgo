"""
Kgo Autonomous Engine
Persistent engine state management.

重要:
- 自己進化の進行状態を保存する
- Golden Stateを追跡する
- Tool RegistryとEvolution Historyを追跡する
- Colab切断後の復旧に使用する
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"


def utc_now() -> str:
    """現在時刻をUTC ISO形式で返す。"""
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str) -> Optional[str]:
    """ファイルのSHA256を計算する。"""
    if not os.path.isfile(path):
        return None

    digest = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def default_state() -> Dict[str, Any]:
    """新規Engine Stateを生成する。"""

    return {
        "schema_version": SCHEMA_VERSION,

        "project": {
            "name": "Kgo",
        },

        "engine": {
            "version": "v4.2",
            "generation": 0,
            "cycle": 0,
            "status": "INITIALIZED",
            "started_at": None,
            "updated_at": utc_now(),
        },

        "golden_state": {
            "status": "UNINITIALIZED",
            "version": None,
            "proxy_path": None,
            "golden_proxy": None,
            "proxy_hash": None,
            "valid": False,
        },

        "tools": {
            "verified": [],
            "quarantined": [],
            "pending": [],
        },

        "evolution": {
            "last_evolution_id": None,
            "last_candidate": None,
            "last_status": None,
            "successful_cycles": 0,
            "failed_cycles": 0,
        },

        "repair": {
            "attempts": 0,
            "successful": 0,
            "failed": 0,
            "last_error": None,
            "last_repair": None,
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

            "regressions": 0,
        },

        "resume": {
            "ready": False,
            "generation": 0,
            "cycle": 0,
            "last_candidate": None,
            "last_evolution_id": None,
            "last_status": None,
        },

        "diagnosis": {
            "root_cause": None,
            "confidence": 0.0,
            "last_error_type": None,
            "last_error_message": None,
        },

        "environment": {
            "runtime": None,
            "gpu": None,
            "ollama": False,
            "claude": False,
        },

        "audit": {
            "created_at": utc_now(),
            "updated_at": utc_now(),
        },
    }


class StateManager:
    """
    Engine Stateの安全な読み書きを担当する。

    特徴:
    - Atomic write
    - JSON検証
    - None-safe
    - 欠落キーの自動補完
    - 更新時刻の自動記録
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)

        directory = os.path.dirname(self.path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        self.state = default_state()

    # ---------------------------------------------------------
    # LOAD
    # ---------------------------------------------------------

    def load(self) -> Dict[str, Any]:
        """既存stateを読み込む。存在しなければ新規stateを返す。"""

        if not os.path.isfile(self.path):
            self.state = default_state()
            return self.state

        try:
            with open(
                self.path,
                "r",
                encoding="utf-8",
            ) as f:
                loaded = json.load(f)

            if not isinstance(loaded, dict):
                raise ValueError("State root must be an object.")

            self.state = self._merge_defaults(
                loaded,
                default_state(),
            )

            return self.state

        except Exception as exc:
            raise RuntimeError(
                f"Failed to load engine state: {exc}"
            ) from exc

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save(self) -> bool:
        """Atomic write + read-back verification。"""

        self.state["audit"]["updated_at"] = utc_now()
        self.state["engine"]["updated_at"] = utc_now()

        directory = os.path.dirname(self.path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(
            prefix=".engine_state_",
            suffix=".tmp",
            dir=directory or None,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    self.state,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

                f.flush()
                os.fsync(f.fileno())

            os.replace(
                temp_path,
                self.path,
            )

            # Read-back verification
            with open(
                self.path,
                "r",
                encoding="utf-8",
            ) as f:
                verified = json.load(f)

            if not isinstance(verified, dict):
                raise RuntimeError(
                    "State verification failed."
                )

            self.state = verified

            return True

        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)

            raise

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    def update(
        self,
        section: str,
        values: Dict[str, Any],
    ) -> None:
        """指定セクションを安全に更新する。"""

        if not isinstance(values, dict):
            raise TypeError(
                "values must be a dictionary."
            )

        current = self.state.setdefault(
            section,
            {},
        )

        if not isinstance(current, dict):
            current = {}
            self.state[section] = current

        current.update(copy.deepcopy(values))

        self.state["audit"]["updated_at"] = utc_now()

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

    def get(
        self,
        section: str,
        key: Optional[str] = None,
        default: Any = None,
    ) -> Any:
        """None-safeな値取得。"""

        section_data = self.state.get(
            section,
            {},
        )

        if not isinstance(section_data, dict):
            return default

        if key is None:
            return section_data

        return section_data.get(
            key,
            default,
        )

    # ---------------------------------------------------------
    # TOOL MANAGEMENT
    # ---------------------------------------------------------

    def add_verified_tool(
        self,
        tool: Dict[str, Any],
    ) -> bool:
        """Verified Toolを登録する。"""

        if not isinstance(tool, dict):
            raise TypeError(
                "tool must be a dictionary."
            )

        name = tool.get("name")

        if not name:
            raise ValueError(
                "Tool name is required."
            )

        tools = self.state.setdefault(
            "tools",
            {},
        )

        verified = tools.setdefault(
            "verified",
            [],
        )

        # 重複登録防止
        for existing in verified:
            if existing.get("name") == name:
                return False

        tool = copy.deepcopy(tool)

        tool.setdefault(
            "verified",
            True,
        )

        tool.setdefault(
            "verified_at",
            utc_now(),
        )

        verified.append(tool)

        return True

    def quarantine_tool(
        self,
        tool: Dict[str, Any],
        reason: str,
    ) -> None:
        """検証失敗したツールを隔離する。"""

        if not isinstance(tool, dict):
            raise TypeError(
                "tool must be a dictionary."
            )

        entry = copy.deepcopy(tool)

        entry["verified"] = False
        entry["quarantined"] = True
        entry["quarantine_reason"] = reason
        entry["quarantined_at"] = utc_now()

        self.state["tools"].setdefault(
            "quarantined",
            [],
        ).append(entry)

    # ---------------------------------------------------------
    # EVOLUTION
    # ---------------------------------------------------------

    def begin_evolution(
        self,
        evolution_id: str,
        candidate: str,
    ) -> None:
        """Evolution開始状態を記録する。"""

        engine = self.state["engine"]
        evolution = self.state["evolution"]
        metrics = self.state["metrics"]

        engine["cycle"] = int(
            engine.get("cycle", 0)
        ) + 1

        evolution["last_evolution_id"] = evolution_id
        evolution["last_candidate"] = candidate
        evolution["last_status"] = "RUNNING"

        metrics["evolution_attempts"] = int(
            metrics.get(
                "evolution_attempts",
                0,
            )
        ) + 1

        self.state["resume"] = {
            "ready": False,
            "generation": engine.get(
                "generation",
                0,
            ),
            "cycle": engine.get(
                "cycle",
                0,
            ),
            "last_candidate": candidate,
            "last_evolution_id": evolution_id,
            "last_status": "RUNNING",
        }

    def finish_evolution(
        self,
        success: bool,
        generation_increment: bool = True,
    ) -> None:
        """Evolution終了状態を記録する。"""

        engine = self.state["engine"]
        evolution = self.state["evolution"]
        metrics = self.state["metrics"]

        if success:
            evolution["last_status"] = "SUCCESS"

            evolution["successful_cycles"] = int(
                evolution.get(
                    "successful_cycles",
                    0,
                )
            ) + 1

            metrics["evolution_successes"] = int(
                metrics.get(
                    "evolution_successes",
                    0,
                )
            ) + 1

            if generation_increment:
                engine["generation"] = int(
                    engine.get(
                        "generation",
                        0,
                    )
                ) + 1

        else:
            evolution["last_status"] = "FAILED"

            evolution["failed_cycles"] = int(
                evolution.get(
                    "failed_cycles",
                    0,
                )
            ) + 1

            metrics["evolution_failures"] = int(
                metrics.get(
                    "evolution_failures",
                    0,
                )
            ) + 1

        self.state["resume"] = {
            "ready": True,
            "generation": engine.get(
                "generation",
                0,
            ),
            "cycle": engine.get(
                "cycle",
                0,
            ),
            "last_candidate": evolution.get(
                "last_candidate"
            ),
            "last_evolution_id": evolution.get(
                "last_evolution_id"
            ),
            "last_status": evolution.get(
                "last_status"
            ),
        }

    # ---------------------------------------------------------
    # GOLDEN STATE
    # ---------------------------------------------------------

    def set_golden_state(
        self,
        proxy_path: str,
        golden_proxy: str,
        version: str = "golden-1",
    ) -> None:
        """Golden Stateを登録する。"""

        proxy_hash = sha256_file(
            proxy_path
        )

        self.state["golden_state"] = {
            "status": (
                "VALID"
                if proxy_hash
                else "INVALID"
            ),
            "version": version,
            "proxy_path": proxy_path,
            "golden_proxy": golden_proxy,
            "proxy_hash": proxy_hash,
            "valid": bool(proxy_hash),
            "updated_at": utc_now(),
        }

    # ---------------------------------------------------------
    # RESUME
    # ---------------------------------------------------------

    def mark_resume_ready(self) -> None:
        """安全な復旧ポイントとしてマークする。"""

        engine = self.state["engine"]
        evolution = self.state["evolution"]

        self.state["resume"] = {
            "ready": True,
            "generation": engine.get(
                "generation",
                0,
            ),
            "cycle": engine.get(
                "cycle",
                0,
            ),
            "last_candidate": evolution.get(
                "last_candidate"
            ),
            "last_evolution_id": evolution.get(
                "last_evolution_id"
            ),
            "last_status": evolution.get(
                "last_status"
            ),
        }

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """現在状態のコピーを返す。"""

        return copy.deepcopy(
            self.state
        )

    # ---------------------------------------------------------
    # INTERNAL
    # ---------------------------------------------------------

    @staticmethod
    def _merge_defaults(
        loaded: Dict[str, Any],
        defaults: Dict[str, Any],
    ) -> Dict[str, Any]:
        """欠落したキーをdefaultsから補完する。"""

        result = copy.deepcopy(
            defaults
        )

        for key, value in loaded.items():

            if (
                isinstance(value, dict)
                and isinstance(
                    result.get(key),
                    dict,
                )
            ):
                result[key] = StateManager._merge_defaults(
                    value,
                    result[key],
                )

            else:
                result[key] = value

        return result


__all__ = [
    "StateManager",
    "default_state",
    "sha256_file",
]
