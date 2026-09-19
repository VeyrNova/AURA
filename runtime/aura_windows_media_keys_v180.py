from __future__ import annotations
import ctypes
import os

VK = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_mute": 0xAD,
    "volume_down": 0xAE,
    "volume_up": 0xAF,
}
KEYEVENTF_KEYUP = 0x0002

def send_media_key(action: str):
    action = str(action or "").strip().casefold()
    if action not in VK:
        raise ValueError("unsupported media key: " + action)
    test_mode = str(os.environ.get("AURA_M180_MEDIA_KEY_TEST_MODE") or "").strip().casefold() in {"1","true","yes"}
    if not test_mode:
        user32 = ctypes.windll.user32
        code = VK[action]
        user32.keybd_event(code, 0, 0, 0)
        user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
    return {
        "schema": "aura.windows-media-key.v180",
        "action": action,
        "sent": True,
        "test_mode": test_mode,
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }
