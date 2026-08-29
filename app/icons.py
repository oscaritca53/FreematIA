"""
Set de íconos propios para la barra de herramientas, dibujados a mano con
QPainter (formas y colores planos). Están inspirados en la disposición
visual general de la barra de FreeMat (colores cálidos para archivo,
azul para guardar, rojo para controles de ejecución, verde para
stop/subir carpeta) pero son arte vectorial original, no una copia de
los íconos reales de FreeMat.
"""
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon
from PySide6.QtCore import Qt, QPoint, QRect

SIZE = 22


def _icon(draw_fn):
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_fn(p)
    p.end()
    return QIcon(pm)


def new_script():
    def draw(p):
        p.setPen(QPen(QColor("#9c7a2e"), 1))
        p.setBrush(QBrush(QColor("#fdf3d3")))
        p.drawPolygon(QPolygon([QPoint(4, 2), QPoint(14, 2), QPoint(18, 6), QPoint(18, 20), QPoint(4, 20)]))
        p.setBrush(QBrush(QColor("#eddca0")))
        p.drawPolygon(QPolygon([QPoint(14, 2), QPoint(18, 6), QPoint(14, 6)]))
        p.setPen(QPen(QColor("#9c7a2e"), 1))
        for y in (10, 13, 16):
            p.drawLine(7, y, 15, y)
    return _icon(draw)


def open_folder():
    def draw(p):
        p.setPen(QPen(QColor("#a06b1a"), 1))
        p.setBrush(QBrush(QColor("#f6b93b")))
        p.drawRect(3, 8, 16, 10)
        p.setBrush(QBrush(QColor("#ffd873")))
        p.drawPolygon(QPolygon([QPoint(3, 8), QPoint(7, 4), QPoint(13, 4), QPoint(15, 8)]))
    return _icon(draw)


def save():
    def draw(p):
        p.setPen(QPen(QColor("#2a5d9f"), 1))
        p.setBrush(QBrush(QColor("#5b9bd5")))
        p.drawRoundedRect(3, 3, 16, 16, 2, 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawRect(6, 3, 10, 6)
        p.setBrush(QBrush(QColor("#2a5d9f")))
        p.drawRect(7, 13, 8, 5)
    return _icon(draw)


def copy_icon():
    def draw(p):
        p.setPen(QPen(QColor("#7f8c8d"), 1))
        p.setBrush(QBrush(QColor("#ecf0f1")))
        p.drawRect(3, 3, 12, 14)
        p.setBrush(QBrush(QColor("white")))
        p.drawRect(7, 6, 12, 14)
        p.setPen(QPen(QColor("#95a5a6"), 1))
        for y in (10, 13, 16):
            p.drawLine(9, y, 16, y)
    return _icon(draw)


def paste_icon():
    def draw(p):
        p.setPen(QPen(QColor("#8a6d3b"), 1))
        p.setBrush(QBrush(QColor("#d9c48a")))
        p.drawRoundedRect(4, 2, 6, 3, 1, 1)
        p.setPen(QPen(QColor("#7f8c8d"), 1))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRoundedRect(3, 4, 16, 16, 2, 2)
        p.setPen(QPen(QColor("#bdc3c7"), 1))
        for y in (9, 12, 15, 18):
            p.drawLine(6, y, 17, y)
    return _icon(draw)


def terminal_icon():
    def draw(p):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#2c3e50")))
        p.drawRoundedRect(2, 3, 18, 16, 2, 2)
        pen = QPen(QColor("#2ecc71"), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(6, 9, 10, 12)
        p.drawLine(6, 15, 10, 12)
        p.drawLine(12, 15, 16, 15)
    return _icon(draw)


def pause_icon():
    def draw(p):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#c0392b")))
        p.drawRect(6, 4, 4, 14)
        p.drawRect(13, 4, 4, 14)
    return _icon(draw)


def step_icon():
    def draw(p):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#c0392b")))
        p.drawRect(9, 3, 3, 9)
        p.drawPolygon(QPolygon([QPoint(5, 12), QPoint(17, 12), QPoint(11, 19)]))
    return _icon(draw)


def stop_icon():
    def draw(p):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#27ae60")))
        p.drawRect(5, 5, 12, 12)
    return _icon(draw)


def loop_arrow_icon(flip=False):
    def draw(p):
        pen = QPen(QColor("#2e86c1"), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        rect = QRect(3, 3, 16, 16)
        start = 150 * 16 if flip else 30 * 16
        p.drawArc(rect, start, 260 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#2e86c1")))
        if flip:
            p.drawPolygon(QPolygon([QPoint(6, 5), QPoint(2, 7), QPoint(6, 10)]))
        else:
            p.drawPolygon(QPolygon([QPoint(16, 5), QPoint(20, 7), QPoint(16, 10)]))
    return _icon(draw)


def up_arrow_icon():
    def draw(p):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#27ae60")))
        p.drawEllipse(2, 2, 18, 18)
        p.setBrush(QBrush(QColor("white")))
        p.drawPolygon(QPolygon([
            QPoint(11, 5), QPoint(16, 11), QPoint(13, 11),
            QPoint(13, 17), QPoint(9, 17), QPoint(9, 11), QPoint(6, 11),
        ]))
    return _icon(draw)
