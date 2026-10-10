import json
import uuid
from constants import CFG

def load_cfg():
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, json.JSONDecodeError):
        c = {}

    c.setdefault("memory", 4096)
    c.setdefault("lang", "en")
    c.setdefault("blur", False)
    c.setdefault("java_path", "")
    c.setdefault("java_args", "")
    c.setdefault("version", None)
    c.setdefault("loader", "vanilla")
    c.setdefault("startup", False)
    c.setdefault("close_on_launch", False)
    c.setdefault("reopen", True)
    c.setdefault("tray", True)
    c.setdefault("optimized", False)
    c.setdefault("accent", [76, 175, 80])
    c.setdefault("bg", [52, 52, 56])
    c.setdefault("client_token", uuid.uuid4().hex)
    c.setdefault("account", None)
    c.setdefault("skin_model", "classic")
    c.setdefault("skin_url", None)
    return c

def save_cfg(c):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)