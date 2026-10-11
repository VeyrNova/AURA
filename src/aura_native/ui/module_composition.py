"""One native module bridge graph, shared by production and Qt tests."""
from dataclasses import dataclass
from aura_native.ui.music_bridge import NativeMusicBridge
from aura_native.ui.qt_bridge import NativeDiagnosticsBridge
from aura_native.weather.qt_bridge import NativeWeatherBridge


@dataclass
class NativeModuleComposition:
    music_bridge: NativeMusicBridge
    weather_bridge: NativeWeatherBridge
    diagnostics_bridge: NativeDiagnosticsBridge

    @classmethod
    def build(cls, runtime, parent=None, *, file_picker=None):
        return cls(NativeMusicBridge(parent, file_picker=file_picker),
                   NativeWeatherBridge(runtime.weather_service, parent, map_service=getattr(runtime, 'maps_service', None)),
                   NativeDiagnosticsBridge(parent, runtime.diagnostics_service))

    def install_context(self, context):
        context.setContextProperty("musicBridge", self.music_bridge)
        context.setContextProperty("musicPlaylistModel", self.music_bridge.model)
        context.setContextProperty("musicLibraryModel", self.music_bridge.libraryModel)
        context.setContextProperty("weatherBridge", self.weather_bridge)
        context.setContextProperty("diagnosticsBridge", self.diagnostics_bridge)
