import math
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QImage, QTransform
from PySide6.QtWidgets import QWidget

def normalize(img):
    img = img.convertToFormat(QImage.Format_ARGB32)
    if img.height() != 32:
        return img
    out = QImage(64, 64, QImage.Format_ARGB32)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.drawImage(0, 0, img)
    painter.drawImage(16, 48, img.copy(0, 16, 16, 16).mirrored(True, False))
    painter.drawImage(32, 48, img.copy(40, 16, 16, 16).mirrored(True, False))
    painter.end()
    return out

def parts(slim):
    arm_width = 3 if slim else 4
    return [
        ((0, 28, 0), (8, 8, 8), (0, 0), (32, 0), 0.5),
        ((0, 18, 0), (8, 12, 4), (16, 16), (16, 32), 0.25),
        ((-(4 + arm_width / 2), 18, 0), (arm_width, 12, 4), (40, 16), (40, 32), 0.25),
        ((4 + arm_width / 2, 18, 0), (arm_width, 12, 4), (32, 48), (48, 48), 0.25),
        ((-2, 6, 0), (4, 12, 4), (0, 16), (0, 32), 0.25),
        ((2, 6, 0), (4, 12, 4), (16, 48), (0, 48), 0.25),
    ]

def box(c, size, gap, uv):
    cx, cy, cz = c
    width, height, depth = size
    u, v = uv
    half_width = width / 2 + gap
    half_height = height / 2 + gap
    half_depth = depth / 2 + gap
    x0, x1 = cx - half_width, cx + half_width
    y0, y1 = cy - half_height, cy + half_height
    z0, z1 = cz - half_depth, cz + half_depth
    full_width, full_height, full_depth = 2 * half_width, 2 * half_height, 2 * half_depth
    return [
        ((x0, y1, z1), (full_width, 0, 0), (0, -full_height, 0), (u + depth, v + depth, width, height), (0, 0, 1)),
        ((x1, y1, z0), (-full_width, 0, 0), (0, -full_height, 0), (u + 2 * depth + width, v + depth, width, height), (0, 0, -1)),
        ((x0, y1, z0), (0, 0, full_depth), (0, -full_height, 0), (u, v + depth, depth, height), (-1, 0, 0)),
        ((x1, y1, z1), (0, 0, -full_depth), (0, -full_height, 0), (u + depth + width, v + depth, depth, height), (1, 0, 0)),
        ((x0, y1, z0), (full_width, 0, 0), (0, 0, full_depth), (u + depth, v, width, depth), (0, 1, 0)),
        ((x0, y0, z1), (full_width, 0, 0), (0, 0, -full_depth), (u + depth + width, v, width, depth), (0, -1, 0)),
    ]

class SkinView(QWidget):
    def __init__(self):
        super().__init__()
        self.img = None
        self.slim = False
        self.yaw = 25.0
        self.pitch = 12.0
        self.drag = None
        self.setMinimumSize(220, 300)
        self.setCursor(Qt.OpenHandCursor)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

    def set_skin(self, img, slim):
        self.img = normalize(img)
        self.slim = slim
        self.update()

    def tick(self):
        if self.drag is None:
            self.yaw = (self.yaw + 0.8) % 360
            self.update()

    def showEvent(self, event):
        self.timer.start(33)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        self.drag = event.position()
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag is None:
            return
        delta = event.position() - self.drag
        self.drag = event.position()
        self.yaw = (self.yaw + delta.x() * 0.8) % 360
        self.pitch = max(-40.0, min(40.0, self.pitch + delta.y() * 0.5))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.drag = None
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def paintEvent(self, event):
        if self.img is None:
            return
        painter = QPainter(self)
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)

        def rotate(x, y, z):
            x, z = x * cos_yaw + z * sin_yaw, -x * sin_yaw + z * cos_yaw
            return x, y * cos_pitch - z * sin_pitch, y * sin_pitch + z * cos_pitch

        scale = min(self.width() / 20.0, self.height() / 36.0)
        origin_x, origin_y = self.width() / 2, self.height() / 2
        faces = []
        for center, size, uv, outer_uv, gap in parts(self.slim):
            for layer, (texture, layer_gap) in enumerate(((uv, 0), (outer_uv, gap))):
                for point, u_vec, v_vec, rect, normal in box(center, size, layer_gap, texture):
                    if rotate(*normal)[2] <= 0:
                        continue
                    a = rotate(point[0], point[1] - 16, point[2])
                    b = rotate(
                        point[0] + u_vec[0],
                        point[1] + u_vec[1] - 16,
                        point[2] + u_vec[2],
                    )
                    d = rotate(
                        point[0] + v_vec[0],
                        point[1] + v_vec[1] - 16,
                        point[2] + v_vec[2],
                    )
                    faces.append(((b[2] + d[2]) / 2 + layer * 0.01, a, b, d, rect))

        faces.sort(key=lambda face: face[0])
        for _, a, b, d, (tx, ty, tw, th) in faces:
            ax, ay = origin_x + a[0] * scale, origin_y - a[1] * scale
            bx, by = origin_x + b[0] * scale, origin_y - b[1] * scale
            cx, cy = origin_x + d[0] * scale, origin_y - d[1] * scale
            m11, m12 = (bx - ax) / tw, (by - ay) / tw
            m21, m22 = (cx - ax) / th, (cy - ay) / th
            painter.setTransform(
                QTransform(
                    m11, m12, m21, m22,
                    ax - tx * m11 - ty * m21,
                    ay - tx * m12 - ty * m22,
                )
            )
            rect = QRectF(tx, ty, tw, th)
            painter.drawImage(rect, self.img, rect)
