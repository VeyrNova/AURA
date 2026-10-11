"""Diagnostics orchestration with an optional psutil collector."""
from __future__ import annotations
import time
from pathlib import Path

class DiagnosticsService:
    def __init__(self, psutil_module=None, *, clock=time.monotonic):
        if psutil_module is None:
            try:
                import psutil as psutil_module
            except ModuleNotFoundError:
                psutil_module = None
        self.psutil = psutil_module
        self.clock = clock
        self._network_sample = None

    def refresh(self):
        if self.psutil is None:
            return {
                'ready': False, 'cpu': 0.0, 'ram': 0.0, 'disk': 0.0,
                'cpuText': 'UNAVAILABLE', 'ramText': 'UNAVAILABLE',
                'diskText': 'UNAVAILABLE', 'temp': 0.0,
                'tempText': 'UNAVAILABLE', 'vram': 0.0,
                'vramText': 'UNAVAILABLE', 'downloadText': 'UNAVAILABLE',
                'uploadText': 'UNAVAILABLE',
            }
        p = self.psutil
        cpu = float(p.cpu_percent(interval=None))
        memory = p.virtual_memory()
        disk = p.disk_usage(str(Path.home().anchor or Path.home()))
        result = {
            'ready': True, 'cpu': cpu, 'ram': float(memory.percent),
            'disk': float(disk.percent), 'cpuText': f'{cpu:.0f}%',
            'ramText': f'{memory.used / 1073741824:.1f} / {memory.total / 1073741824:.1f} Gio',
            'diskText': f'{disk.used / 1000000000:.0f} / {disk.total / 1000000000:.0f} GB',
            'temp': 0.0, 'tempText': 'UNSUPPORTED',
            'vram': 0.0, 'vramText': 'UNSUPPORTED',
            'downloadText': 'Collecte…', 'uploadText': 'Collecte…',
        }
        counters = p.net_io_counters()
        now = self.clock()
        if counters is not None and self._network_sample is not None:
            previous_at, received, sent = self._network_sample
            elapsed = max(0.001, now - previous_at)
            result['downloadText'] = f'{max(0, counters.bytes_recv - received) * 8 / elapsed / 1000000:.1f} Mbps'
            result['uploadText'] = f'{max(0, counters.bytes_sent - sent) * 8 / elapsed / 1000000:.1f} Mbps'
        if counters is not None:
            self._network_sample = (now, counters.bytes_recv, counters.bytes_sent)
        else:
            result['downloadText'] = result['uploadText'] = 'UNAVAILABLE'
        return result
