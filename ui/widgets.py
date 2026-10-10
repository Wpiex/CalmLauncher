import math
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QPolygon, QRegion, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import QWidget, QPushButton, QComboBox, QCheckBox, QGraphicsDropShadowEffect
from ui.effects import notch
from ui import sound, theme

class Button(QPushButton):
    def __init__(self, text, color=None):
        super().__init__(text)
        self.color = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.pressed.connect(sound.click)
        fx = QGraphicsDropShadowEffect(self)
        fx.setBlurRadius(0)
        fx.setOffset(0, 4)
        fx.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(fx)

    def set_color(self, color):
        self.color = color
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        base = QColor(*(self.color or theme.accent()))
        if not self.isEnabled():
            c = QColor(90, 90, 90)
        elif self.isDown():
            c = base.darker(120)
        elif self.underMouse():
            c = base.lighter(115)
        else:
            c = base
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPolygon(notch(r))
        p.setPen(QColor(0, 0, 0, 120))
        p.drawText(r.translated(2, 2), Qt.AlignCenter, self.text())
        p.setPen(QColor(255, 255, 255) if self.isEnabled() else QColor(170, 170, 170))
        p.drawText(r, Qt.AlignCenter, self.text())

class IconButton(Button):
    def __init__(self, path, color=None):
        super().__init__("", color)
        self.pix = QPixmap(path)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.pix.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        area = self.rect().adjusted(8, 8, -8, -8)
        scaled = self.pix.scaled(area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = area.x() + (area.width() - scaled.width()) // 2
        y = area.y() + (area.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)

class Panel(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*theme.panel(), theme.panel_alpha()))
        p.drawPolygon(notch(self.rect()))

class Card(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*theme.card()))
        p.drawPolygon(notch(self.rect()))

class Icon(QWidget):
    def __init__(self, size=48):
        super().__init__()
        self.setFixedSize(size, size)
        self.pix = None

    def set_pixmap(self, pix):
        self.pix = pix
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = self.rect()
        p.setClipRegion(QRegion(notch(r)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*theme.field()))
        p.drawRect(r)
        if self.pix:
            p.drawPixmap(r, self.pix)

class Select(QComboBox):
    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setMaxVisibleItems(10)

    def mousePressEvent(self, e):
        sound.click()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        x = self.width() - 24
        y = self.height() // 2 - 3
        p.drawPolygon(QPolygon([QPoint(x, y), QPoint(x + 10, y), QPoint(x + 5, y + 6)]))

class Check(QCheckBox):
    def __init__(self, text, wrap=False):
        super().__init__(text)
        self.wrap = wrap
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52 if wrap else 32)
        self.clicked.connect(sound.click)

    def paintEvent(self, e):
        p = QPainter(self)
        box = QRect(0, (self.height() - 24) // 2, 24, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*theme.accent()) if self.isChecked() else QColor(*theme.field()))
        p.drawPolygon(notch(box))
        if self.isChecked():
            p.setBrush(QColor(255, 255, 255))
            p.drawRect(box.adjusted(8, 8, -8, -8))
        p.setPen(QColor(255, 255, 255))
        flags = int(Qt.AlignVCenter.value | Qt.AlignLeft.value | (Qt.TextWordWrap.value if self.wrap else 0))
        p.drawText(QRect(36, 0, self.width() - 36, self.height()), flags, self.text())

class Credit(QWidget):
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.t = 0.0
        f = QFont(self.font())
        f.setPointSize(8)
        self.setFont(f)
        fm = QFontMetrics(f)
        self.setFixedSize(fm.horizontalAdvance(text) + 4, fm.height())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

    def tick(self):
        self.t += 0.15
        self.update()

    def showEvent(self, e):
        self.timer.start(40)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(self.font())
        fm = p.fontMetrics()
        x = 0
        for i, ch in enumerate(self.text):
            a = 60 + int(80 * (math.sin(self.t - i * 0.4) + 1) / 2)
            p.setPen(QColor(255, 255, 255, a))
            p.drawText(x, fm.ascent(), ch)
            x += fm.horizontalAdvance(ch)