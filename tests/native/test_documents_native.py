from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

from aura_native.documents.filesystem import FileSystemError, FileSystemRepository, MAX_TEXT_READ_BYTES
from aura_native.documents.qt_bridge import NativeDocumentsBridge
from aura_native.documents.service import DocumentsError, DocumentsService

ROOT=Path(__file__).parents[2]


class DocumentsSandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/"tests/native/_evidence")
        self.root=Path(self.tmp.name)/"documents"; self.repo=FileSystemRepository(self.root); self.service=DocumentsService(self.repo); self.service.ensure_root()
    def tearDown(self): self.tmp.cleanup()
    def code(self,fn,*args,**kwargs):
        with self.assertRaises(DocumentsError) as caught: fn(*args,**kwargs)
        return caught.exception.code

    def test_list_empty_files_folders_and_sorting(self):
        self.service.create_text("","z.txt",""); self.service.create_folder("","Beta"); self.service.create_folder("","alpha"); self.service.create_text("","A.md","")
        rows=self.service.list_directory("")
        self.assertEqual([(x.kind,x.name) for x in rows],[('folder','alpha'),('folder','Beta'),('file','A.md'),('file','z.txt')])
        self.assertTrue(all(x.modified_at and isinstance(x.readable,bool) and isinstance(x.writable,bool) for x in rows))

    def test_list_missing_and_permission(self):
        self.assertEqual(self.code(self.service.list_directory,"missing"),"NOT_FOUND")
        with patch.object(Path,"iterdir",side_effect=PermissionError): self.assertEqual(self.code(self.service.list_directory,""),"PERMISSION_DENIED")

    def test_search_name_extension_zero_limit_and_depth(self):
        self.service.create_folder("","a"); self.service.create_text("a","report.md","needle in content")
        self.service.create_text("","other.txt","report only in content")
        self.assertEqual([x.name for x in self.service.search("report")],["report.md"])
        self.assertEqual([x.name for x in self.service.search(".md")],["report.md"])
        self.assertEqual(self.service.search("absent"),())
        self.assertEqual(len(self.service.search(".",limit=1)),1)

    def test_search_cancellation(self):
        self.service.create_text("","a.txt",""); self.assertEqual(self.service.search("a",cancelled=lambda:True),())

    def test_read_utf8_bom_empty_large_binary_missing_outside(self):
        (self.root/"bom.txt").write_bytes(b"\xef\xbb\xbfbonjour"); (self.root/"empty.txt").write_bytes(b"")
        self.assertEqual(self.service.read_text("bom.txt").content,"bonjour"); self.assertEqual(self.service.read_text("empty.txt").content,"")
        (self.root/"large.txt").write_bytes(b"x"*(MAX_TEXT_READ_BYTES+1)); self.assertEqual(self.code(self.service.read_text,"large.txt"),"FILE_TOO_LARGE")
        (self.root/"image.png").write_bytes(b"\x89PNG\x00"); self.assertEqual(self.code(self.service.read_text,"image.png"),"UNSUPPORTED_BINARY")
        self.assertEqual(self.code(self.service.read_text,"missing.txt"),"NOT_FOUND"); self.assertEqual(self.code(self.service.read_text,"../secret.txt"),"OUTSIDE_ALLOWED_ROOT")

    def test_create_file_folder_duplicate_invalid_and_traversal(self):
        self.service.create_folder("","Folder"); self.service.create_text("Folder","note.txt","hello")
        self.assertEqual((self.root/"Folder/note.txt").read_text(),"hello")
        self.assertEqual(self.code(self.service.create_text,"Folder","note.txt","x"),"OVERWRITE_REQUIRED")
        for name in ("", "CON", "bad:name", ".."):
            self.assertEqual(self.code(self.service.create_text,"",name,"x"),"INVALID_NAME")
        self.assertEqual(self.code(self.service.create_text,"..","x.txt","x"),"OUTSIDE_ALLOWED_ROOT")

    def test_save_atomic_and_external_change(self):
        self.service.create_text("","note.txt","old"); opened=self.service.read_text("note.txt")
        saved=self.service.save_text("note.txt","new",opened.fingerprint); self.assertEqual(saved.content,"new")
        (self.root/"note.txt").write_text("external")
        self.assertEqual(self.code(self.service.save_text,"note.txt","mine",saved.fingerprint),"EXTERNAL_CHANGE")
        self.assertEqual((self.root/"note.txt").read_text(),"external")

    def test_atomic_failure_leaves_original(self):
        self.service.create_text("","note.txt","original"); doc=self.service.read_text("note.txt")
        with patch("aura_native.documents.filesystem.os.replace",side_effect=OSError("fail")):
            self.assertEqual(self.code(self.service.save_text,"note.txt","broken",doc.fingerprint),"IO_ERROR")
        self.assertEqual((self.root/"note.txt").read_text(),"original")

    def test_move_rename_folder_collision_outside_and_descendant(self):
        self.service.create_text("","a.txt","a"); self.service.move("a.txt","b.txt"); self.assertTrue((self.root/"b.txt").is_file())
        self.service.create_folder("","folder"); self.service.create_text("folder","x.txt","x"); self.service.move("folder","renamed"); self.assertTrue((self.root/"renamed/x.txt").is_file())
        self.service.create_text("","collision.txt","c"); self.assertEqual(self.code(self.service.move,"b.txt","collision.txt"),"OVERWRITE_REQUIRED")
        self.assertEqual(self.code(self.service.move,"b.txt","../outside.txt"),"OUTSIDE_ALLOWED_ROOT")
        self.assertEqual(self.code(self.service.move,"renamed","renamed/child"),"INVALID_PATH")

    def test_delete_requires_confirmation_and_nonempty_strengthening(self):
        self.service.create_text("","a.txt","x"); self.assertEqual(self.code(self.service.delete,"a.txt"),"CONFIRMATION_REQUIRED")
        self.service.delete("a.txt",confirmed=True); self.assertFalse((self.root/"a.txt").exists())
        self.service.create_folder("","empty"); self.service.delete("empty",confirmed=True); self.assertFalse((self.root/"empty").exists())
        self.service.create_folder("","full"); self.service.create_text("full","x.txt","x")
        self.assertEqual(self.code(self.service.delete,"full",confirmed=True),"NON_EMPTY_CONFIRMATION_REQUIRED")
        self.service.delete("full",confirmed=True,recursive_confirmed=True); self.assertFalse((self.root/"full").exists())

    def test_absolute_unc_mixed_and_case_escape(self):
        for value in (str(Path("C:/Windows/System32")),r"\\server\share\x",r"a\..\..\secret",r"../config/credentials",r"../data/aura_native.db"):
            self.assertEqual(self.code(self.service.read_text,value),"OUTSIDE_ALLOWED_ROOT")

    def test_symlink_escape_is_denied(self):
        outside=Path(self.tmp.name)/"outside"; outside.mkdir(); (outside/"secret.txt").write_text("secret")
        link=self.root/"link"
        try: link.symlink_to(outside,target_is_directory=True)
        except OSError: self.skipTest("symlink creation is unavailable")
        self.assertEqual(self.code(self.service.read_text,"link/secret.txt"),"OUTSIDE_ALLOWED_ROOT")

    def test_reparse_guard_is_enforced(self):
        self.service.create_folder("","link")
        with patch.object(self.repo,"_is_reparse",side_effect=lambda p:p.name=="link"):
            self.assertEqual(self.code(self.service.list_directory,"link"),"OUTSIDE_ALLOWED_ROOT")


class DocumentsBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/"tests/native/_evidence"); self.root=Path(self.tmp.name)/"docs"; self.service=DocumentsService(FileSystemRepository(self.root)); self.service.ensure_root(); self.bridge=NativeDocumentsBridge(self.service)
    def tearDown(self): self.tmp.cleanup()
    def wait(self):
        until=time.time()+2
        while self.bridge.state=="loading" and time.time()<until:self.app.processEvents();time.sleep(.005)
        self.app.processEvents()
    def test_list_and_stale_search(self):
        self.service.create_text("","one.txt","1"); self.bridge.listDirectory(""); self.wait(); self.assertEqual(len(self.bridge.items),1)
        self.bridge._generation=3; self.bridge._apply_loaded([{"name":"stale"}],"","search",2); self.assertEqual(self.bridge.items[0]["name"],"one.txt")
    def test_delete_flow_has_no_mutation_before_confirm(self):
        self.service.create_text("","one.txt","1"); self.bridge.requestDelete("one.txt","one.txt",False); self.assertTrue((self.root/"one.txt").exists()); self.assertTrue(self.bridge.confirmDelete(False)); self.wait(); self.assertFalse((self.root/"one.txt").exists())
    def test_external_open_validates_containment(self):
        self.service.create_text("","one.txt","1"); opened=[]; bridge=NativeDocumentsBridge(self.service,opener=lambda url:opened.append(url.toLocalFile()) or True)
        self.assertTrue(bridge.openExternal("one.txt")); self.assertFalse(bridge.openExternal("../secret")); self.assertEqual([Path(x).resolve() for x in opened],[(self.root/"one.txt").resolve()])


class DocumentsQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
    def test_view_sizes_and_routing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tests/native/_evidence") as temp:
            bridge=NativeDocumentsBridge(DocumentsService(FileSystemRepository(Path(temp)/"docs")))
            for width,height in ((1100,700),(1280,720),(1440,900),(1920,1080)):
                view=QQuickView();warnings=[];view.engine().warnings.connect(lambda values:warnings.extend(x.toString() for x in values));view.rootContext().setContextProperty("documentsBridge",bridge);view.resize(QSize(width,height));view.setSource(QUrl.fromLocalFile(str(ROOT/"app/qml/views/DocumentsView.qml")))
                try:self.assertEqual(view.status(),QQuickView.Ready,warnings);self.assertFalse(any("ReferenceError" in x or "TypeError" in x for x in warnings),warnings)
                finally:view.setSource(QUrl())
        modules=(ROOT/"app/qml/views/ModulesView.qml").read_text(encoding="utf-8");subdock=(ROOT/"app/qml/components/ModulesSubdock.qml").read_text(encoding="utf-8")
        self.assertNotIn('openConversationPrefill("liste mes fichiers")',modules);self.assertNotIn('prefillRequested("liste mes fichiers")',subdock)
        self.assertIn('navigateRequested("documents")',modules);self.assertIn('navigateRequested("documents")',subdock)


if __name__=='__main__':unittest.main()
