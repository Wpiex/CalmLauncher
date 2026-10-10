import os
import sys
from pathlib import Path

import psutil

try:
    _err = os.dup(2)
    sys.stderr = os.fdopen(_err, "w")
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
except OSError:
    pass

CONTENTS_DIR = "Files"

os.environ["QT_LOGGING_RULES"] = "qt.multimedia.*=false"

from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication

from constants import FONT, APP_NAME
from ui.window import Window


def close_previous_instances():
    current_pid = os.getpid()
    frozen = getattr(sys, "frozen", False)
    target_exe = os.path.normcase(os.path.realpath(sys.executable))
    target_script = os.path.normcase(os.path.realpath(__file__))
    previous = []

    for process in psutil.process_iter(["pid"]):
        try:
            if process.info["pid"] == current_pid:
                continue

            same_instance = False

            if frozen:
                process_exe = process.exe()
                if process_exe:
                    same_instance = (
                        os.path.normcase(os.path.realpath(process_exe))
                        == target_exe
                    )
            else:
                command = process.cmdline()

                if len(command) > 1:
                    process_cwd = process.cwd()

                    for argument in command[1:]:
                        if not argument or argument.startswith("-"):
                            continue

                        candidate = Path(argument)

                        if not candidate.is_absolute():
                            candidate = Path(process_cwd) / candidate

                        if (
                            os.path.normcase(os.path.realpath(str(candidate)))
                            == target_script
                        ):
                            same_instance = True
                            break

            if same_instance:
                process.terminate()
                previous.append(process)

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            OSError,
            ValueError,
        ):
            continue

    if previous:
        _, alive = psutil.wait_procs(previous, timeout=5)

        for process in alive:
            try:
                process.kill()
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                pass

        if alive:
            psutil.wait_procs(alive, timeout=2)


def restore_virus_file():
    if not getattr(sys, "frozen", False):
        return

    meipass = getattr(sys, "_MEIPASS", None)
    base = Path(meipass) if meipass else Path(sys.executable).resolve().parent / CONTENTS_DIR
    virus_file = base / "assets" / "virus.txt"

    if virus_file.exists():
        return

    try:
        virus_file.parent.mkdir(parents=True, exist_ok=True)
        virus_file.write_text("i always come back", encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    close_previous_instances()
    restore_virus_file()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    if os.path.exists(FONT):
        fid = QFontDatabase.addApplicationFont(FONT)

        if fid >= 0:
            app.setFont(
                QFont(
                    QFontDatabase.applicationFontFamilies(fid)[0],
                    11,
                )
            )

    w = Window()

    if "--hidden" not in sys.argv:
        w.show()

    sys.exit(app.exec())
