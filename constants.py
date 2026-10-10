import os

APP_NAME = "Calm Launcher"
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "CalmLauncher")
INSTANCES = os.path.join(ROOT, "Instances")
CFG = os.path.join(ROOT, "config.json")
AGENT = os.path.join(ROOT, "authlib-injector.jar")
FONT = os.path.join(BASE, "assets", "Font.ttf")
CLICK = os.path.join(BASE, "assets", "click.ogg")
SLIDER = os.path.join(BASE, "assets", "slider.ogg")
ICON = os.path.join(BASE, "assets", "icon.png")
COMPLETED = os.path.join(BASE, "assets", "completed.ogg")
ERROR = os.path.join(BASE, "assets", "error.ogg")
WINDOW_NOTCH = 8
ELY = "https://authserver.ely.by/auth"
ELY_AGENT = "https://authserver.ely.by/api/authlib-injector"
GREEN = (76, 175, 80)
RED = (200, 60, 60)
GRAY = (90, 90, 90)

os.makedirs(INSTANCES, exist_ok=True)