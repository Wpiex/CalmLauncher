import ctypes
from ctypes import wintypes
from PySide6.QtCore import QPoint
from PySide6.QtGui import QPolygon

def notch(r, n=4):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    return QPolygon([
        QPoint(x + n, y), QPoint(x + w - n, y), QPoint(x + w - n, y + n), QPoint(x + w, y + n),
        QPoint(x + w, y + h - n), QPoint(x + w - n, y + h - n), QPoint(x + w - n, y + h),
        QPoint(x + n, y + h), QPoint(x + n, y + h - n), QPoint(x, y + h - n), QPoint(x, y + n),
        QPoint(x + n, y + n)])

class BLURBEHIND(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Enable", wintypes.BOOL),
                ("Region", ctypes.c_void_p), ("Transition", wintypes.BOOL)]

def unblur(hwnd):
    dwm = ctypes.windll.dwmapi
    dwm.DwmEnableBlurBehindWindow.argtypes = [ctypes.c_void_p, ctypes.POINTER(BLURBEHIND)]
    bb = BLURBEHIND(1, False, None, False)
    dwm.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))

def blur(hwnd, w, h, dpr, n):
    w, h, n = round(w * dpr), round(h * dpr), max(1, round(n * dpr))
    pts = [(n, 0), (w - n, 0), (w - n, n), (w, n), (w, h - n), (w - n, h - n),
           (w - n, h), (n, h), (n, h - n), (0, h - n), (0, n), (n, n)]
    arr = (wintypes.POINT * len(pts))(*[wintypes.POINT(x, y) for x, y in pts])
    gdi = ctypes.windll.gdi32
    gdi.CreatePolygonRgn.restype = ctypes.c_void_p
    gdi.CreatePolygonRgn.argtypes = [ctypes.POINTER(wintypes.POINT), ctypes.c_int, ctypes.c_int]
    rgn = gdi.CreatePolygonRgn(arr, len(pts), 1)
    dwm = ctypes.windll.dwmapi
    dwm.DwmEnableBlurBehindWindow.argtypes = [ctypes.c_void_p, ctypes.POINTER(BLURBEHIND)]
    bb = BLURBEHIND(3, True, rgn, False)
    dwm.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))
    dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    pref = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)