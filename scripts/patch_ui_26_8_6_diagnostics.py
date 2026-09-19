from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
checks=[]
def check(name, ok):
    checks.append((name,bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
llm=(root/'ai'/'llm_manager.py').read_text(encoding='utf-8')
chat=(root/'ui'/'chat_panel.py').read_text(encoding='utf-8')
res=(root/'ui'/'holographic_results_panel.py').read_text(encoding='utf-8')
tri=(root/'ui'/'text_rendering.py').read_text(encoding='utf-8')
check('UTF-8 stream decoder present', '_decode_utf8_stream_line' in llm)
check('3 streaming providers use byte mode', llm.count('iter_lines(decode_unicode=False)') >= 3)
check('legacy unicode streaming disabled', 'iter_lines(decode_unicode=True):' not in llm)
check('Unicode repair layer present', 'repair_mojibake' in tri)
check('NFC normalization present', 'unicodedata.normalize("NFC"' in tri)
check('Result overlay renders Markdown', 'setMarkdown(clean_text)' in res)
check('Result overlay has Unicode font fallback', 'Segoe UI Emoji' in res)
check('Conversation result parses Markdown', 'markdown_doc.setMarkdown(markdown_text)' in chat)
check('Conversation normalization uses shared layer', 'return normalize_plain_text(text)' in chat)
print(f"\n{sum(ok for _,ok in checks)}/{len(checks)} checks PASS")
sys.exit(0 if all(ok for _,ok in checks) else 1)
