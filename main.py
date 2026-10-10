import os
import sys

try:
    _err = os.dup(2)
    sys.stderr = os.fdopen(_err, "w")
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
except OSError:
    pass

os.environ["QT_LOGGING_RULES"] = "qt.multimedia.*=false"
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from constants import FONT, APP_NAME
from ui.window import Window

if __name__ == "__main__":
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