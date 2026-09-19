import unittest

from core.local_action_context import LocalActionContext


class LocalActionContextV071112Tests(unittest.TestCase):
    def test_task_title_reply_completes_pending_create_task(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("faire les levées des non conformités ICPE")
        self.assertTrue(result.handled)
        self.assertEqual(result.intent, "CREATE_TASK")
        self.assertEqual(result.params, {"raw": "faire les levées des non conformités ICPE"})
        self.assertFalse(ctx.active)

    def test_task_title_prefix_is_cleaned(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("La tâche c'est préparer le rapport.")
        self.assertEqual(result.params["raw"], "préparer le rapport")

    def test_imperative_search_word_can_still_be_a_task_title(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("recherche les causes de la non conformité")
        self.assertTrue(result.handled)
        self.assertEqual(result.params["raw"], "recherche les causes de la non conformité")

    def test_cancel_is_local_and_closes_slot(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("annule")
        self.assertTrue(result.handled)
        self.assertFalse(result.intent)
        self.assertIn("annule", result.response.lower())
        self.assertFalse(ctx.active)

    def test_weather_request_is_not_swallowed_as_task_title(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("météo à Toulon")
        self.assertFalse(result.handled)
        self.assertFalse(ctx.active)

    def test_explicit_local_intent_wins_and_clears_slot(self):
        ctx = LocalActionContext(ttl_seconds=120)
        ctx.open_task_title()
        result = ctx.resolve("liste mes tâches", explicit_intent="LIST_TASKS")
        self.assertFalse(result.handled)
        self.assertFalse(ctx.active)

    def test_slot_expires(self):
        now = [100.0]
        ctx = LocalActionContext(clock=lambda: now[0], ttl_seconds=10)
        ctx.open_task_title()
        now[0] = 111.0
        result = ctx.resolve("préparer le rapport")
        self.assertFalse(result.handled)
        self.assertFalse(ctx.active)


if __name__ == '__main__':
    unittest.main()
