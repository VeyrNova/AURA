
from __future__ import annotations
from pathlib import Path
import ast,re

IMPORT="from ui.developer_mode_web_surface import open_web_developer_workspace\n"

def _method_span(source,name):
    pattern=re.compile(rf"(?m)^    def {re.escape(name)}\([^\n]*\)(?:[ \t]*->[ \t]*[^:\n]+)?:[ \t]*\n")
    m=pattern.search(source)
    if not m: raise RuntimeError("method not found: "+name)
    nxt=re.search(r"(?m)^    (?:def |async def |@)",source[m.end():])
    end=m.end()+nxt.start() if nxt else len(source)
    return m.start(),end,source[m.start():end]

def patch_main(path: Path):
    source=path.read_text(encoding="utf-8-sig",errors="strict")
    original=source
    ast.parse(source)

    if IMPORT.strip() not in source:
        imports=[n for n in ast.parse(source).body if isinstance(n,(ast.Import,ast.ImportFrom))]
        if not imports: raise RuntimeError("top-level imports missing")
        last=max(imports,key=lambda n:getattr(n,"end_lineno",n.lineno))
        lines=source.splitlines(keepends=True)
        idx=getattr(last,"end_lineno",last.lineno)
        lines[idx:idx]=["\n",IMPORT,"\n"]
        source="".join(lines)

    start,end,method=_method_span(source,"_handle_developer_mode_command_live")
    if "open_web_developer_workspace(self)" not in method:
        anchor='        if result.get("open_workspace"):\n'
        if anchor not in method:
            raise RuntimeError("Developer Workspace branch missing")
        web_block=(
            '        _aura_dev_web_workspace_opened = False\n'
            '        if result.get("open_workspace"):\n'
            '            try:\n'
            '                _aura_dev_web_result = open_web_developer_workspace(self)\n'
            '                _aura_dev_web_workspace_opened = bool(_aura_dev_web_result.get("opened"))\n'
            '            except Exception:\n'
            '                logger.debug("AURA Web Developer Workspace open failed", exc_info=True)\n'
        )
        method=method.replace(anchor,web_block+'        if result.get("open_workspace") and not _aura_dev_web_workspace_opened:\n',1)
        source=source[:start]+method.rstrip("\n")+"\n\n"+source[end:].lstrip("\n")

    ast.parse(source)
    if source!=original:
        path.write_text(source,encoding="utf-8",newline="\n")
    return {"changed":source!=original,"web_workspace_binding":True}
