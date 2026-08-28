from __future__ import annotations

from .models import CheckResult, DiagnosisResult, Classification, RootCauseCategory
from .signatures import match_signature


def classify(check: CheckResult, repairable_map: dict | None = None) -> DiagnosisResult:
    repairable_map = repairable_map or {}

    if check.ok:
        return DiagnosisResult(
            component=check.component,
            classification=Classification.HEALTHY.value,
            root_cause_category=RootCauseCategory.UNKNOWN.value,
            root_cause="N/A",
            confidence=1.0,
            repairable=False,
            recommended_action="NONE",
            detail=check.detail,
            evidence=check.raw,
        )

    sig = match_signature(check.detail)
    root_cause = sig.root_cause if sig else "UNKNOWN"
    category = sig.category if sig else RootCauseCategory.UNKNOWN.value
    action_info = repairable_map.get(root_cause, {"action": "NONE", "confidence": 0.5, "repairable": False})

    return DiagnosisResult(
        component=check.component,
        classification=Classification.SERVICE_DOWN.value if category == RootCauseCategory.SERVICE.value else Classification.MISSING.value,
        root_cause_category=category,
        root_cause=root_cause,
        confidence=action_info["confidence"],
        repairable=action_info["repairable"],
        recommended_action=action_info["action"],
        detail=check.detail,
        evidence=check.raw,
    )
