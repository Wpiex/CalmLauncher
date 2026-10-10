import os
import sys
import threading
import time
import psutil

from PySide6.QtCore import Qt, Signal, QObject, QUrl, QTimer, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPixmap, QIcon, QDesktopServices, QImage, QCursor,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QLabel,
    QSlider, QProgressBar, QStackedWidget, QSystemTrayIcon, QMenu,
    QColorDialog, QMessageBox, QFileDialog, QSizePolicy, QInputDialog,
)

from constants import RED, GRAY, GREEN, APP_NAME, INSTANCES, ICON, WINDOW_NOTCH, DONATE_ICON, DONATE_URL
from core.config import load_cfg, save_cfg
from core.auth import login, SessionExpired
from core.game import install, run, crash_file, Cancelled
from core.versions import get_versions
from core.loaders import LOADERS, supported
from core.system import set_startup
from core import optimize, launcher_update, vault, java as javas
from core.oauth import microsoft_login
from ui import theme
from ui.style import build_style
from ui.effects import notch, blur, unblur
from ui.widgets import Button, IconButton, Panel, Card, Select, Check, Credit
from ui.content import ContentPage
from ui.instances import InstancesPage
from ui.skins import SkinsPage
from ui import sound
from ui.i18n import tr, bind, set_lang, retranslate, ask
from core import skins as skin_api

TERMS_TEXT = "I accept all registration terms for this launcher and assume full responsibility."
MICROSOFT_CLIENT_ID = "98c3ad7d-048d-44ea-a61a-11908b0a0647"

NETWORK_ERROR_MARKERS = (
    "404", "403", "429", "500", "502", "503", "504",
    "connection", "timeout", "timed out", "network", "http error",
    "ssl", "dns", "requestexception", "urlopenerror",
    "failed to establish", "connectionerror",
)

class Bridge(QObject):
    logged = Signal(dict)
    error = Signal(str)
    progress = Signal(str, int)
    installed = Signal(str)
    cancelled = Signal()
    launched = Signal()
    exited = Signal()
    expired = Signal()
    versions = Signal(list)
    loader_versions = Signal(str, list)
    crashed = Signal(str)
    skin_loaded = Signal(int, bytes)
    launcher_update_checked = Signal(object, str)
    launcher_update_finished = Signal(str, str)
    javas = Signal(list)
    microsoft_code = Signal(str, str)

def box(widget, margin=16, spacing=14):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return layout

def lbl(text):
    return bind(QLabel(), text)

def btn(text, color=None):
    return bind(Button(text, color), text)

