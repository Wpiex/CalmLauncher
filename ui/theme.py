THEME = {"accent": (76, 175, 80), "bg": (52, 52, 56)}
DEFAULT = dict(THEME)
BLUR = {"on": False}

def load(cfg):
    THEME["accent"] = tuple(cfg["accent"])
    THEME["bg"] = tuple(cfg["bg"])
    BLUR["on"] = bool(cfg.get("blur"))

def set_blur(on):
    BLUR["on"] = bool(on)

def window_alpha():
    return 175 if BLUR["on"] else 255

def panel_alpha():
    return 225 if BLUR["on"] else 255

def store(cfg):
    cfg["accent"] = list(THEME["accent"])
    cfg["bg"] = list(THEME["bg"])

def shade(c, d):
    return tuple(max(0, min(255, v + d)) for v in c)

def css(c):
    return f"rgb({c[0]},{c[1]},{c[2]})"

def accent():
    return THEME["accent"]

def bg():
    return THEME["bg"]

def panel():
    return shade(THEME["bg"], 12)

def card():
    return shade(THEME["bg"], 26)

def field():
    return shade(THEME["bg"], -8)

def border():
    return shade(THEME["bg"], 40)