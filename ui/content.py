import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QScrollArea,
    QWidget,
    QFrame,
)

from core import modrinth, instances, content_updates
from core.config import save_cfg
from core.loaders import LOADERS
from ui.widgets import Button, Panel, Card, Select, Icon
from ui import sound, theme
from ui.i18n import tr, bind

TYPES = [("Mods", "mod"), ("Resources", "resourcepack"), ("Shaders", "shader")]
POOL = ThreadPoolExecutor(max_workers=6)
ICONS = {}

NETWORK_ERROR_MARKERS = (
    "404", "403", "429", "500", "502", "503", "504",
    "connection", "timeout", "timed out", "network", "http error",
    "ssl", "dns", "requestexception", "urlopenerror",
    "failed to establish", "connectionerror",
)

def fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

class Bridge(QObject):
    results = Signal(int, list, int)
    done = Signal(object, str)
    error = Signal(str)
    icon = Signal(object, str, bytes)
    update_checked = Signal(object, str, object, str)
    update_done = Signal(object, str, str)


def find_installed_project_file(hit, instance_name, ptype):
    if not instance_name:
        return None

    try:
        root = instances.instance_path(instance_name)
    except Exception:
        return None

    folders = {
        "mod": "mods",
        "resourcepack": "resourcepacks",
        "shader": "shaderpacks",
    }
    folder = folders.get(ptype)
    if not folder:
        return None

    candidates = (
        os.path.join(root, folder),
        os.path.join(root, "minecraft", folder),
    )

    def normalize(value):
        return re.sub(r"[^a-z0-9]", "", value.lower())

    keys = {
        normalize(str(hit.get(field) or ""))
        for field in ("slug", "title")
        if hit.get(field)
    }
    keys.discard("")
    if not keys:
        return None

    for directory in candidates:
        if not os.path.isdir(directory):
            continue
        try:
            filenames = os.listdir(directory)
        except OSError:
            continue

        for filename in filenames:
            if not filename.lower().endswith((".jar", ".zip")):
                continue
            file_key = normalize(os.path.splitext(filename)[0])
            if any(key in file_key for key in keys):
                return os.path.join(directory, filename)
    return None

def is_project_installed(hit, instance_name, ptype):
    return find_installed_project_file(hit, instance_name, ptype) is not None

