"""FIFO local bus. It deliberately contains no Qt, I/O, or workers."""
from __future__ import annotations
from collections import OrderedDict, deque
from dataclasses import replace
from threading import Event as ThreadEvent, RLock
from typing import Callable
from aura_native.core.contracts import Command, CommandError, CommandResult, Event
from aura_native.core.errors import BusCapacityError, BusClosedError, DeliveryFailure

class CancellationToken:
    """Cooperative token passed to command handlers; it never interrupts a thread."""
    def __init__(self): self._event=ThreadEvent()
    @property
    def cancelled(self): return self._event.is_set()
    def _cancel(self): self._event.set()

class Subscription:
    def __init__(self,bus,token): self._bus,self.token=bus,token
    def close(self): self._bus.unsubscribe(self.token)

class LocalBus:
    def __init__(self,*,capacity:int=512,dedupe_limit:int=1024):
        if capacity<1 or dedupe_limit<1: raise ValueError("capacity and dedupe_limit must be positive")
        self._capacity,self._dedupe_limit=capacity,dedupe_limit; self._lock=RLock()
        self._queue=deque(); self._commands=deque(); self._subscriptions={}; self._handlers={}
        self._seen_events=OrderedDict(); self._command_results=OrderedDict(); self._correlations={}; self._tokens={}; self._cancelled_correlations=set()
        self._closed=False; self._sequence=0; self._token=0; self._waker=None
    @property
    def closed(self):
        with self._lock:return self._closed
    def set_waker(self,waker):
        with self._lock:self._waker=waker
    def subscribe(self,callback,*,name=None):
        with self._lock:
            if self._closed: raise BusClosedError("bus is closed")
            self._token+=1; self._subscriptions[self._token]=(name,callback); return Subscription(self,self._token)
    def unsubscribe(self,token):
        token=token.token if isinstance(token,Subscription) else token
        with self._lock:self._subscriptions.pop(token,None)
    def register_handler(self,name,handler):
        with self._lock:
            if self._closed: raise BusClosedError("bus is closed")
            self._handlers[name]=handler
    def publish(self,event):
        with self._lock:
            if self._closed: raise BusClosedError("bus is closed")
            if event.event_id in self._seen_events:return event
            if len(self._queue)+len(self._commands)>=self._capacity:raise BusCapacityError("bus queue is full")
            self._sequence+=1; admitted=replace(event,sequence=self._sequence); self._queue.append(admitted); self._remember(self._seen_events,event.event_id)
            waker=self._waker
        if waker:waker()
        return admitted
    def discard_events(self,predicate):
        """Drop queued events matching a local cancellation boundary."""
        with self._lock:
            kept=deque(event for event in self._queue if not predicate(event))
            removed=len(self._queue)-len(kept); self._queue=kept
            return removed
    def submit(self,command):
        with self._lock:
            if self._closed:raise BusClosedError("bus is closed")
            duplicate=self._command_results.get(command.command_id)
            correlation_command=self._correlations.get(command.correlation_id)
            if duplicate:return duplicate
            if correlation_command:return self._command_results[correlation_command]
            token=CancellationToken(); self._tokens[command.correlation_id]=token; self._correlations[command.correlation_id]=command.command_id
            if command.correlation_id in self._cancelled_correlations:
                token._cancel()
                pending=CommandResult(command.command_id,False,"cancelled",error=CommandError("cancelled","command cancelled"),correlation_id=command.correlation_id,session_id=command.session_id)
                self._remember(self._command_results,command.command_id,pending); waker=self._waker; handler=None
            else:
                handler=self._handlers.get(command.name)
            if handler is not None:
                if len(self._queue)+len(self._commands)>=self._capacity:raise BusCapacityError("bus queue is full")
                pending=CommandResult(command.command_id,False,"queued",correlation_id=command.correlation_id,session_id=command.session_id)
                self._remember(self._command_results,command.command_id,pending); self._commands.append((command,handler,token)); waker=self._waker
            elif command.command_id not in self._command_results:
                pending=CommandResult(command.command_id,False,"not_migrated",error=CommandError("not_migrated",f"{command.name} is not_migrated"),correlation_id=command.correlation_id,session_id=command.session_id)
                self._remember(self._command_results,command.command_id,pending); waker=self._waker
        if handler is None:self._publish_result(command,pending)
        elif waker:waker()
        return pending
    def cancel(self,correlation_id):
        with self._lock:
            if self._closed:return False
            self._cancelled_correlations.add(correlation_id)
            token=self._tokens.get(correlation_id)
            if token is not None:token._cancel()
            return True
    def _publish_result(self,command,result):
        try:self.publish(Event(name="command.result",payload={"command_id":command.command_id,"status":result.status},correlation_id=command.correlation_id,session_id=command.session_id))
        except BusClosedError: pass
    def _remember(self,table,key,value=None):
        table[key]=value
        if len(table)>self._dedupe_limit: table.popitem(last=False)
    def _drain_command(self):
        with self._lock:
            if not self._commands:return None
            return self._commands.popleft()
    def drain(self):
        failures=[]
        while True:
            item=self._drain_command()
            if item is None:break
            command,handler,token=item
            if token.cancelled: result=CommandResult(command.command_id,False,"cancelled",error=CommandError("cancelled","command cancelled"),correlation_id=command.correlation_id,session_id=command.session_id)
            else:
                try: result=handler(command,token)
                except Exception as exc: result=CommandResult(command.command_id,False,"failed",error=CommandError("handler_failed",str(exc)),correlation_id=command.correlation_id,session_id=command.session_id)
                if not isinstance(result,CommandResult): raise TypeError("command handler must return CommandResult")
                if token.cancelled: result=CommandResult(command.command_id,False,"cancelled",error=CommandError("cancelled","command cancelled"),correlation_id=command.correlation_id,session_id=command.session_id)
            with self._lock:self._remember(self._command_results,command.command_id,result)
            self._publish_result(command,result)
        while True:
            with self._lock:
                if self._closed or not self._queue:break
                event=self._queue.popleft(); targets=tuple((token,cb) for token,(name,cb) in self._subscriptions.items() if name is None or name==event.name)
            for token,callback in targets:
                try:callback(event)
                except Exception as exc:failures.append(DeliveryFailure(event.name,token,type(exc).__name__,str(exc)))
        return tuple(failures)
    def close(self):
        with self._lock:
            self._closed=True
            for token in self._tokens.values():token._cancel()
            self._queue.clear();self._commands.clear();self._subscriptions.clear();self._handlers.clear();self._waker=None
