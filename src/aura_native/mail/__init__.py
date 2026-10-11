from .service import MailService, FakeMailBackend
def __getattr__(name):
    if name == "NativeMailBridge":
        from .qt_bridge import NativeMailBridge
        return NativeMailBridge
    raise AttributeError(name)

__all__ = ["NativeMailBridge"]
