"""Security audit trail.

Writes through Python logging and, when available, the existing SQLite database.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from security.risk import RiskLevel

logger = logging.getLogger("aura.security.audit")


@dataclass(frozen=True)
class SecurityAuditEvent:
    action: str
    risk: RiskLevel
    allowed: bool
    reason: str
    timestamp: str


class SecurityAuditLogger:
    def __init__(self, db=None):
        self.db = db

    def record(self, action: str, risk: RiskLevel, allowed: bool, reason: str) -> None:
        event = SecurityAuditEvent(
            action=action,
            risk=risk,
            allowed=allowed,
            reason=reason,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )
        logger.info(
            "SECURITY action=%s risk=%s allowed=%s reason=%s",
            event.action,
            event.risk.name,
            event.allowed,
            event.reason,
        )
        if self.db is not None:
            try:
                self.db.log_security_audit(
                    action=event.action,
                    risk=event.risk.name,
                    allowed=event.allowed,
                    reason=event.reason,
                )
            except Exception:
                # Security auditing must not crash the assistant; the rotating
                # application log still keeps the event.
                logger.exception("Impossible d'ecrire l'audit securite en base")