class ContentPage(Panel):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        changed_cfg = self.cfg.pop("curseforge_api_key", None) is not None
        if str(self.cfg.get("content_source", "modrinth")).lower() != "modrinth":
            self.cfg["content_source"] = "modrinth"
            changed_cfg = True
        self.source = "modrinth"
        if changed_cfg:
            save_cfg(self.cfg)

        self.bridge = Bridge()
        self.bridge.results.connect(self.on_results)
        self.bridge.done.connect(self.on_done)
        self.bridge.error.connect(self.on_error)
        self.bridge.icon.connect(self.on_icon)
        self.bridge.update_checked.connect(self.on_update_checked)
        self.bridge.update_done.connect(self.on_update_done)
        self.synced = False
        self.token = 0
        self.offset = 0
        self.ptype = "mod"
        self.more = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        source_row = QHBoxLayout()
        source_row.setSpacing(10)
        self.source_btns = []
        for label, key in (("Modrinth", "modrinth"), ("CurseForge", "curseforge")):
            button = Button(label)
            if key == "curseforge":
                button.setEnabled(False)
                button.setToolTip(tr("Temporarily unavailable"))
                button.set_color(None)
            else:
                button.clicked.connect(lambda _, value=key: self.set_source(value))
            source_row.addWidget(button)
            self.source_btns.append((key, button))
        source_row.addStretch()
        layout.addLayout(source_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.search = QLineEdit()
        bind(self.search, "Search", "setPlaceholderText")
        self.search.returnPressed.connect(self.reset)
        go = bind(Button("Go"), "Go")
        go.setFixedWidth(90)
        go.clicked.connect(self.reset)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(go)
        layout.addLayout(search_row)

        self.inst = Select()
        self.inst.currentIndexChanged.connect(lambda _: self.apply_instance(True))
        layout.addWidget(self.inst)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_btns = []
        for name, key in TYPES:
            button = Button(name)
            button.clicked.connect(lambda _, k=key: self.set_type(k))
            type_row.addWidget(button)
            self.type_btns.append((key, button))

        self.filters_btn = bind(Button("Filters"), "Filters")
        self.filters_btn.setFixedWidth(130)
        self.filters_btn.clicked.connect(self.toggle_filters)
        type_row.addWidget(self.filters_btn)
        layout.addLayout(type_row)

        self.filter_panel = QWidget()
        filter_row = QHBoxLayout(self.filter_panel)
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        self.version = Select()
        self.loader = Select()
        self.sort = Select()
        for key, label in LOADERS.items():
            self.loader.addItem(label, key)
        for control in (self.version, self.loader):
            control.currentIndexChanged.connect(self.reset)
            filter_row.addWidget(control)
        filter_row.addWidget(self.sort)
        self.sort.currentIndexChanged.connect(self.reset)
        self.filter_panel.hide()
        layout.addWidget(self.filter_panel)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.list = QVBoxLayout(body)
        self.list.setContentsMargins(0, 0, 8, 0)
        self.list.setSpacing(8)
        self.list.addStretch()
        self.scroll.setWidget(body)
        layout.addWidget(self.scroll, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.configure_sort()
        self.paint_source()
        self.paint_types()

    def retranslate(self):
        self.configure_sort()
        if self.list.count() > 1:
            self.reset()

    def toggle_filters(self):
        self.filter_panel.setVisible(not self.filter_panel.isVisible())

    def paint_source(self):
        for key, button in self.source_btns:
            if key == "curseforge" or key == self.source:
                button.set_color(None)
            else:
                button.set_color(theme.shade(theme.bg(), 15))

    def configure_sort(self, preferred=None):
        if preferred is None:
            preferred = self.sort.currentData() if self.sort.count() else None
        mapping = modrinth.SORTS
        self.sort.blockSignals(True)
        self.sort.clear()
        for label, value in mapping.items():
            self.sort.addItem(tr(label), value)
        index = self.sort.findData(preferred)
        self.sort.setCurrentIndex(index if index >= 0 else 0)
        self.sort.blockSignals(False)

    def set_source(self, source):
        if source != "modrinth" or source == self.source:
            return
        self.source = "modrinth"
        self.cfg["content_source"] = self.source
        save_cfg(self.cfg)
        self.paint_source()
        self.configure_sort()
        self.reset()

    def paint_types(self):
        for key, button in self.type_btns:
            if key == self.ptype:
                button.set_color(None)
            else:
                button.set_color(theme.shade(theme.bg(), 15))

    def set_type(self, key):
        self.ptype = key
        self.paint_types()
        self.reset()

    def set_versions(self, items):
        self.version.blockSignals(True)
        self.version.clear()
        self.version.addItems(items)
        version = self.cfg.get("version", "")
        if version in items:
            self.version.setCurrentText(version)
        elif items:
            self.version.setCurrentIndex(len(items) - 1)
        self.version.blockSignals(False)
        if self.synced:
            if self.inst.currentData():
                self.apply_instance(True)
            else:
                self.reset()

    def sync(self):
        current = self.inst.currentData()
        names = instances.list_instances()
        self.inst.blockSignals(True)
        self.inst.clear()
        for name in names:
            self.inst.addItem(instances.title(name), name)
        index = self.inst.findData(current)
        self.inst.setCurrentIndex(index if index >= 0 else 0)
        self.inst.blockSignals(False)
        self.version.setEnabled(not names)
        self.loader.setEnabled(not names)
        self.synced = True
        if not names:
            if self.list.count() == 1:
                self.reset()
            return
        self.apply_instance(reset=index < 0 or self.list.count() == 1)

    def apply_instance(self, reset=True):
        name = self.inst.currentData()
        if not name:
            return
        meta = instances.read_meta(name)
        self.version.blockSignals(True)
        self.loader.blockSignals(True)
        vi = self.version.findText(meta["version"])
        if vi >= 0:
            self.version.setCurrentIndex(vi)
        li = self.loader.findData(meta["loader"])
        if li >= 0:
            self.loader.setCurrentIndex(li)
        self.version.blockSignals(False)
        self.loader.blockSignals(False)
        if reset:
            self.reset()

    def clear(self):
        self.more = None
        while self.list.count() > 1:
            item = self.list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def reset(self, *_):
        self.token += 1
        self.offset = 0
        self.clear()
        self.fetch()

    def fetch(self):
        self.status.setText(tr("Loading"))
        args = (
            self.token,
            self.source,
            self.ptype,
            self.search.text().strip(),
            self.version.currentText(),
            self.loader.currentData(),
            self.sort.currentData(),
            self.offset,
        )
        threading.Thread(target=self.t_fetch, args=args, daemon=True).start()

    def t_fetch(self, token, source, ptype, query, version, loader, sort, offset):
        try:
            if source != "modrinth":
                raise RuntimeError("CurseForge is temporarily unavailable")
            hits, total = modrinth.search(ptype, query, version, loader, sort, offset)
            self.bridge.results.emit(token, hits, total)
        except Exception as exc:
            self.bridge.error.emit(str(exc))

    def on_results(self, token, hits, total):
        if token != self.token:
            return
        first_page = self.offset == 0
        if self.more:
            self.more.deleteLater()
            self.more = None
        for hit in hits:
            self.add_item(hit)
        self.offset += len(hits)
        if self.offset < total and hits:
            self.more = Button(tr("More"))
            self.more.clicked.connect(self.load_more)
            self.list.insertWidget(self.list.count() - 1, self.more)
        if first_page and (total == 0 or not hits):
            self.status.setText(tr("Nothing found"))
        else:
            self.status.setText("")

    def load_more(self):
        if self.more:
            self.more.setEnabled(False)
        self.fetch()

    def on_error(self, text):
        error_text = str(text).lower()
        if any(marker in error_text for marker in NETWORK_ERROR_MARKERS):
            self.status.setText(tr("Check your Internet connection"))
        else:
            self.status.setText(tr(str(text)) if str(text) else tr("Check your Internet connection"))

    def t_icon(self, icon, url):
        try:
            data = modrinth.fetch_bytes(url)
            self.bridge.icon.emit(icon, url, data)
        except Exception:
            pass

    def on_icon(self, icon, url, data):
        ICONS[url] = data
        self.set_icon(icon, data)

    def set_icon(self, icon, data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            try:
                icon.set_pixmap(pixmap)
            except RuntimeError:
                pass

    def add_item(self, hit):
        card = Card()
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 10, 8)
        row.setSpacing(10)
        icon = Icon()
        url = hit.get("icon_url")
        if url:
            if url in ICONS:
                self.set_icon(icon, ICONS[url])
            else:
                POOL.submit(self.t_icon, icon, url)

        column = QVBoxLayout()
        column.setSpacing(2)
        title = QLabel(hit.get("title") or tr("Unknown project"))
        title.setWordWrap(True)
        meta = QLabel(f'{hit.get("author") or tr("Unknown")} - {fmt(hit.get("downloads", 0))} {tr("downloads")}')
        meta.setWordWrap(True)
        meta.setStyleSheet("color:rgba(255,255,255,140);")
        column.addWidget(title)
        column.addWidget(meta)

        instance_name = self.inst.currentData()
        installed_path = find_installed_project_file(hit, instance_name, self.ptype)
        installed = installed_path is not None
        button = Button(tr("Checking...") if installed else tr("Install"))
        button.setFixedSize(140, 36)
        button.setEnabled(not installed)
        if installed:
            meta = instances.read_meta(instance_name)
            threading.Thread(
                target=self.t_check_existing_update,
                args=(button, installed_path, meta.get("version", ""), meta.get("loader", ""), self.ptype),
                daemon=True,
            ).start()
        else:
            button.clicked.connect(lambda _, h=hit, b=button: self.install(h, b))

        row.addWidget(icon, 0, Qt.AlignVCenter)
        row.addLayout(column, 1)
        row.addWidget(button, 0, Qt.AlignVCenter)
        self.list.insertWidget(self.list.count() - 1, card)

    def t_check_existing_update(self, button, path, version, loader, ptype):
        info = None
        error = ""
        try:
            info = content_updates.latest_update_for_file(path, version, loader, ptype)
        except Exception as exc:
            error = str(exc)
        self.bridge.update_checked.emit(button, path, info, error)

    def on_update_checked(self, button, path, info, error):
        try:
            if info:
                button.setText(tr("Update"))
                button.setEnabled(True)
                button.set_color(None)
                button.clicked.connect(
                    lambda _, b=button, p=path, item=info: self.update_existing(b, p, item)
                )
            else:
                button.setText(tr("Installed"))
                button.setEnabled(False)
        except RuntimeError:
            return
        if error and any(marker in error.lower() for marker in NETWORK_ERROR_MARKERS):
            self.status.setText(tr("Check your Internet connection"))

    def update_existing(self, button, path, info):
        button.setEnabled(False)
        button.setText("...")
        threading.Thread(
            target=self.t_update_existing,
            args=(button, path, info),
            daemon=True,
        ).start()

    def t_update_existing(self, button, path, info):
        try:
            content_updates.apply_update(path, info)
            self.bridge.update_done.emit(button, "", path)
        except Exception:
            self.bridge.update_done.emit(button, "Update Error", path)

    def on_update_done(self, button, error, path):
        if error:
            sound.error()
            label = tr("Update Error")
            self.status.setText(label)
        else:
            sound.completed()
            label = tr("Installed")
            self.status.setText(tr("Updated"))
        try:
            button.setText(label)
            button.setEnabled(bool(error))
        except RuntimeError:
            pass

    def install(self, hit, button):
        name = self.inst.currentData()
        if not name:
            self.status.setText(tr("Select an instance"))
            return
        meta = instances.read_meta(name)
        button.setEnabled(False)
        button.setText("...")
        args = (
            self.source,
            hit,
            button,
            self.ptype,
            meta["version"],
            meta["loader"],
            name,
        )
        threading.Thread(target=self.t_install, args=args, daemon=True).start()

    def t_install(self, source, hit, button, ptype, version, loader, name):
        try:
            if source != "modrinth":
                raise RuntimeError("CurseForge is temporarily unavailable")
            modrinth.install(
                hit["project_id"], ptype, version, loader,
                instances.instance_path(name),
            )
            self.bridge.done.emit(button, "")
        except Exception:
            self.bridge.done.emit(button, "Installation Error")

    def on_done(self, button, err):
        if err:
            sound.error()
            label = tr("Installation Error")
        else:
            sound.completed()
            label = tr("Installed")

        try:
            button.setText(label)
            button.setEnabled(bool(err))
        except RuntimeError:
            pass

        self.status.setText(tr("Installation Error") if err else "")
