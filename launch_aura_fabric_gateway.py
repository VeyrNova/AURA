from pathlib import Path
import os
import sys

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_fabric_http_gateway import serve_forever

if __name__ == "__main__":
    serve_forever()
