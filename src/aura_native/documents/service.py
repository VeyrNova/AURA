from __future__ import annotations

from .filesystem import FileSystemError


class DocumentsError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None: super().__init__(message or code); self.code=code


class DocumentsService:
    def __init__(self, repository): self.repository=repository
    def _call(self, name, *args, **kwargs):
        try: return getattr(self.repository,name)(*args,**kwargs)
        except FileSystemError as exc: raise DocumentsError(exc.code) from exc
        except PermissionError as exc: raise DocumentsError("PERMISSION_DENIED") from exc
        except OSError as exc: raise DocumentsError("IO_ERROR") from exc
    def ensure_root(self): return self._call("ensure_root")
    def list_directory(self,path=""): return self._call("list_directory",path)
    def search(self,query,**kwargs): return self._call("search",query,**kwargs)
    def read_text(self,path): return self._call("read_text",path)
    def create_folder(self,parent,name): return self._call("create_folder",parent,name)
    def create_text(self,parent,name,content="",**kwargs): return self._call("create_text",parent,name,content,**kwargs)
    def save_text(self,path,content,fingerprint,**kwargs): return self._call("save_text",path,content,fingerprint,**kwargs)
    def move(self,source,destination,**kwargs): return self._call("move",source,destination,**kwargs)
    def delete(self,path,**kwargs): return self._call("delete",path,**kwargs)
