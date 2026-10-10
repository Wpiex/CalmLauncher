import requests

HEADERS = {"User-Agent": "CalmLauncher/1.0"}
MC = "https://api.minecraftservices.com/minecraft/profile"

def auth(token):
    return {**HEADERS, "Authorization": f"Bearer {token}"}

def check(r):
    if r.status_code == 401:
        raise RuntimeError("Session expired")
    if not r.ok:
        raise RuntimeError(r.text[:200] or f"HTTP {r.status_code}")

def download(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.content

def ely_skin(name):
    r = requests.get(f"https://skinsystem.ely.by/textures/{name}", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        raise RuntimeError("Skin not found on Ely.by")
    skin = r.json().get("SKIN")
    if not skin:
        raise RuntimeError("Skin not found on Ely.by")
    slim = skin.get("metadata", {}).get("model") == "slim"
    return download(skin["url"]), slim

def ms_skin(token):
    r = requests.get(MC, headers=auth(token), timeout=15)
    check(r)
    items = r.json().get("skins", [])
    skin = next((s for s in items if s.get("state") == "ACTIVE"), items[0] if items else None)
    if not skin:
        raise RuntimeError("No skin")
    return download(skin["url"]), skin.get("variant") == "SLIM"

def ms_upload(token, data, slim):
    r = requests.post(f"{MC}/skins", headers=auth(token),
                      data={"variant": "slim" if slim else "classic"},
                      files={"file": ("skin.png", data, "image/png")}, timeout=30)
    check(r)

def ms_reset(token):
    r = requests.delete(f"{MC}/skins/active", headers=auth(token), timeout=15)
    check(r)
