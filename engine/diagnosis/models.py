from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List


class Classification(str, Enum):
    HEALTHY = "HEALTHY"
    MISSING = "MISSING"
    SERVICE_DOWN = "SERVICE_DOWN"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class RootCauseCategory(str, Enum):
    DEPENDENCY = "DEPENDENCY"
    SERVICE = "SERVICE"
    CONFIG = "CONFIG"
    UNKNOWN = "UNKNOWN"


@dataclass
class CheckResult:
    ok: bool
    component: str
    detail: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosisResult:
    component: str
    classification: str = Classification.UNKNOWN.value
    root_cause_category: str = RootCauseCategory.UNKNOWN.value
    root_cause: str = "N/A"
    confidence: float = 0.0
    repairable: bool = False
    recommended_action: str = "NONE"
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosisReport:
    generation: int
    timestamp: float
    results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation": self.generation,
            "timestamp": self.timestamp,
            "results": self.results,
        }
