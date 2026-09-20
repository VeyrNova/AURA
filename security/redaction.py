"""Best-effort redaction for logs and diagnostics.

Defense-in-depth only: application code should avoid logging secrets in the first place.
"""
import logging
import re

_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)([^\s,;]+)"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|passwd|secret)\s*[:=]\s*)([^\s,;]+)"),
]


def redact_sensitive_data(value: object) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1<REDACTED>", text)
    return text


def _redact_arg(value):
    if isinstance(value, str):
        return redact_sensitive_data(value)
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(_redact_arg(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {key: _redact_arg(value) for key, value in record.args.items()}
        return True
