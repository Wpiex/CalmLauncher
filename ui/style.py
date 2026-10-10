from ui import theme

TEMPLATE = """
QLabel{color:white;}
QLineEdit{background:%FIELD%;border:2px solid %BORDER%;color:white;padding:8px;selection-background-color:%ACCENT%;}
QLineEdit:focus{border:2px solid %ACCENT%;}
QComboBox{background:%FIELD%;border:2px solid %BORDER%;color:white;padding:8px;}
QComboBox:focus{border:2px solid %ACCENT%;}
QComboBox::drop-down{border:none;width:28px;}
QComboBox::down-arrow{image:none;}
QComboBox QAbstractItemView{background:%FIELD%;color:white;border:2px solid %BORDER%;selection-background-color:%ACCENT%;outline:none;}
QSlider::groove:horizontal{height:8px;background:%FIELD%;}
QSlider::sub-page:horizontal{background:%ACCENT%;}
QSlider::handle:horizontal{background:white;width:12px;margin:-4px 0;}
QProgressBar{background:%FIELD%;border:none;height:12px;color:transparent;}
QProgressBar::chunk{background:%ACCENT%;}
QScrollArea{background:transparent;border:none;}
QScrollArea>QWidget{background:transparent;}
QScrollArea>QWidget>QWidget{background:transparent;}
QScrollBar:vertical{background:%FIELD%;width:8px;margin:0;border:none;}
QScrollBar::handle:vertical{background:%ACCENT%;min-height:24px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}
QMenu{background:%MENU%;border:2px solid %BORDER%;color:white;padding:4px;}
QMenu::item{padding:8px 24px;}
QMenu::item:selected{background:%ACCENT%;}
QMessageBox{background:%MENU%;}
QMessageBox QLabel{color:white;}
QMessageBox QPushButton{background:%ACCENT%;color:white;border:none;padding:8px 16px;min-width:64px;}
QMessageBox QPushButton:hover{background:%ACCENT_HOVER%;}
QInputDialog{background:%MENU%;}
QInputDialog QLabel{color:white;}
QInputDialog QPushButton{background:%ACCENT%;color:white;border:none;padding:8px 16px;min-width:64px;}
QInputDialog QPushButton:hover{background:%ACCENT_HOVER%;}
QColorDialog{background:%MENU%;}
QColorDialog QLabel{color:white;}
QColorDialog QSpinBox{background:%FIELD%;color:white;border:2px solid %BORDER%;}
QColorDialog QPushButton{background:%ACCENT%;color:white;border:none;padding:8px 16px;min-width:64px;}
QColorDialog QPushButton:hover{background:%ACCENT_HOVER%;}
"""

def build_style():
    a = theme.accent()
    pairs = (("%ACCENT_HOVER%", theme.shade(a, 25)), ("%ACCENT%", a), ("%FIELD%", theme.field()),
             ("%BORDER%", theme.border()), ("%MENU%", theme.bg()))
    s = TEMPLATE
    for k, c in pairs:
        s = s.replace(k, theme.css(c))
    return s