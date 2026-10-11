from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aura-native-foundation")
except PackageNotFoundError:
    __version__ = "0.1.0"
APP_NAME = "AURA"
APP_ID = "com.aura.native"
APP_USER_MODEL_ID = "AURA.Native"
