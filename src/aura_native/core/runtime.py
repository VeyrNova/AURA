"""A lifecycle with no implicit historical services, I/O or global singleton."""

from collections.abc import Callable, Iterable

from aura_native.config.paths import RuntimePaths
from aura_native.config.settings import Settings
from aura_native.core.contracts import Capability, CapabilityState, RuntimeState
from aura_native.core.bus import LocalBus
from enum import Enum


class BackgroundLifecycle(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"


class NativeRuntime:
    def __init__(
        self,
        settings: Settings,
        paths: RuntimePaths,
        bus: LocalBus | None = None,
        *,
        bus_binders: Iterable[Callable[[LocalBus], None]] = (),
        service_stoppers: Iterable[Callable[[], None]] = (),
        available_capabilities: Iterable[str] = (),
    ) -> None:
        self.settings = settings
        self.paths = paths
        self._state = RuntimeState.CREATED
        self._transitions = [RuntimeState.CREATED]
        self._bus_binders = tuple(bus_binders)
        self._service_stoppers = tuple(service_stoppers)
        self._available_capabilities = frozenset(str(name) for name in available_capabilities)
        self.bus = bus if bus is not None else LocalBus()
        self._background_state = BackgroundLifecycle.STOPPED
        self._bind_bus()

    def _bind_bus(self) -> None:
        for binder in self._bus_binders:
            binder(self.bus)

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def transitions(self) -> tuple[RuntimeState, ...]:
        return tuple(self._transitions)

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        names = (
            "ui", "event_bus", "storage", "memory", "productivity", "google",
            "conversation", "agent", "inference", "security_actions", "music", "voice",
            "documents", "weather", "tools", "diagnostics",
        )
        out = [Capability("foundation", CapabilityState.AVAILABLE, "native lifecycle")]
        for name in names:
            if name in self._available_capabilities:
                out.append(Capability(name, CapabilityState.AVAILABLE, "native lot 3A"))
            else:
                out.append(Capability(name, CapabilityState.NOT_MIGRATED, "not connected yet"))
        return tuple(out)

    def start(self) -> None:
        if self._state is RuntimeState.STOPPED:
            self.bus = LocalBus()
            self._bind_bus()
        if self._state is not RuntimeState.RUNNING:
            self._state = RuntimeState.RUNNING
            self._transitions.append(self._state)

    @property
    def background_state(self) -> BackgroundLifecycle:
        return self._background_state

    def start_background(self) -> bool:
        if self._state is not RuntimeState.RUNNING or self._background_state is BackgroundLifecycle.RUNNING:
            return False
        self._background_state = BackgroundLifecycle.RUNNING
        scheduler = getattr(self, "reminder_scheduler", None)
        if scheduler is not None:
            scheduler.start()
        return True

    def stop_background(self) -> bool:
        if self._background_state is BackgroundLifecycle.STOPPED:
            return False
        self._background_state = BackgroundLifecycle.STOPPING
        scheduler = getattr(self, "reminder_scheduler", None)
        if scheduler is not None:
            scheduler.stop()
        self._background_state = BackgroundLifecycle.STOPPED
        return True

    def stop(self) -> None:
        if self._state is not RuntimeState.STOPPED:
            self.stop_background()
            self.bus.close()
            for stopper in self._service_stoppers:
                stopper()
            self._state = RuntimeState.STOPPED
            self._transitions.append(self._state)
