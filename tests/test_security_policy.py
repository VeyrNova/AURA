import unittest

from security.permissions import Permission
from security.policy_engine import SecurityPolicyEngine
from security.risk import RiskLevel


class SecurityPolicyTests(unittest.TestCase):
    def test_safe_action_is_allowed(self):
        engine = SecurityPolicyEngine()
        decision = engine.authorize("LIST_NOTES")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.SAFE)

    def test_low_action_is_allowed(self):
        engine = SecurityPolicyEngine()
        decision = engine.authorize("CREATE_TASK", {"raw": "test"})
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.LOW)

    def test_medium_record_deletion_is_audited_and_allowed(self):
        engine = SecurityPolicyEngine()
        decision = engine.authorize("DELETE_NOTE", {"raw": "1"})
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.MEDIUM)

    def test_unknown_action_fails_closed(self):
        engine = SecurityPolicyEngine()
        decision = engine.authorize("DO_ANYTHING")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.CRITICAL)

    def test_high_action_needs_permission_and_confirmation(self):
        engine = SecurityPolicyEngine(granted_permissions={Permission.PROCESS_CONTROL})
        decision = engine.authorize("RUN_PROGRAM")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.confirmation_required)

        confirmed = engine.authorize("RUN_PROGRAM", user_confirmed=True)
        self.assertTrue(confirmed.allowed)

    def test_critical_action_stays_denied_even_when_confirmed(self):
        engine = SecurityPolicyEngine(granted_permissions={Permission.SYSTEM_CHANGE})
        decision = engine.authorize("DISABLE_SECURITY", user_confirmed=True)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.CRITICAL)


if __name__ == "__main__":
    unittest.main()
