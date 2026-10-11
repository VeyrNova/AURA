from .service import MapsService
def __getattr__(name):
    if name == "NativeMapsBridge":
        from .qt_bridge import NativeMapsBridge
        return NativeMapsBridge
    raise AttributeError(name)

__all__ = ["NativeMapsBridge"]
