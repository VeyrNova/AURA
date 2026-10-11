import unittest
import threading
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Event, Command
from aura_native.core.errors import BusCapacityError, BusClosedError

class BusTests(unittest.TestCase):
    def test_fifo_unsubscribe_and_failure_isolation(self):
        bus=LocalBus(); received=[]
        token=bus.subscribe(lambda e: received.append(e.sequence))
        bus.subscribe(lambda e: (_ for _ in ()).throw(ValueError("expected")))
        bus.publish(Event(name="a")); bus.publish(Event(name="a")); failures=bus.drain()
        self.assertEqual(received,[1,2]); self.assertEqual(len(failures),2)
        bus.unsubscribe(token); bus.publish(Event(name="a")); bus.drain(); self.assertEqual(received,[1,2])
    def test_dedup_capacity_close_and_cancel(self):
        bus=LocalBus(capacity=1); event=Event(name="a"); bus.publish(event); bus.publish(event)
        with self.assertRaises(BusCapacityError): bus.publish(Event(name="a"))
        bus.drain(); self.assertTrue(bus.cancel("c")); result=bus.submit(Command(name="x",correlation_id="c")); self.assertEqual(result.status,"cancelled")
        bus.close()
        with self.assertRaises(BusClosedError): bus.publish(Event(name="a"))
    def test_reentrant_publish_keeps_fifo(self):
        bus=LocalBus(); seen=[]
        def callback(e):
            seen.append(e.name)
            if e.name=="one":bus.publish(Event(name="two"))
        bus.subscribe(callback); bus.publish(Event(name="one")); bus.drain(); self.assertEqual(seen,["one","two"])
    def test_unsubscribe_during_delivery_and_no_callback_after_close(self):
        bus=LocalBus(); received=[]; holder={}
        def first(event): received.append("first"); bus.unsubscribe(holder["second"])
        bus.subscribe(first); holder["second"]=bus.subscribe(lambda event: received.append("second"))
        bus.publish(Event(name="x")); bus.drain(); self.assertEqual(received,["first","second"])
        bus.close(); bus.drain(); self.assertEqual(received,["first","second"])
    def test_concurrent_publish_is_sequenced(self):
        bus=LocalBus(capacity=64); events=[]; bus.subscribe(lambda event: events.append(event.sequence))
        workers=[threading.Thread(target=lambda: bus.publish(Event(name="x"))) for _ in range(20)]
        [worker.start() for worker in workers]; [worker.join() for worker in workers]; bus.drain()
        self.assertEqual(events,list(range(1,21)))
    def test_duplicate_command_and_cooperative_cancellation(self):
        bus=LocalBus(); observed=[]
        def handler(command, token):
            bus.cancel(command.correlation_id); observed.append(token.cancelled)
            return CommandResult(command.command_id,not token.cancelled,"ok",correlation_id=command.correlation_id,session_id=command.session_id)
        from aura_native.core.contracts import CommandResult
        bus.register_handler("test",handler); command=Command(command_id="one",name="test",correlation_id="corr")
        first=bus.submit(command); duplicate=bus.submit(Command(command_id="one",name="test",correlation_id="corr")); self.assertIs(first,duplicate)
        bus.drain(); self.assertEqual(observed,[True])
        again=bus.submit(Command(command_id="different",name="test",correlation_id="corr")); self.assertEqual(again.status,"cancelled")
    def test_contract_metadata_and_deep_payload_are_immutable(self):
        event=Event(name="x",source="worker",payload={"nested":[{"value":1}]})
        self.assertTrue(event.session_id); self.assertEqual(event.source,"worker"); self.assertIsNotNone(event.timestamp_utc.tzinfo)
        with self.assertRaises(TypeError): event.payload["x"]=1
        with self.assertRaises(TypeError): event.payload["nested"][0]["value"]=2
