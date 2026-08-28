from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict


@dataclass
class RepairAction:
    component: str
    classification: str
    root_cause: str
    planned_action: str
    confidence: float
    risk_class: str
    requires_human_approval: bool
    execution_allowed: bool = False
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