def load_icon():
    if os.path.exists(ICON):
        return QIcon(ICON)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(*GREEN))
    painter.drawPolygon(notch(pixmap.rect(), 8))
    painter.end()
    return QIcon(pixmap)

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        theme.load(self.cfg)
        set_lang(self.cfg["lang"])
        self.java_items = []
        self.app_icon = load_icon()
        self.all_versions = []
        self.sup = {}
        self.cancel = threading.Event()
        self._account_skin_request = 0
        self.drag = None
        self.game_running = False
        self.show_action = None

        self.bridge = Bridge()
        self.bridge.logged.connect(self.on_logged)
        self.bridge.error.connect(self.on_error)
        self.bridge.progress.connect(self.on_progress)
        self.bridge.installed.connect(self.on_installed)
        self.bridge.cancelled.connect(self.on_cancelled)
        self.bridge.launched.connect(self.on_launched)
        self.bridge.exited.connect(self.on_exited)
        self.bridge.expired.connect(self.on_expired)
        self.bridge.versions.connect(self.on_versions)
        self.bridge.loader_versions.connect(self.on_loader_versions)
        self.bridge.crashed.connect(self.on_crashed)
        self.bridge.skin_loaded.connect(self.on_account_skin)
        self.bridge.launcher_update_checked.connect(self.on_launcher_update_checked)
        self.bridge.launcher_update_finished.connect(self.on_launcher_update_finished)
        self.bridge.javas.connect(self.on_javas)
        self.bridge.microsoft_code.connect(self.on_microsoft_code)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1000, 640)
        self.setWindowTitle(APP_NAME)
        self.setStyleSheet(build_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.logo = QLabel()
        title = QLabel("CALM LAUNCHER")
        self.credit = Credit("#ArtixTeam")

        self.account_box = QWidget()
        account_layout = QHBoxLayout(self.account_box)
        account_layout.setContentsMargins(8, 4, 8, 4)
        account_layout.setSpacing(6)

        self.account_head = QLabel()
        self.account_head.setFixedSize(28, 28)
        self.account_head.setAlignment(Qt.AlignCenter)
        self.account_head.setStyleSheet(
            "background: rgba(255,255,255,24); border-radius: 4px; "
            "font-weight: 700; color: white;"
        )
        self.account_name = QLabel("")
        self.account_name.setMaximumWidth(120)
        self.account_name.setStyleSheet("background: transparent; font-weight: 600;")
        self.provider_icon = QLabel()
        self.provider_icon.setFixedSize(18, 18)

        account_layout.addWidget(self.account_head)
        account_layout.addWidget(self.account_name)
        account_layout.addWidget(self.provider_icon)
        self.account_box.hide()

        minimize = Button("-")
        minimize.setFixedSize(40, 40)
        minimize.clicked.connect(self.showMinimized)
        close = Button("X", RED)
        close.setFixedSize(40, 40)
        close.clicked.connect(self.on_close)
        top.addWidget(self.logo)
        top.addWidget(title)
        top.addWidget(self.credit, 0, Qt.AlignVCenter)
        top.addStretch()
        top.addWidget(self.account_box)
        top.addWidget(minimize)
        top.addWidget(close)
        root.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.login_page())
        self.stack.addWidget(self.main_page())
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        root.addWidget(self.stack)
        root.addWidget(self.msg)

        self.make_tray()
        if self.cfg.get("account"):
            self.show_play()
        threading.Thread(target=self.t_versions, daemon=True).start()
        threading.Thread(target=self.t_javas, daemon=True).start()
        self.center()

    def center(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(
            area.x() + (area.width() - self.width()) // 2,
            area.y() + (area.height() - self.height()) // 2,
        )

    def apply_blur(self):
        theme.set_blur(self.cfg.get("blur"))
        if sys.platform == "win32":
            hwnd = int(self.winId())
            if self.cfg.get("blur"):
                blur(hwnd, self.width(), self.height(), self.devicePixelRatioF(), WINDOW_NOTCH)
            else:
                unblur(hwnd)
        for widget in self.findChildren(QWidget):
            widget.update()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_blur()

    def make_tray(self):
        self.setWindowIcon(self.app_icon)
        self.logo.setPixmap(self.app_icon.pixmap(36, 36))
        self.menu = QMenu(self)
        self.show_action = self.menu.addAction(
        tr("Show"), self.restore
        )
        bind(self.show_action, "Show")
        bind(self.menu.addAction(tr("Quit"), self.quit_app), "Quit")
        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self.on_tray)
        self.tray.show()

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore()
        elif reason == QSystemTrayIcon.Context:
            self.show_tray_menu()

    def show_tray_menu(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        size = self.menu.sizeHint()
        geometry = self.tray.geometry()
        anchor = geometry.center() if geometry.isValid() and not geometry.isEmpty() else QCursor.pos()
        x = min(max(anchor.x() - size.width() // 2, area.left()), area.right() - size.width())
        y = max(min(anchor.y() - size.height(), area.bottom() - size.height()), area.top())
        self.menu.exec(QPoint(x, y))

    def restore(self):
        self.center()
        self.showNormal()
        self.activateWindow()

    def quit_app(self):
        save_cfg(self.cfg)
        QApplication.quit()

    def on_close(self):
        if self.cfg["tray"]:
            self.hide()
        else:
            self.quit_app()

    def login_page(self):
       page = Panel()
       layout = box(page)

       card = Card()
       card_layout = QHBoxLayout(card)
       card_layout.setContentsMargins(10, 10, 10, 10)
       card_layout.setSpacing(12)

       self.ely_tab = Button("Ely.by")
       self.ms_tab = Button("Microsoft")
       self.ely_tab.clicked.connect(lambda: self.set_login_tab(0))
       self.ms_tab.clicked.connect(lambda: self.set_login_tab(1))

       card_layout.addWidget(self.ely_tab)
       card_layout.addWidget(self.ms_tab)
       layout.addWidget(card)

       self.user = QLineEdit()
       bind(self.user, "Username or Email", "setPlaceholderText")

       self.pw = QLineEdit()
       bind(self.pw, "Password", "setPlaceholderText")
       self.pw.setEchoMode(QLineEdit.Password)
       self.pw.returnPressed.connect(self.login)

       layout.addWidget(self.user)
       layout.addWidget(self.pw)
       layout.addStretch()

       login_card = Card()
       login_layout = box(login_card, 10)

       self.terms = bind(Check(TERMS_TEXT, wrap=True), TERMS_TEXT)
       self.terms.toggled.connect(lambda _: self.update_login_buttons())

       self.login_button = btn("Login")
       self.login_button.clicked.connect(self.login)

       self.microsoft_button = btn("Login Via Microsoft")
       self.microsoft_button.clicked.connect(self.microsoft_login)

       login_layout.addWidget(self.terms)
       login_layout.addWidget(self.login_button)
       login_layout.addWidget(self.microsoft_button)
       layout.addWidget(login_card)
       self.update_login_buttons()
       self.set_login_tab(0)
       return page

    def set_login_tab(self, index):
        ely = index == 0
        self.ely_tab.set_color(None if ely else GRAY)
        self.ms_tab.set_color(GRAY if ely else None)
        self.user.setVisible(ely)
        self.pw.setVisible(ely)
        self.login_button.setVisible(ely)
        self.microsoft_button.setVisible(not ely)
        if ely:
            self.user.setFocus()

    def update_login_buttons(self):
        if not hasattr(self, "terms"):
            return
        accepted = self.terms.isChecked()
        self.login_button.setEnabled(accepted)

    def main_page(self):
        widget = QWidget()
        horizontal = QHBoxLayout(widget)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(12)

        side = Panel()
        side.setFixedWidth(170)
        side_layout = box(side, 12, 12)
        self.tabs = [
            btn("Play"), btn("Install"), btn("Content"),
            btn("Skins"), btn("Settings"),
        ]
        for index, button in enumerate(self.tabs):
            button.clicked.connect(lambda _, i=index: self.set_tab(i))
            side_layout.addWidget(button)
        side_layout.addStretch()

        self.content = ContentPage(self.cfg)
        self.instances = InstancesPage(self.app_icon, self.play_instance, lambda: self.set_tab(1))
        self.skins = SkinsPage(self.cfg)

        self.ely_warning = lbl(
            "You are using a third-party account system (Ely.by)\n"
            "Skin editing takes place ONLY on the Ely.by website."
        )
        self.ely_warning.setAlignment(Qt.AlignCenter)
        self.ely_warning.setWordWrap(True)
        self.ely_warning.setStyleSheet(
            "QLabel { color: #ff4545; font-weight: 700; font-size: 12px; padding: 6px 10px; }"
        )
        self._ely_warning_bright = True
        self.ely_warning_timer = QTimer(self)
        self.ely_warning_timer.setInterval(600)
        self.ely_warning_timer.timeout.connect(self.blink_ely_warning)
        self.ely_warning_timer.start()

        self.pages = QStackedWidget()
        self.pages.addWidget(self.instances)
        self.pages.addWidget(self.install_page())
        self.pages.addWidget(self.content)

        skins_container = QWidget()
        skins_layout = QVBoxLayout(skins_container)
        skins_layout.setContentsMargins(0, 0, 0, 0)
        skins_layout.setSpacing(6)
        skins_layout.addWidget(self.ely_warning, 0)
        skins_layout.addWidget(self.skins, 1)
        self.pages.addWidget(skins_container)
        self.pages.addWidget(self.settings_page())

        horizontal.addWidget(side)
        horizontal.addWidget(self.pages)
        self.set_tab(0)
        return widget

    def set_tab(self, index):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.tabs):
            button.set_color(None if i == index else GRAY)
        if index == 0:
            self.instances.refresh()
        elif index == 2:
            self.content.sync()
        elif index == 3:
            self.skins.refresh()

    def install_page(self):
        page = Panel()
        layout = box(page)

        self.title_edit = QLineEdit()
        bind(self.title_edit, "Name (optional)", "setPlaceholderText")
        layout.addWidget(lbl("Name (Optional)"))
        layout.addWidget(self.title_edit)

        self.select = Select()
        self.select.currentTextChanged.connect(self.on_version)
        layout.addWidget(lbl("Version"))
        layout.addWidget(self.select)

        self.loader = Select()
        for key, label in LOADERS.items():
            self.loader.addItem(label, key)
        self.loader.setCurrentIndex(max(self.loader.findData(self.cfg["loader"]), 0))
        self.cfg["loader"] = self.loader.currentData()
        self.loader.currentIndexChanged.connect(self.on_loader)
        layout.addWidget(lbl("Loader"))
        layout.addWidget(self.loader)

        self.opt_lbl = lbl("Optimizer")
        self.opt = Select()
        layout.addWidget(self.opt_lbl)
        layout.addWidget(self.opt)
        layout.addStretch()

        card = Card()
        card_layout = box(card, 10, 12)
        card_layout.setContentsMargins(10, 10, 10, 20)
        self.status = QLabel("")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.install_btn = btn("Install")
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self.start_install)
        self.cancel_btn = btn("Cancel", RED)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_install)
        card_layout.addWidget(self.status)
        card_layout.addWidget(self.bar)
        card_layout.addWidget(self.install_btn)
        card_layout.addWidget(self.cancel_btn)
        layout.addWidget(card)

        self.apply_opt()
        return page

    def apply_opt(self):
        items = []
        if self.cfg["optimized"]:
            items = optimize.options(self.cfg["loader"], self.cfg["version"] or "")
        previous = self.opt.currentData()
        self.opt.blockSignals(True)
        self.opt.clear()
        if items:
            self.opt.addItem(tr("None"), None)
            for item in items:
                self.opt.addItem(item, item)
            index = self.opt.findData(previous)
            self.opt.setCurrentIndex(max(index, 0))
        self.opt.blockSignals(False)
        self.opt_lbl.setVisible(bool(items))
        self.opt.setVisible(bool(items))

    def settings_page(self):
        page = Panel()
        layout = box(page, 16, 8)

        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self.settings_tab_buttons = []
        for index, label in enumerate(("Launcher", "Java")):
            button = btn(label)
            button.setFixedWidth(120)
            button.clicked.connect(lambda _, i=index: self.set_settings_tab(i))
            tabs.addWidget(button)
            self.settings_tab_buttons.append(button)
        tabs.addStretch()
        donate = IconButton(DONATE_ICON)
        donate.setFixedSize(40, 40)
        donate.clicked.connect(self.open_donate)
        tabs.addWidget(donate)
        layout.addLayout(tabs)

        self.settings_stack = QStackedWidget()
        self.settings_stack.addWidget(self.launcher_settings_page())
        self.settings_stack.addWidget(self.java_settings_page())
        layout.addWidget(self.settings_stack, 1)
        self.set_settings_tab(0)
        return page

    def open_donate(self):
        sound.donate()
        QDesktopServices.openUrl(QUrl(DONATE_URL))

    def set_settings_tab(self, index):
        self.settings_stack.setCurrentIndex(index)
        for i, button in enumerate(self.settings_tab_buttons):
            button.set_color(None if i == index else GRAY)

    @staticmethod
    def recommended_memory_mb(total_mb):
        total_gb = max(1.0, float(total_mb) / 1024.0)
        anchors = ((4, 2), (8, 4), (12, 6), (16, 8), (32, 12), (64, 16))
        if total_gb <= anchors[0][0]:
            recommended_gb = anchors[0][1]
        elif total_gb >= anchors[-1][0]:
            recommended_gb = anchors[-1][1]
        else:
            recommended_gb = anchors[-1][1]
            for (left_ram, left_rec), (right_ram, right_rec) in zip(anchors, anchors[1:]):
                if left_ram <= total_gb <= right_ram:
                    ratio = (total_gb - left_ram) / (right_ram - left_ram)
                    recommended_gb = left_rec + ratio * (right_rec - left_rec)
                    break
        return max(2048, int(round(recommended_gb * 1024 / 512)) * 512)

    @staticmethod
    def _gb_text(mb):
        value = mb / 1024.0
        return f"{int(value)}" if value.is_integer() else f"{value:.1f}".rstrip("0").rstrip(".")

    def java_settings_page(self):
        page = Panel()
        layout = box(page, 16, 8)
        self.mem_total_mb = int(psutil.virtual_memory().total // 1_048_576)
        self.mem_recommended_mb = self.recommended_memory_mb(self.mem_total_mb)
        maximum = max(1024, ((self.mem_total_mb - 1024) // 512) * 512)

        self.mem_lbl = QLabel("")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1024, max(1024, maximum))
        self.slider.setSingleStep(512)
        self.slider.setPageStep(512)
        current = int(self.cfg.get("memory", 4096))
        self.slider.setValue(min(max(current, 1024), max(1024, maximum)))
        self.slider.valueChanged.connect(self.on_mem)
        self.slider.sliderReleased.connect(lambda: save_cfg(self.cfg))

        self.mem_warning = QLabel("")
        self.mem_warning.setWordWrap(True)
        self.mem_warning.setStyleSheet(
            "QLabel { color: #ff4545; font-weight: 700; font-size: 12px; padding: 6px 10px; }"
        )
        self.mem_warning.hide()
        tune = btn("Use reccomended")
        tune.clicked.connect(self.tune_memory)

        self.java_select = Select()
        self.java_select.addItem(tr("Auto (recommended)"), "")
        self.java_select.currentIndexChanged.connect(self.on_java_changed)
        browse = btn("Browse")
        browse.setFixedWidth(120)
        browse.clicked.connect(self.browse_java)
        java_row = QHBoxLayout()
        java_row.setSpacing(8)
        java_row.addWidget(self.java_select, 1)
        java_row.addWidget(browse)

        self.java_args = QLineEdit()
        self.java_args.setPlaceholderText("-Dkey=value -XX:+UseG1GC")
        self.java_args.setText(str(self.cfg.get("java_args") or ""))
        self.java_args.editingFinished.connect(self.on_java_args)

        layout.addWidget(lbl("Java memory allocation"))
        layout.addWidget(self.mem_lbl)
        layout.addWidget(self.slider)
        layout.addWidget(self.mem_warning)
        layout.addWidget(tune)
        layout.addWidget(lbl("Java version"))
        layout.addLayout(java_row)
        layout.addWidget(lbl("JVM arguments"))
        layout.addWidget(self.java_args)
        layout.addStretch()
        self.on_mem(self.slider.value(), True)
        return page

    def tune_memory(self):
        self.slider.setValue(min(self.mem_recommended_mb, self.slider.maximum()))
        save_cfg(self.cfg)

    def t_javas(self):
        try:
            items = javas.find([str(self.cfg.get("java_path") or "")])
        except Exception:
            items = []
        self.bridge.javas.emit(items)

    def on_javas(self, items):
        self.java_items = [tuple(item) for item in items]
        self.fill_javas()

    def fill_javas(self):
        saved = str(self.cfg.get("java_path") or "")
        self.java_select.blockSignals(True)
        self.java_select.clear()
        self.java_select.addItem(tr("Auto (recommended)"), "")
        for name, path in self.java_items:
            self.java_select.addItem(name, path)
            self.java_select.setItemData(self.java_select.count() - 1, path, Qt.ToolTipRole)
        index = self.java_select.findData(saved)
        self.java_select.setCurrentIndex(max(index, 0))
        self.java_select.blockSignals(False)

    def on_java_changed(self, _):
        self.cfg["java_path"] = self.java_select.currentData() or ""
        save_cfg(self.cfg)

    def on_java_args(self):
        self.cfg["java_args"] = self.java_args.text().strip()
        save_cfg(self.cfg)

    def browse_java(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Select Java"), "", "Java (java*)")
        if not path:
            return
        path = javas.normalize(path)
        name = javas.describe(path)
        if not name:
            self.msg.setText(tr("Invalid Java"))
            return
        self.msg.setText("")
        if path not in [item[1] for item in self.java_items]:
            self.java_items.append((name, path))
        self.cfg["java_path"] = path
        save_cfg(self.cfg)
        self.fill_javas()

    def launcher_settings_page(self):
        page = Panel()
        layout = box(page, 12, 8)

        layout.addWidget(lbl("Language"))
        languages = QHBoxLayout()
        languages.setSpacing(8)
        self.lang_buttons = {}
        for code, name in (("en", "English"), ("ru", "Russian")):
            button = Button(name)
            button.setFixedWidth(120)
            button.clicked.connect(lambda _, c=code: self.set_language(c))
            languages.addWidget(button)
            self.lang_buttons[code] = button
        languages.addStretch()
        layout.addLayout(languages)
        self.paint_languages()

        options = [
            ("startup", "Launch at Windows startup"),
            ("close_on_launch", "Close launcher after opening Minecraft"),
            ("reopen", "Reopen launcher when Minecraft closes"),
            ("tray", "Keep in tray when closed"),
            ("optimized", "Enable Optimized Versions"),
            ("blur", "Enable Transparency (Experimental)"),
        ]
        for key, label in options:
            check = bind(Check(label), label)
            check.setChecked(self.cfg[key])
            check.toggled.connect(lambda value, k=key: self.on_toggle(k, value))
            layout.addWidget(check)

        layout.addStretch()

        accent = btn("Button Color")
        accent.clicked.connect(lambda: self.pick_color("accent"))
        background = btn("Background Color")
        background.clicked.connect(lambda: self.pick_color("bg"))
        reset = btn("Reset Colors")
        reset.clicked.connect(self.reset_colors)
        folder = btn("Open instances folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(INSTANCES)))
        self.update_btn = btn("Check for updates")
        self.update_btn.clicked.connect(self.check_launcher_updates)
        logout = btn("Logout")
        logout.clicked.connect(self.logout)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)
        for index, button in enumerate((accent, background, reset, folder, self.update_btn, logout)):
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grid.addWidget(button, index // 3, index % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)
        return page

    def paint_languages(self):
        for code, button in self.lang_buttons.items():
            button.set_color(None if code == self.cfg.get("lang") else GRAY)

    def set_language(self, code):
        if code == self.cfg.get("lang"):
            return
        self.cfg["lang"] = code
        save_cfg(self.cfg)
        set_lang(code)
        retranslate()
        self.paint_languages()
        self.on_mem(self.slider.value(), True)
        self.apply_opt()
        self.fill_javas()
        self.instances.refresh()
        self.content.retranslate()
        self.msg.setText("")

    def check_launcher_updates(self):
        if not hasattr(self, "update_btn") or not self.update_btn.isEnabled():
            return
        self.update_btn.setEnabled(False)
        self.update_btn.setText(tr("Checking..."))
        threading.Thread(target=self.t_check_launcher_updates, daemon=True).start()

    def t_check_launcher_updates(self):
        current = str(self.cfg.get("launcher_version") or launcher_update.CURRENT_VERSION)
        try:
            release = launcher_update.check_latest_release(current)
            self.bridge.launcher_update_checked.emit(release, "")
        except Exception as exc:
            self.bridge.launcher_update_checked.emit(None, str(exc))

    def restore_update_btn(self):
        if self.update_btn.isEnabled():
            self.update_btn.setText(tr("Check for updates"))

    def on_launcher_update_checked(self, release, error):
        self.update_btn.setEnabled(True)
        self.update_btn.setText(tr("Check for updates"))
        if error:
            QMessageBox.warning(self, tr("Update check"), tr(error))
            return
        if not release:
            self.update_btn.setText(tr("No updates yet!"))
            QTimer.singleShot(3000, self.restore_update_btn)
            return

        notes = release.get("body") or tr("No release notes provided.")
        if len(notes) > 1400:
            notes = notes[:1400].rstrip() + "…"
        message = tr(
            "A new version is available: {}\n\n{}\n\nDownload and install this update?"
        ).format(release["tag_name"], notes)
        if not ask(self, "Calm Launcher update", message):
            return

        self.update_btn.setEnabled(False)
        self.update_btn.setText(tr("Downloading..."))
        threading.Thread(
            target=self.t_install_launcher_update,
            args=(release,),
            daemon=True,
        ).start()

    def t_install_launcher_update(self, release):
        try:
            version = launcher_update.install_release_zip(
                release["asset_url"], release["tag_name"]
            )
            self.bridge.launcher_update_finished.emit(version, "")
        except Exception as exc:
            self.bridge.launcher_update_finished.emit("", str(exc))

    def on_launcher_update_finished(self, version, error):
        self.update_btn.setEnabled(True)
        self.update_btn.setText(tr("Check for updates"))
        if error:
            QMessageBox.warning(self, tr("Update failed"), tr(error))
            return
        self.cfg["launcher_version"] = version
        save_cfg(self.cfg)
        if launcher_update.is_frozen():
            QMessageBox.information(
                self,
                tr("Update installed"),
                tr("Calm Launcher {} has been downloaded.\n\nThe launcher will now restart to apply the update.").format(version),
            )
            self.quit_app()
            return
        QMessageBox.information(
            self,
            tr("Update installed"),
            tr("Calm Launcher {} has been installed.\n\nRestart Calm Launcher to use the updated files.").format(version),
        )

    def pick_color(self, key):
        color = QColorDialog.getColor(QColor(*theme.THEME[key]), self, tr("Color"))
        if not color.isValid():
            return
        theme.THEME[key] = (color.red(), color.green(), color.blue())
        self.save_theme()

    def reset_colors(self):
        theme.THEME.update(theme.DEFAULT)
        self.save_theme()

    def save_theme(self):
        theme.store(self.cfg)
        save_cfg(self.cfg)
        self.setStyleSheet(build_style())
        if hasattr(self, "content"):
            self.content.paint_source()
            self.content.paint_types()
        for widget in self.findChildren(QWidget):
            widget.update()
        self.update()

    def on_toggle(self, key, value):
        self.cfg[key] = value
        save_cfg(self.cfg)
        if key == "startup":
            set_startup(value)
        if key == "optimized":
            self.apply_opt()
        if key == "blur":
            self.apply_blur()

    def update_ely_warning(self):
        if not hasattr(self, "ely_warning"):
            return

        account = self.cfg.get("account") or {}
        account_type = str(account.get("type", "ely")).lower()

        is_microsoft = account_type in (
            "microsoft",
            "ms",
            "microsoft_oauth",
        )

        show_warning = bool(account) and not is_microsoft
        self.ely_warning.setVisible(show_warning)

        if hasattr(self, "ely_warning_timer"):
            if show_warning:
                if not self.ely_warning_timer.isActive():
                    self.ely_warning_timer.start()
            else:
                self.ely_warning_timer.stop()

    def blink_ely_warning(self):
        self._ely_warning_bright = not self._ely_warning_bright
        color = "#ff4545" if self._ely_warning_bright else "#8f2525"
        style = f"QLabel {{ color: {color}; font-weight: 700; font-size: 12px; padding: 6px 10px; }}"
        self.ely_warning.setStyleSheet(style)
        if hasattr(self, "mem_warning") and self.mem_warning.isVisible():
            self.mem_warning.setStyleSheet(style)

    def make_provider_icon(self, is_microsoft):
        filename = "microsoft.png" if is_microsoft else "elyby.png"

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        candidates = [
            os.path.join(project_dir, filename),
            os.path.join(project_dir, "assets", filename),
            os.path.join(project_dir, "assets", "icons", filename),
            os.path.join(project_dir, "icons", filename),
            os.path.join(project_dir, "ui", filename),
            os.path.join(project_dir, "ui", "assets", filename),
            os.path.join(project_dir, "resources", filename),
        ]

        icon_path = next(
            (path for path in candidates if os.path.isfile(path)),
            None,
        )

        self.provider_icon.setToolTip(
            tr("Microsoft account") if is_microsoft else tr("Ely.by account")
        )
        self.provider_icon.setAlignment(Qt.AlignCenter)
        self.provider_icon.setStyleSheet("background: transparent;")

        if icon_path:
            pixmap = QPixmap(icon_path)

            if not pixmap.isNull():
                self.provider_icon.setText("")
                self.provider_icon.setPixmap(
                    pixmap.scaled(
                        18,
                        18,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.provider_icon.setVisible(True)
                return

        self.provider_icon.setPixmap(QPixmap())
        self.provider_icon.setText("M" if is_microsoft else "E")
        self.provider_icon.setVisible(True)

    def update_account_bar(self):
        account = self.cfg.get("account") or {}
        self._account_skin_request += 1
        request_id = self._account_skin_request
        self.account_box.setVisible(bool(account))

        if not account:
            self.account_name.clear()
            self.account_head.clear()
            self.provider_icon.clear()
            self.provider_icon.hide()
            if hasattr(self, "ely_warning"):
                self.update_ely_warning()
            return

        name = str(account.get("name") or tr("Account"))
        self.account_name.setText(name)
        self.account_head.setText(name[:1].upper() if name else "?")

        account_type = str(account.get("type", "ely")).lower()
        is_microsoft = account_type in ("microsoft", "ms", "microsoft_oauth")
        self.make_provider_icon(is_microsoft)

        threading.Thread(
            target=self.t_account_skin,
            args=(dict(account), request_id),
            daemon=True,
        ).start()
        if hasattr(self, "ely_warning"):
            self.update_ely_warning()

    def t_account_skin(self, account, request_id):
        try:
            if account.get("type", "ely") == "ely":
                data, _ = skin_api.ely_skin(account["name"])
            else:
                data, _ = skin_api.ms_skin(account["token"])
            self.bridge.skin_loaded.emit(request_id, data)
        except Exception:
            self.bridge.skin_loaded.emit(request_id, b"")

    def on_account_skin(self, request_id, data):
        if request_id != self._account_skin_request or not self.cfg.get("account"):
            return
        if not data:
            return
        image = QImage.fromData(data)
        if image.isNull() or image.width() < 16 or image.height() < 16:
            return

        face = QPixmap(8, 8)
        face.fill(Qt.transparent)
        painter = QPainter(face)
        painter.drawImage(0, 0, image.copy(8, 8, 8, 8))
        if image.width() >= 48 and image.height() >= 64:
            painter.drawImage(0, 0, image.copy(40, 8, 8, 8))
        painter.end()
        self.account_head.setText("")
        self.account_head.setPixmap(
            face.scaled(28, 28, Qt.KeepAspectRatio, Qt.FastTransformation)
        )

    def show_play(self):
        self.update_account_bar()
        self.stack.setCurrentIndex(1)

    def on_mem(self, value, silent=False):
        value = value // 512 * 512
        value = min(max(value, self.slider.minimum()), self.slider.maximum())
        if value != self.cfg.get("memory", 4096) and not silent:
            sound.slider()
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        total_gb = self._gb_text(self.mem_total_mb)
        recommended_gb = self._gb_text(self.mem_recommended_mb)
        self.mem_lbl.setText(
            tr("Memory: {} GB allocated · {} GB total · Recommended: {} GB").format(
                self._gb_text(value), total_gb, recommended_gb
            )
        )
        self.cfg["memory"] = value
        over_recommended = value > self.mem_recommended_mb
        if over_recommended:
            self.mem_warning.setText(
                tr("Allocating more RAM than the recommended amount ({} GB) may lead to problems.").format(
                    recommended_gb
                )
            )
            self.mem_warning.show()
        else:
            self.mem_warning.hide()

    def on_version(self, version):
        if version:
            self.cfg["version"] = version
            self.apply_opt()

    def on_loader(self, _):
        self.cfg["loader"] = self.loader.currentData()
        self.apply_versions()

    def t_versions(self):
        try:
            items = get_versions()
        except Exception:
            items = [self.cfg["version"] or "1.20.1"]
        self.bridge.versions.emit(items)

    def on_versions(self, items):
        self.all_versions = items
        self.apply_versions()
        self.content.set_versions(items)

    def apply_versions(self):
        loader = self.cfg["loader"]
        items = self.all_versions
        if loader != "vanilla":
            supported_versions = self.sup.get(loader)
            if supported_versions is None:
                self.select.blockSignals(True)
                self.select.clear()
                self.select.blockSignals(False)
                self.install_btn.setEnabled(False)
                self.apply_opt()
                if items:
                    threading.Thread(
                        target=self.t_loader_versions,
                        args=(loader,),
                        daemon=True,
                    ).start()
                return
            items = [version for version in items if version in supported_versions]

        self.select.blockSignals(True)
        self.select.clear()
        self.select.addItems(items)
        version = self.cfg["version"]
        if items:
            self.select.setCurrentText(version if version in items else items[0])
            self.cfg["version"] = self.select.currentText()
        self.select.blockSignals(False)
        self.install_btn.setEnabled(bool(items))
        self.apply_opt()

    def t_loader_versions(self, loader):
        try:
            self.bridge.loader_versions.emit(loader, supported(loader))
        except Exception as exc:
            self.bridge.error.emit(str(exc))

    def on_loader_versions(self, loader, items):
        self.sup[loader] = items
        if loader == self.cfg["loader"]:
            self.apply_versions()

    def on_microsoft_code(self, uri, code):
        dialog = QMessageBox(
            QMessageBox.NoIcon,
            "Microsoft",
            tr("Your code is: {}").format(code),
            QMessageBox.NoButton,
            self,
        )
        ok = dialog.addButton(tr("Ok"), QMessageBox.AcceptRole)
        copy = dialog.addButton(tr("Copy"), QMessageBox.ActionRole)
        dialog.setDefaultButton(ok)
        dialog.setEscapeButton(ok)
        while True:
            dialog.exec()
            if dialog.clickedButton() is copy:
                QApplication.clipboard().setText(code)
                copy.setText(tr("Copied"))
                continue
            break
        self.msg.setText(tr("Waiting for Microsoft authorization..."))
        self.code_ok = True
        self.code_wait.set()

    def ask_code(self, uri, code):
        self.code_ok = False
        self.code_wait = threading.Event()
        self.bridge.microsoft_code.emit(uri, code)
        self.code_wait.wait(900)
        return self.code_ok

    def login(self):
        if not self.terms.isChecked():
            return
        username, password = self.user.text().strip(), self.pw.text()
        if not username or not password:
            return
        self.msg.setText("")
        threading.Thread(
            target=self.t_login,
            args=(username, password),
            daemon=True,
        ).start()

    def t_login(self, username, password):
        try:
            self.bridge.logged.emit(login(self.cfg, username, password))
        except Exception as exc:
            self.bridge.error.emit(str(exc))

    def microsoft_client_id(self):
        return MICROSOFT_CLIENT_ID

    def microsoft_login(self):
        if not hasattr(self, "microsoft_button"):
            return

        if not self.microsoft_button.isEnabled():
            return

        if not self.terms.isChecked():
            QMessageBox.warning(self, APP_NAME, tr("Please Accept Registration terms"))
            return

        client_id = self.microsoft_client_id()
        if not client_id:
            return

        self.msg.setText("")
        self.microsoft_button.setEnabled(False)

        threading.Thread(
            target=self.t_microsoft_login,
            args=(client_id,),
            daemon=True,
        ).start()

    def t_microsoft_login(self, client_id):
        try:
            account = microsoft_login(
                client_id,
                on_device_code=self.ask_code,
            )
            self.bridge.logged.emit(account)
        except Exception as exc:
            self.bridge.error.emit(str(exc))

    def on_logged(self, account):
        if hasattr(self, "microsoft_button"):
           self.terms.setChecked(False)
           self.update_login_buttons()

           self.cfg["account"] = account
           save_cfg(self.cfg)
           self.pw.clear()
           self.msg.setText("")
           self.update_ely_warning()
           self.show_play()

    def on_error(self, text):
        self.update_login_buttons()
        sound.error()
        text = str(text)
        lowered = text.lower()
        if "AADSTS700016" in text or "invalid_client" in lowered:
            if self.cfg.pop("microsoft_client_id", None) is not None:
                save_cfg(self.cfg)
        if text != "Installation Error" and any(
            marker in lowered for marker in NETWORK_ERROR_MARKERS
        ):
            text = "Check your Internet connection"
        self.msg.setText(tr(text))
        self.install_btn.setEnabled(self.select.count() > 0)
        self.cancel_btn.setVisible(False)
        self.instances.set_busy(False)
        self.instances.set_status("")
        self.status.setText("")
        self.bar.setValue(0)
        self.instances.refresh()

    def on_expired(self):
        self.cfg["account"] = None
        save_cfg(self.cfg)
        self.update_account_bar()
        self.stack.setCurrentIndex(0)

    def on_progress(self, text, value):
        if text:
           self.status.setText(tr(text))
        if value >= 0:
           self.bar.setValue(value)

    def logout(self):
        self.terms.setChecked(False)
        self.cfg["account"] = None
        save_cfg(self.cfg)
        self.update_account_bar()
        self.stack.setCurrentIndex(0)
        self.update_ely_warning()
        self.msg.setText("")

    def start_install(self):
        version, loader = self.cfg["version"], self.cfg["loader"]
        if not version:
            return
        title = self.title_edit.text().strip() or None
        extra = self.opt.currentData() if self.opt.count() else None
        save_cfg(self.cfg)
        self.msg.setText("")
        self.cancel = threading.Event()
        self.install_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setVisible(True)
        threading.Thread(
            target=self.t_install,
            args=(version, loader, title, extra, self.cancel),
            daemon=True,
        ).start()

    def cancel_install(self):
        self.cancel.set()
        self.cancel_btn.setEnabled(False)
        self.status.setText(tr("Cancelling"))

    def t_install(self, version, loader, title, extra, cancel):
        try:
            warning = install(version, loader, self.bridge.progress.emit, title, cancel, extra)
        except Cancelled:
            self.bridge.cancelled.emit()
            return
        except Exception:
            self.bridge.error.emit("Installation Error")
            return
        self.bridge.installed.emit(warning or "")

    def on_installed(self, warning):
        self.install_btn.setEnabled(self.select.count() > 0)
        self.cancel_btn.setVisible(False)
        self.title_edit.clear()
        self.status.setText(tr("Completed"))
        self.bar.setValue(100)
        self.msg.setText(warning)
        self.instances.refresh()
        sound.completed()

    def on_cancelled(self):
        self.install_btn.setEnabled(self.select.count() > 0)
        self.cancel_btn.setVisible(False)
        self.status.setText(tr("Cancelled"))
        self.bar.setValue(0)
        self.instances.set_status("")
        self.instances.refresh()

    def play_instance(self, name):
        save_cfg(self.cfg)
        self.msg.setText("")
        self.instances.set_busy(True)
        threading.Thread(target=self.t_play, args=(name,), daemon=True).start()

    def t_play(self, name):
        start = time.time() - 2
        try:
            process = run(self.cfg, name, self.bridge.progress.emit)
        except SessionExpired as exc:
            self.bridge.error.emit(str(exc))
            self.bridge.expired.emit()
            return
        except Exception as exc:
            self.bridge.error.emit(str(exc))
            return
        self.bridge.launched.emit()
        code = process.wait()
        if code != 0:
            path = crash_file(name, start)
            if path:
                self.bridge.crashed.emit(path)
        self.bridge.exited.emit()

    def on_crashed(self, path):
        sound.error()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_launched(self):
        self.game_running = True
        if self.show_action:
          self.show_action.setVisible(False)
        self.status.setText("")
        self.bar.setValue(0)
        self.instances.set_status("")
        if self.cfg["close_on_launch"]:
          self.quit_app()
        else:
          self.hide()

    def on_exited(self):
        self.game_running = False
        if self.show_action:
           self.show_action.setVisible(True)
        self.instances.set_busy(False)
        if self.cfg["reopen"]:
           self.restore()

    def closeEvent(self, event):
        event.ignore()
        self.on_close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*theme.bg(), theme.window_alpha()))
        painter.drawPolygon(notch(self.rect(), WINDOW_NOTCH))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, event):
        self.drag = None