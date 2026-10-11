import tempfile
import unittest
from pathlib import Path

from aura_native.bootstrap.composition import compose_runtime
from aura_native.config.settings import Settings
from aura_native.core.contracts import Command
from aura_native.intents.router import NativeIntentRouter


class MemoryCommands008Tests(unittest.TestCase):
    def test_router_memory_contracts(self):
        router = NativeIntentRouter()
        self.assertEqual(router.parse('Souviens-toi que AURA_TEST_008_MEMORY_X').intent, 'CREATE_MEMORY')
        self.assertEqual(router.parse('affiche ma mémoire').intent, 'LIST_MEMORY')
        self.assertEqual(router.parse('cherche dans ma mémoire AURA_TEST_008').intent, 'SEARCH_MEMORY')
        self.assertEqual(router.parse('oublie AURA_TEST_008_MEMORY_X').intent, 'FORGET_MEMORY')

    def test_create_is_prepared_and_confirm_executes_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = compose_runtime(project_root=Path.cwd(), state_dir=tmp, settings=Settings())
            runtime.start()
            dispatcher = runtime.local_intent_dispatcher
            result = dispatcher.dispatch(NativeIntentRouter().parse('Souviens-toi que AURA_TEST_008_MEMORY_ONCE'))
            self.assertEqual(result.result_type, 'PREPARED_ACTION_CREATED')
            action = runtime.prepared_action_repository.get(result.data['action_id'])
            self.assertEqual(action.state, 'prepared')
            runtime.bus.submit(Command(name='pending_action.confirm', payload={'action_id': action.action_id}))
            runtime.bus.drain()
            self.assertEqual(runtime.prepared_action_repository.get(action.action_id).state, 'prepared')
            runtime._ui_prepared_action_confirmer.confirm(action.action_id)
            self.assertEqual(runtime.prepared_action_repository.get(action.action_id).state, 'executed')
            runtime.stop()


if __name__ == '__main__':
    unittest.main()
