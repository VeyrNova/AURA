"""Lot-1 validation supervisor. Run with Python -I -S -B.

The foundation itself never spawns a process. This validation tool is allowed
one child interpreter to exercise the CLI in a fresh, audited process. Evidence
is created exclusively (never overwritten) under tests/native/_evidence.
Python audit hooks cover the Python operations exercised, not arbitrary native
code or unrelated OS processes. The foundation only uses the standard library.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/native/_evidence"
STATE = EVIDENCE / "unused-profile"
FORBIDDEN_ROOTS = {
    "PySide6", "PyQt6", "shiboken6", "core", "ui", "runtime", "aura", "accounts",
    "integrations", "voice", "ai", "agent", "memory", "database", "dotenv", "vlc",
}


class AuditGuard:
    def __init__(self, *, harness_scratch_roots=()):
        self.read_count = 0
        self.writes = []
        self.processes = []
        self.violations = []
        self.allowed_writes = set()
        self.allowed_process = None
        self.loaded_libraries = []
        self.pipe_reads = 0
        self.harness_scratch_roots = tuple(Path(path).resolve() for path in harness_scratch_roots)

    def is_harness_scratch(self, value):
        try:
            path = Path(os.fsdecode(value)).resolve()
        except (TypeError, ValueError):
            return False
        return any(path.is_relative_to(root) for root in self.harness_scratch_roots)

    def fail(self, event, detail):
        self.violations.append({"event": event, "detail": str(detail)})
        raise PermissionError("lot-1 validation blocked: " + event)

    def __call__(self, event, args):
        if event == "open":
            name, mode, flags = args
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if isinstance(name, int):
                # subprocess capture opens anonymous read-only pipes before
                # launching the explicitly permitted child. These are not files.
                if self.allowed_process is not None and not writing and stat.S_ISFIFO(os.fstat(name).st_mode):
                    self.pipe_reads += 1
                    return
                self.fail(event, "unexpected file descriptor open")
            path = Path(os.fsdecode(name)).resolve()
            if writing:
                self.writes.append(str(path))
                if path not in self.allowed_writes or not (flags & os.O_EXCL):
                    self.fail(event, path)
            else:
                self.read_count += 1
                if not path.is_relative_to(ROOT):
                    self.fail("read_outside_workspace", path)
                if path.name == ".env" or path.name.startswith(".env."):
                    self.fail("dotenv_read", path)
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "shutil.rmtree"}:
            if not args or not self.is_harness_scratch(args[0]):
                self.fail(event, args[0] if args else "")
        elif event in {
            "os.rename", "os.link", "os.symlink",
            "os.chmod", "os.chown", "os.utime", "os.truncate", "os.chdir", "os.fchdir",
            "shutil.copyfile", "shutil.copymode", "shutil.copystat",
            "os.startfile", "os.startfile/2", "os.system", "os.exec", "os.posix_spawn",
            "sqlite3.connect", "winreg.CreateKey", "winreg.DeleteKey", "winreg.DeleteValue", "winreg.SetValue",
        }:
            self.fail(event, args[0] if args else "")
        elif event.startswith("socket."):
            self.fail(event, "network operations are not allowed")
        elif event == "subprocess.Popen":
            executable, command, cwd, env = args
            if self.allowed_process is None or command != self.allowed_process:
                self.fail(event, "only the declared self-check interpreter is permitted")
            if Path(executable).resolve() != Path(sys.executable).resolve() or Path(cwd).resolve() != ROOT / "tools":
                self.fail(event, "unexpected executable or working directory")
            self.processes.append({"executable": executable, "command": command, "cwd": cwd})
            self.allowed_process = None
        elif event == "ctypes.dlopen":
            self.loaded_libraries.append(str(args[0]))
            self.fail(event, "dynamic libraries are not needed by the foundation")
        elif event == "import":
            name = args[0]
            if name.split(".")[0] in FORBIDDEN_ROOTS or "webengine" in name.lower():
                self.fail(event, name)

    def report(self):
        return {
            "file_reads": self.read_count,
            "supervisor_pipe_reads": self.pipe_reads,
            "file_writes": self.writes,
            "child_processes": self.processes,
            "dynamic_libraries": self.loaded_libraries,
            "violations": self.violations,
            "scope": "Python audit events in supervised parent and child; no OS-wide monitoring",
        }


def check_modules():
    bad = []
    native = []
    modules = []
    for name, module in sorted(sys.modules.items()):
        if module is None:
            continue
        origin = getattr(module, "__file__", None)
        modules.append({"name": name, "origin": origin})
        if name.split(".")[0] in FORBIDDEN_ROOTS or "webengine" in name.lower() or "mainwindow" in name.lower():
            bad.append(name)
        if name == "aura_native" or name.startswith("aura_native."):
            native.append(name)
            if not origin or not Path(origin).resolve().is_relative_to(ROOT / "src/aura_native"):
                bad.append(name)
        if origin and not origin.startswith("<") and not Path(origin).resolve().is_relative_to(ROOT):
            bad.append(name)
    return {"forbidden_or_external": sorted(set(bad)), "native": native, "all": modules}


def child_selfcheck():
    guard = AuditGuard()
    sys.addaudithook(guard)
    # These stdlib imports, all native imports and the CLI execution are audited.
    import contextlib
    import io
    import runpy

    capture = io.StringIO()
    sys.argv = [str(ROOT / "tools/native_core_selfcheck.py"), "--self-check", "--state-dir", str(STATE)]
    rc = 0
    try:
        with contextlib.redirect_stdout(capture):
            runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        rc = int(exc.code or 0)
    body = json.loads(capture.getvalue())
    modules = check_modules()
    ok = rc == 0 and body.get("ok") is True and not guard.violations and not guard.writes and not modules["forbidden_or_external"]
    print(json.dumps({"ok": ok, "exit_code": rc, "selfcheck": body, "imports": modules, "audit": guard.report()}, ensure_ascii=False))
    return 0 if ok else 1


def verify_workspace():
    baseline = json.loads((EVIDENCE / "before.json").read_text(encoding="utf-8"))
    originals = baseline["files"]
    canonical = json.dumps(originals, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != baseline["manifest_sha256"]:
        raise ValueError("baseline manifest integrity failure")
    changed, missing, metadata_changed = [], [], []
    for relative, previous in originals.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        st = path.stat()
        if digest != previous["sha256"] or st.st_size != previous["size"]:
            changed.append(relative)
        if st.st_mtime_ns != previous["mtime_ns"]:
            metadata_changed.append(relative)
    additions = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.relative_to(ROOT).as_posix() not in originals)
    allowed_exact = {"pyproject.toml", ".gitignore", "tools/native_core_selfcheck.py", "docs/migration/lot_01.md"}
    unexpected = [p for p in additions if p not in allowed_exact and not p.startswith(("src/aura_native/", "tests/native/"))]
    return {
        "baseline_manifest_sha256": baseline["manifest_sha256"],
        "original_files": len(originals),
        "changed": changed, "missing": missing, "mtime_changed": metadata_changed,
        "new_files_before_this_report": additions, "unexpected_new_files": unexpected,
        "ok": not (changed or missing or metadata_changed or unexpected),
    }


def main():
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise SystemExit("Run this validator with Python -I -S -B")
    if "--child-selfcheck" in sys.argv:
        return child_selfcheck()
    if "--fingerprints-only" in sys.argv:
        print(json.dumps(verify_workspace(), ensure_ascii=False, indent=2))
        return 0
    scratch_root = EVIDENCE / (".lot1-scratch-" + str(os.getpid()))
    scratch_root.mkdir(parents=False, exist_ok=False)
    os.environ["AURA_LOT1_HARNESS_SCRATCH"] = str(scratch_root)
    guard = AuditGuard(harness_scratch_roots=(scratch_root,))
    sys.addaudithook(guard)
    import io
    import shutil
    import subprocess
    import unittest

    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/native"))
    result_stream = io.StringIO()
    suite = unittest.TestSuite()
    for module_name in ("test_bootstrap", "test_isolation", "test_paths", "test_validate_lot1_guard"):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module_name))
    result = unittest.TextTestRunner(stream=result_stream, verbosity=2).run(suite)
    if "--tests-only" in sys.argv:
        print(result_stream.getvalue())
        shutil.rmtree(scratch_root)
        os.environ.pop("AURA_LOT1_HARNESS_SCRATCH", None)
        return 0 if result.wasSuccessful() else 1
    parent_imports = check_modules()
    command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "--child-selfcheck"]
    guard.allowed_process = subprocess.list2cmdline(command) if os.name == "nt" else command
    child = subprocess.run(command, executable=sys.executable, cwd=str(ROOT / "tools"), capture_output=True, text=True, encoding="utf-8", timeout=30)
    child_body = json.loads(child.stdout) if child.stdout.strip() else {"ok": False, "stderr": child.stderr}
    fingerprints = verify_workspace()
    ok = result.wasSuccessful() and child.returncode == 0 and child_body.get("ok") and fingerprints["ok"] and not guard.violations and not parent_imports["forbidden_or_external"]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    record_path = EVIDENCE / ("validation_" + stamp + ".json")
    guard.allowed_writes.add(record_path)
    record = {
        "ok": bool(ok), "python": sys.version, "executable": sys.executable,
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site, "no_bytecode": sys.dont_write_bytecode},
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "test_output": result_stream.getvalue(),
        "parent_imports": parent_imports, "child": child_body, "fingerprints": fingerprints,
    }
    # Open before capturing audit.report(), so the evidence write is recorded.
    with record_path.open("x", encoding="utf-8") as handle:
        record["parent_audit"] = guard.report()
        json.dump(record, handle, ensure_ascii=False, indent=2)
    shutil.rmtree(scratch_root)
    os.environ.pop("AURA_LOT1_HARNESS_SCRATCH", None)
    print(result_stream.getvalue())
    print(json.dumps({
        "ok": bool(ok), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "selfcheck_ok": child_body.get("ok"),
        "original_files": fingerprints["original_files"],
        "changed": fingerprints["changed"], "missing": fingerprints["missing"],
        "mtime_changed": fingerprints["mtime_changed"],
        "unexpected_new_files": fingerprints["unexpected_new_files"],
        "native_modules": parent_imports["native"],
        "forbidden_imports": parent_imports["forbidden_or_external"],
        "audit_violations": guard.violations,
        "writes": guard.writes,
        "evidence": str(record_path),
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
