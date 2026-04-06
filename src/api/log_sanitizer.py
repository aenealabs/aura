"""Log sanitization utility to prevent log injection attacks (CWE-117).

Sanitizes user-controlled input before interpolation into log messages,
stripping newlines and control characters that could forge log entries.
"""

import re
from typing import Any

# Matches control characters (C0/C1) except tab, which is common in structured logs
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize_log(value: Any) -> str:
    """Sanitize a value for safe inclusion in log messages.

    Replaces newlines and carriage returns with escaped representations
    and strips other control characters to prevent log forging.
    """
    s = str(value)
    s = s.replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")
    s = _CONTROL_CHARS.sub("", s)
    return s
