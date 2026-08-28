from __future__ import annotations

import re
from typing import NamedTuple, Optional, List

from .models import RootCauseCategory


class Signature(NamedTuple):
    pattern: str
    root_cause: str
    category: str


SIGNATURES: List[Signature] = [
    Signature(r"not\s+found\s+on\s+path", "TOOL_NOT_ON_PATH", RootCauseCategory.DEPENDENCY.value),
    Signature(r"connection\s+refused|closed", "PROXY_UNREACHABLE", RootCauseCategory.SERVICE.value),
    Signature(r"port.*in\s+use", "PORT_IN_USE", RootCauseCategory.SERVICE.value),
]


def match_signature(detail: str) -> Optional[Signature]:
    for sig in SIGNATURES:
        if re.search(sig.pattern, detail, re.IGNORECASE):
            return sig
    return None
