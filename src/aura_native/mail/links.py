GMAIL_HOME = "https://mail.google.com/"
TASKS_HOME = "https://tasks.google.com/"

def _safe(value):
    raw = str(value).encode("utf-8")
    return "".join(chr(b) if (48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122 or b in b"-._~") else "%%%02X" % b for b in raw)

def gmail_url(thread_id="", message_id=""):
    value = str(thread_id or message_id or "").strip()
    return GMAIL_HOME + ("#all/" + _safe(value) if value else "")

def tasks_url(): return TASKS_HOME
