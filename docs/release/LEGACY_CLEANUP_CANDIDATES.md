# Legacy cleanup candidates

| Path | Reason | Runtime referenced | Safe to remove later |
|---|---|---:|---:|
| `app/main.py` compatibility bridge classes | historical HTTP/Chromium/music fallback | legacy mode only | No, until legacy mode retirement decision |
| `app/main.py.*.bak` | historical snapshots | No | Yes, after archive policy approval |
| `app/qml/**/*.bak` | historical QML snapshots | No | Yes, after archive policy approval |
| `tools/aura_poc6b_headless_core_host.py*` | historical audit hosts | No native startup reference | Yes, after evidence retention decision |
| root `*.bat` POC launchers | old diagnostics and builds | No native startup reference | Review individually |

No candidate was deleted in this macro-lot.
