import json
import os
import sys

STATE = {"data": None}


def tokens_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "tokens.json")


def load():
    try:
        with open(tokens_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(name):
    if STATE["data"] is None:
        STATE["data"] = load()
    return str(STATE["data"].get(name) or "").strip()
