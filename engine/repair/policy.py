from __future__ import annotations

from typing import NamedTuple


class PolicyEntry(NamedTuple):
    risk_class: str
    requires_human_approval: bool


POLICY_TABLE = {
    "TOOL_NOT_ON_PATH": PolicyEntry(risk_class="DEPENDENCY_INSTALL", requires_human_approval=True),
    "PROXY_UNREACHABLE": PolicyEntry(risk_class="SERVICE_START", requires_human_approval=True),
    "PORT_IN_USE": PolicyEntry(risk_class="CONFIG_CHANGE", requires_human_approval=True),
    "FREE_PORT_OR_RECONFIGURE": PolicyEntry(risk_class="CONFIG_CHANGE", requires_human_approval=True),
}

DEFAULT_POLICY = PolicyEntry(risk_class="UNKNOWN", requires_human_approval=True)


def resolve_policy(root_cause: str) -> PolicyEntry:
    return POLICY_TABLE.get(root_cause, DEFAULT_POLICY)
