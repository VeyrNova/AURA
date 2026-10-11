import tempfile
import time
import unittest
from pathlib import Path
from aura_native.agent.provider import StreamingFakeProvider
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Command

ROOT=Path(__file__).resolve().parents[2]
class AgentStreamingTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(prefix="aura-stream-");self.runtime=compose_runtime(project_root=ROOT,state_dir=Path(self.tmp.name),provider=StreamingFakeProvider(("Bon","jour","")));self.runtime.start()
    def tearDown(self): self.runtime.stop();self.tmp.cleanup()
    def command(self,n,p=None): return Command(name=n,payload=p or {},session_id="native",source="test")
    def wait(self,items):
        for _ in range(60):
            self.runtime.bus.drain()
            if items:return
            time.sleep(.01)
    def test_chunks_then_single_persisted_assistant(self):
        deltas=[];completed=[];messages=[];self.runtime.bus.subscribe(deltas.append,name="agent.delta");self.runtime.bus.subscribe(completed.append,name="agent.completed");self.runtime.bus.subscribe(messages.append,name="conversation.message_created")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"Salut"}));self.runtime.bus.drain();self.wait(completed)
        self.assertEqual("".join(x.payload["text"] for x in deltas),"Bonjour");self.assertTrue(deltas[-1].payload["done"]);self.assertEqual(deltas[-1].payload["text"],"");self.assertEqual(deltas[-1].payload["accumulated"],"Bonjour");self.assertEqual(completed[-1].payload["message"]["content"],"Bonjour");self.assertEqual([x.payload["message"]["role"] for x in messages],["user","assistant"])
    def test_cancel_drops_late_chunks_and_assistant(self):
        self.runtime.stop();self.runtime=compose_runtime(project_root=ROOT,state_dir=Path(self.tmp.name),provider=StreamingFakeProvider(("a","b","c"),delay=.06));self.runtime.start();created=[];deltas=[];messages=[];self.runtime.bus.subscribe(created.append,name="agent.request_created");self.runtime.bus.subscribe(deltas.append,name="agent.delta");self.runtime.bus.subscribe(messages.append,name="conversation.message_created")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"stop"}));self.runtime.bus.drain();request=created[-1].payload["request"]["request_id"];time.sleep(.07);self.runtime.bus.drain();before=len(deltas);self.runtime.bus.submit(self.command("agent.cancel",{"request_id":request}));self.runtime.bus.drain();time.sleep(.2);self.runtime.bus.drain();self.assertEqual(len(deltas),before);self.assertEqual([x.payload["message"]["role"] for x in messages],["user"])

    def test_ollama_ndjson_final_empty_chunk_and_whitespace_are_valid(self):
        from aura_native.agent.provider import OllamaProvider
        from aura_native.config.agent_provider import AgentProviderSettings
        class Response:
            def __iter__(self): return iter((b'{"model":"qwen3:8b","message":{"content":"1"},"done":false}\n',b'{"model":"qwen3:8b","message":{"content":"  \\n"},"done":false}\n',b'{"model":"qwen3:8b","message":{"content":"2"},"done":false}\n',b'{"model":"qwen3:8b","message":{"content":""},"done":true,"done_reason":"stop"}\n'))
            def __enter__(self): return self
            def __exit__(self,*_): return False
        provider=OllamaProvider(AgentProviderSettings("ollama","qwen3:8b","http://127.0.0.1:11434",1),opener=lambda *_args,**_kwargs:Response())
        chunks=list(provider.generate_stream(({"role":"user","content":"x"},)))
        self.assertEqual("".join(chunk.text for chunk in chunks),"1  \n2")
        self.assertTrue(chunks[-1].done);self.assertEqual(chunks[-1].text,"")

    def test_whitespace_does_not_leave_thinking_before_visible_content(self):
        states=[]; self.runtime.bus.subscribe(states.append,name="agent.state_changed")
        self.runtime.stop();self.runtime=compose_runtime(project_root=ROOT,state_dir=Path(self.tmp.name),provider=StreamingFakeProvider(("  \n","OK",""),delay=.01));self.runtime.start();self.runtime.bus.subscribe(states.append,name="agent.state_changed")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"state"}));self.runtime.bus.drain();self.wait(states)
        for _ in range(50): self.runtime.bus.drain(); time.sleep(.01)
        names=[x.payload.get("request",{}).get("state") for x in states]
        self.assertIn("thinking",names);self.assertIn("responding",names);self.assertLess(names.index("thinking"),names.index("responding"))
