import os
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from constants import CLICK, SLIDER, COMPLETED, ERROR

class Pool:
    def __init__(self, path, size):
        self.path = path
        self.size = size
        self.items = []
        self.i = 0

    def make(self):
        out = QAudioOutput()
        out.setVolume(0.6)
        pl = QMediaPlayer()
        pl.setAudioOutput(out)
        pl.setSource(QUrl.fromLocalFile(self.path))
        self.items.append((pl, out))

    def play(self):
        if not os.path.exists(self.path):
            return
        if not self.items:
            for _ in range(self.size):
                self.make()
        pl = self.items[self.i][0]
        self.i = (self.i + 1) % self.size
        pl.stop()
        pl.play()

_click = Pool(CLICK, 6)
_slider = Pool(SLIDER, 10)
_completed = Pool(COMPLETED, 2)
_error = Pool(ERROR, 2)

def click():
    _click.play()

def slider():
    _slider.play()

def completed():
    _completed.play()

def error():
    _error.play()