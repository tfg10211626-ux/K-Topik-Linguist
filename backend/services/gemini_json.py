from __future__ import annotations

import json
import re
from typing import Any


def strip_json_fence(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", t)
    if m:
        return m.group(1).strip()
    return t


def parse_json_text(raw_text: str) -> Any:
    return json.loads(strip_json_fence(raw_text))
