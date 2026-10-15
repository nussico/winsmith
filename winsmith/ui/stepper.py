"""Top navigation: numbered steps joined by lines, each with a label and a short status underneath."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import T, font

DOT, TOP, MIN_COL, STATUS_COL = 28, 8, 64, 90


class Stepper(QWidget):
    """Every step owns an equal column, so the dots never move when the active step or a status changes.
    Status kinds: 'ok' (green check), 'info' (accent text), 'error' (red !), '' (muted text)."""
    selected = Signal(str)

    def __init__(self, names):
        super().__init__()
        self.names = names
        self.status = {n: ("", "") for n in names}
        self.active = names[0]
        self.hovered = None
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(78)
        self.setMinimumWidth(len(names) * MIN_COL)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_status(self, name, text, kind=""):
        if self.status[name] != (text, kind):
            self.status[name] = (text, kind)
            self.update()

    def select(self, name):
        self.active = name
        self.update()

    def column(self, name):
        w = self.width() / len(self.names)
        return QRectF(self.names.index(name) * w, 0, w, self.height())

    def dot_rect(self, name):
        c = self.column(name).center().x()
        return QRectF(c - DOT / 2, TOP, DOT, DOT)

    def _hit(self, pos):
        for n in self.names:
            if self.column(n).contains(pos):
                return n
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self.hovered:
            self.hovered = h
            self.update()
            self.setToolTip(h or "")

    def leaveEvent(self, e):
        self.hovered = None
        self.update()

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h:
            self.selected.emit(h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        bold, small = font(10, QFont.DemiBold), font(8.5)
        fm, sm = QFontMetrics(bold), QFontMetrics(small)
        active_i = self.names.index(self.active)
        cy = TOP + DOT / 2

        for i, n in enumerate(self.names[:-1]):  # connecting lines first, under the dots
            a, b = self.dot_rect(n), self.dot_rect(self.names[i + 1])
            p.setPen(QPen(QColor(T["accent"] if i < active_i else T["border_strong"]), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(a.right() + 8, cy), QPointF(b.left() - 8, cy))

        for i, n in enumerate(self.names, 1):
            col, dot = self.column(n), self.dot_rect(n)
            text, kind = self.status[n]
            is_active = n == self.active
            if n == self.hovered and not is_active:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T["hover"]))
                p.drawEllipse(dot.adjusted(-4, -4, 4, 4))
            if is_active:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T["accent"]))
            elif kind == "ok":
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T["success"]))
            else:
                p.setPen(QPen(QColor(T["border_strong"]), 1.5))
                p.setBrush(QColor(T["surface"]))
            p.drawEllipse(dot.adjusted(1, 1, -1, -1))
            if kind == "ok" and not is_active:
                p.setPen(QPen(QColor(T["surface"]), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                c = dot.center()
                path = QPainterPath(QPointF(c.x() - 5, c.y()))
                path.lineTo(c.x() - 1.5, c.y() + 3.5)
                path.lineTo(c.x() + 5, c.y() - 3.5)
                p.drawPath(path)
            else:
                p.setFont(bold)
                p.setPen(QColor(T["on_accent"] if is_active else T["muted"]))
                p.drawText(dot, Qt.AlignCenter, str(i))
            if kind == "error":  # small red badge on the dot
                b = QRectF(dot.right() - 9, dot.top() - 3, 13, 13)
                p.setPen(QPen(QColor(T["surface"]), 2))
                p.setBrush(QColor(T["danger"]))
                p.drawEllipse(b)
                p.setPen(QColor("#FFFFFF"))
                p.setFont(font(7, QFont.Bold))
                p.drawText(b, Qt.AlignCenter, "!")

            room = int(col.width()) - 8
            y = dot.bottom() + 6
            p.setFont(bold)
            p.setPen(QColor(T["text"] if is_active or n == self.hovered else T["muted"]))
            p.drawText(QRectF(col.left() + 4, y, room, fm.height()), Qt.AlignHCenter | Qt.AlignTop,
                       fm.elidedText(n, Qt.ElideRight, room))
            if text and col.width() >= STATUS_COL:
                p.setFont(small)
                p.setPen(QColor({"ok": T["success"], "info": T["accent"], "error": T["danger"]}.get(kind, T["muted"])))
                p.drawText(QRectF(col.left() + 4, y + fm.height(), room, sm.height()), Qt.AlignHCenter | Qt.AlignTop,
                           sm.elidedText(text, Qt.ElideRight, room))
