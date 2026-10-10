import threading
from PySide6.QtCore import QUrl, Signal, QObject
from PySide6.QtGui import QImage, QDesktopServices
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFileDialog
from core import skins
from ui.widgets import Button, Panel, Card
from ui.skinview import SkinView
from ui import sound
from ui.i18n import tr, bind
from constants import GRAY

ELY_URL = "https://ely.by/skins"

class Bridge(QObject):
    loaded = Signal(bytes, bool)
    error = Signal(str)

class SkinsPage(Panel):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.data = None
        self.slim = False
        self.bridge = Bridge()
        self.bridge.loaded.connect(self.on_loaded)
        self.bridge.error.connect(self.on_error)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 16, 16, 16)
        h.setSpacing(16)

        card = Card()
        card.setFixedWidth(260)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 8, 8, 8)
        self.view = SkinView()
        cl.addWidget(self.view)

        col = QVBoxLayout()
        col.setSpacing(10)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.b_upload = bind(Button("Upload Skin"), "Upload Skin")
        self.b_default = bind(Button("Default"), "Default")
        self.b_slim = bind(Button("Slim"), "Slim")
        self.b_manage = bind(Button("Manage on Ely.by"), "Manage on Ely.by")
        self.b_reset = bind(Button("Reset Skin"), "Reset Skin")
        self.b_upload.clicked.connect(self.upload)
        self.b_default.clicked.connect(lambda: self.set_arms(False))
        self.b_slim.clicked.connect(lambda: self.set_arms(True))
        self.b_manage.clicked.connect(self.open_ely)
        self.b_reset.clicked.connect(self.reset)
        col.addWidget(self.b_upload)
        arms = QHBoxLayout()
        arms.setSpacing(6)
        arms.addWidget(self.b_default, 1)
        arms.addWidget(self.b_slim, 1)
        col.addWidget(bind(QLabel(), "Arms"))
        col.addLayout(arms)
        col.addWidget(self.b_manage)
        col.addWidget(self.b_reset)
        col.addStretch()
        col.addWidget(self.status)

        h.addWidget(card)
        h.addLayout(col, 1)
        self.paint_arms()

    def paint_arms(self):
        self.b_default.set_color(GRAY if self.slim else None)
        self.b_slim.set_color(None if self.slim else GRAY)

    def account(self):
        return self.cfg["account"] or {}

    def is_ely(self):
        return self.account().get("type", "ely") == "ely"

    def open_ely(self):
        QDesktopServices.openUrl(QUrl(ELY_URL))

    def refresh(self):
        acc = self.account()
        if not acc:
            return
        ely = self.is_ely()
        self.b_manage.setVisible(ely)
        self.b_reset.setVisible(not ely)
        self.status.setText(tr("Loading"))
        threading.Thread(target=self.t_load, args=(dict(acc),), daemon=True).start()

    def t_load(self, acc):
        try:
            if acc.get("type", "ely") == "ely":
                data, slim = skins.ely_skin(acc["name"])
            else:
                data, slim = skins.ms_skin(acc["token"])
            self.bridge.loaded.emit(data, slim)
        except Exception as e:
            self.bridge.error.emit(str(e))

    def on_loaded(self, data, slim):
        img = QImage.fromData(data)
        if img.isNull():
            self.status.setText(tr("Invalid skin"))
            return
        self.data = data
        self.slim = slim
        self.paint_arms()
        self.view.set_skin(img, slim)
        self.status.setText("")

    def on_error(self, text):
        self.status.setText(tr(text))
        sound.error()

    def upload(self):
        if self.is_ely():
            self.open_ely()
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Skin"), "", "PNG (*.png)")
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        img = QImage.fromData(data)
        if img.isNull() or img.width() != 64 or img.height() not in (32, 64):
            self.status.setText(tr("Skin must be a 64x64 or 64x32 PNG"))
            return
        self.send(data, self.slim)

    def set_arms(self, slim):
        if self.is_ely():
            self.open_ely()
            return
        if self.data is None:
            return
        self.send(self.data, slim)

    def send(self, data, slim):
        self.status.setText(tr("Uploading"))
        threading.Thread(target=self.t_send, args=(self.account()["token"], data, slim), daemon=True).start()

    def t_send(self, token, data, slim):
        try:
            skins.ms_upload(token, data, slim)
            self.bridge.loaded.emit(data, slim)
        except Exception as e:
            self.bridge.error.emit(str(e))

    def reset(self):
        self.status.setText(tr("Resetting"))
        threading.Thread(target=self.t_reset, args=(self.account()["token"],), daemon=True).start()

    def t_reset(self, token):
        try:
            skins.ms_reset(token)
            data, slim = skins.ms_skin(token)
            self.bridge.loaded.emit(data, slim)
        except Exception as e:
            self.bridge.error.emit(str(e))