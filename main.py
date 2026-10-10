import os
import re
import sys

try:
    _err = os.dup(2)
    sys.stderr = os.fdopen(_err, "w")
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
except OSError:
    pass

SECRET = "983522e476169b82209c783aaf6cb8ecd1be275e83f82ea9"

TOKENS = {
    "microsoft": "",
    "curseforge": "",
}

def make_tokens():
    from core import vault

    data = {key: value.strip() for key, value in TOKENS.items() if value.strip()}
    if not data:
        print("Paste your tokens into TOKENS in main.py first.")
        return 1
    path = vault.write(data, SECRET)
    source_path = os.path.abspath(__file__)
    with open(source_path, "r", encoding="utf-8") as file:
        source = file.read()
    head, marker, tail = source.partition("TOKENS = {")
    block, end, rest = tail.partition("\n}")
    block = re.sub(r'("(?:microsoft|curseforge)":\s*)"[^"\n]*"', r'\1""', block)
    with open(source_path, "w", encoding="utf-8") as file:
        file.write(head + marker + block + end + rest)
    print(f"Created {path}. The tokens were removed from main.py.")
    return 0


if "--make-tokens" in sys.argv:
    sys.exit(make_tokens())

os.environ["QT_LOGGING_RULES"] = "qt.multimedia.*=false"
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from constants import FONT, APP_NAME
from core import vault
from ui.window import Window

if __name__ == "__main__":
    vault.configure(SECRET)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if os.path.exists(FONT):
        fid = QFontDatabase.addApplicationFont(FONT)
        if fid >= 0:
            app.setFont(QFont(QFontDatabase.applicationFontFamilies(fid)[0], 11))
    w = Window()
    if "--hidden" not in sys.argv:
        w.show()
    sys.exit(app.exec())
