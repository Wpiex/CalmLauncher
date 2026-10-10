import os
import threading
from PySide6.QtCore import Qt, QUrl, QPoint, Signal, QObject
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QFrame, QMenu,
                               QMessageBox, QInputDialog, QFileDialog)
from core import instances, content_updates
from ui.widgets import Button, Panel, Card, Icon
from ui import sound
from ui.i18n import tr, bind, ask
from core.loaders import LOADERS

class ContentUpdateBridge(QObject):
    checked = Signal(str, object, str)
    finished = Signal(str, int, int)

class InstancesPage(Panel):
    def __init__(self, icon, on_play, on_install):
        super().__init__()
        self.update_bridge = ContentUpdateBridge()
        self.update_bridge.checked.connect(self.on_content_updates_checked)
        self.update_bridge.finished.connect(self.on_content_updates_finished)
        self.default = icon.pixmap(128, 128)
        self.on_play = on_play
        self.busy = False
        self.play_btns = []
        self.row_buttons = []
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(10)
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
        self.empty = bind(QLabel(), "There's no Instances")
        self.empty.setAlignment(Qt.AlignCenter)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.install_btn = bind(Button("Install"), "Install")
        self.install_btn.clicked.connect(on_install)
        l.addWidget(self.scroll, 1)
        l.addWidget(self.empty, 1)
        l.addWidget(self.status)
        l.addWidget(self.install_btn)
        self.refresh()

    def set_status(self, text):
        self.status.setText(text)

    def set_busy(self, busy):
        self.busy = busy

        for button in self.row_buttons:
            try:
                button.setEnabled(not busy)
            except RuntimeError:
              pass

        self.install_btn.setEnabled(not busy)

    def refresh(self):
        self.play_btns = []
        self.row_buttons = []
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        names = instances.list_instances()
        for n in names:
            self.add_row(n)
        has = bool(names)
        self.scroll.setVisible(has)
        self.empty.setVisible(not has)
        self.install_btn.setVisible(not has)

    def add_row(self, name):
        pending = name in instances.INSTALLING
        c = Card()
        row = QHBoxLayout(c)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(12)
        icon = Icon(44)
        ip = None if pending else instances.icon_path(name)
        pix = QPixmap(ip) if ip else QPixmap()
        icon.set_pixmap(pix if not pix.isNull() else self.default)
        col = QVBoxLayout()
        col.setSpacing(2)
        if pending:
            col.addWidget(QLabel(tr("Unnamed")))
        else:
            meta = instances.read_meta(name)
            sub = QLabel(f'{meta["version"]} - {LOADERS.get(meta["loader"], meta["loader"])}')
            col.addWidget(QLabel(instances.title(name)))
            col.addWidget(sub)
        play = Button(tr("Play"))
        play.setFixedSize(90, 36)
        dots = Button("...")
        dots.setFixedSize(44, 36)
        row.addWidget(icon, 0, Qt.AlignVCenter)
        row.addLayout(col, 1)
        row.addWidget(play, 0, Qt.AlignVCenter)
        row.addWidget(dots, 0, Qt.AlignVCenter)
        self.list.insertWidget(self.list.count() - 1, c)
        if pending:
            play.setEnabled(False)
            dots.setEnabled(False)
            return
        play.setEnabled(not self.busy)
        play.clicked.connect(lambda _, n=name: self.on_play(n))
        self.play_btns.append(play)
        dots.clicked.connect(lambda _, n=name, b=dots: self.menu(n, b))
        dots.setEnabled(not self.busy)
        self.row_buttons.extend((play, dots))

    def menu(self, name, btn):
        m = QMenu(self)
        a_rename = m.addAction(tr("Rename"))
        a_icon = m.addAction(tr("Change Icon"))
        a_reset = m.addAction(tr("Reset Icon"))
        a_reset.setEnabled(bool(instances.icon_path(name)))
        a_mods = m.addAction(tr("Open Mods Folder"))
        a_updates = m.addAction(tr("Check for Content updates"))
        a_delete = m.addAction(tr("Delete"))
        pos = btn.mapToGlobal(QPoint(btn.width() - m.sizeHint().width(), btn.height()))
        act = m.exec(pos)
        if not act:
            return
        sound.click()
        if act is a_rename:
            self.rename(name)
        elif act is a_icon:
            self.change_icon(name)
        elif act is a_reset:
            self.reset_icon(name)
        elif act is a_mods:
            QDesktopServices.openUrl(QUrl.fromLocalFile(instances.mods_dir(name)))
        elif act is a_updates:
            self.check_content_updates(name)
        elif act is a_delete:
            self.delete(name)

    def check_content_updates(self, name):
        if self.busy:
            return
        self.set_busy(True)
        self.status.setText(tr("Checking content updates..."))
        threading.Thread(
            target=self.t_check_content_updates,
            args=(name,),
            daemon=True,
        ).start()

    def t_check_content_updates(self, name):
        updates = []
        error = ""
        try:
            meta = instances.read_meta(name)
            root = instances.instance_path(name)
            updates = content_updates.check_instance(
                root,
                meta.get("version", ""),
                meta.get("loader", ""),
            )
        except Exception as exc:
            error = str(exc)
        self.update_bridge.checked.emit(name, updates, error)

    def on_content_updates_checked(self, name, updates, error):
        self.set_busy(False)
        if error:
            lowered = error.lower()
            if any(marker in lowered for marker in (
                "connection", "timeout", "timed out", "network", "ssl", "dns",
                "urlopenerror", "failed to establish", "connectionerror", "http error",
            )):
                self.status.setText(tr("Check your Internet connection"))
            else:
                self.status.setText(tr("Content update check failed"))
            return

        if not updates:
            self.status.setText(tr("No content updates found"))
            return

        lines = []
        for item in updates:
            filename = os.path.basename(item["path"])
            version = item["update"].get("version_number", "latest")
            lines.append(f"{filename}  →  {version}")

        message = tr("Updates available:\n\n{}\n\nInstall these updates?").format("\n".join(lines))
        if not ask(self, "Content updates", message):
            self.status.setText(tr("Update cancelled"))
            return

        self.set_busy(True)
        self.status.setText(tr("Updating content..."))
        threading.Thread(
            target=self.t_apply_content_updates,
            args=(name, updates),
            daemon=True,
        ).start()

    def t_apply_content_updates(self, name, updates):
        succeeded = 0
        failed = 0
        for item in updates:
            try:
                content_updates.apply_update(item["path"], item["update"])
                succeeded += 1
            except Exception:
                failed += 1
        self.update_bridge.finished.emit(name, succeeded, failed)

    def on_content_updates_finished(self, name, succeeded, failed):
        self.set_busy(False)
        self.refresh()
        if failed and succeeded:
            self.status.setText(tr("Updated {}; failed: {}").format(succeeded, failed))
        elif failed:
            self.status.setText(tr("Update Error"))
        elif succeeded:
            self.status.setText(tr("Updated {} content item(s)").format(succeeded))
        else:
            self.status.setText(tr("No content updates found"))

    def rename(self, name):
        text, ok = QInputDialog.getText(self, tr("Rename"), tr("Name"), text=instances.title(name))
        text = text.strip()
        if not ok or not text:
            return
        metadata = instances.read_meta(name)
        metadata["title"] = text
        instances.save_meta(name, metadata)
        self.refresh()

    def change_icon(self, name):
        path, _ = QFileDialog.getOpenFileName(self, tr("Icon"), "", "Images (*.png *.jpg *.jpeg *.ico)")
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            self.status.setText(tr("Invalid image"))
            return
        pix = pix.scaled(128, 128, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        pix = pix.copy((pix.width() - 128) // 2, (pix.height() - 128) // 2, 128, 128)
        pix.save(os.path.join(instances.instance_path(name), "icon.png"), "PNG")
        self.status.setText("")
        self.refresh()

    def reset_icon(self, name):
        p = instances.icon_path(name)
        if p:
            try:
                os.remove(p)
            except OSError as e:
                self.status.setText(str(e))
        self.refresh()

    def delete(self, name):
        if not ask(self, "Delete", tr("Delete {} with all its data?").format(instances.title(name))):
            return
        try:
            instances.delete_instance(name)
        except Exception as e:
            self.status.setText(str(e))
            return
        self.refresh()
