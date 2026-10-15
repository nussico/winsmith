"""Reusable widgets. Colors always come from theme.T so they follow light/dark mode."""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from .theme import T


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def set_prop(w, name, value):
    if w.property(name) != value:
        w.setProperty(name, value)
        repolish(w)


def label(text="", role=None, wrap=False):
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def button(text, command=None, kind="secondary", big=False):
    b = QPushButton(text)
    b.setProperty("kind", kind)
    b.setProperty("big", big)
    b.setCursor(Qt.PointingHandCursor)
    if command:
        b.clicked.connect(command)
    return b


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor.fromRgbF(*(x + (y - x) * t for x, y in zip(a.getRgbF()[:3], b.getRgbF()[:3])))


def animation(parent, ms, on_value, start=0.0, end=1.0, curve=QEasingCurve.OutCubic):
    a = QVariantAnimation(parent)
    a.setDuration(ms)
    a.setStartValue(float(start))
    a.setEndValue(float(end))
    a.setEasingCurve(curve)
    a.valueChanged.connect(on_value)
    return a


def vbox(parent=None, spacing=0, margins=(0, 0, 0, 0)):
    lay = QVBoxLayout(parent) if parent is not None else QVBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def hbox(parent=None, spacing=0, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout(parent) if parent is not None else QHBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


# ---------------------------------------------------------------- inputs

class Switch(QAbstractButton):
    """Pill switch with an animated knob and a focus ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(44, 24)
        self.pos_ = 0.0
        self.hover = False
        self.anim = animation(self, 160, self._set_pos)
        self.toggled.connect(self._go)

    def _set_pos(self, v):
        self.pos_ = v
        self.update()

    def _go(self, on):
        self.anim.stop()
        self.anim.setStartValue(self.pos_)
        self.anim.setEndValue(1.0 if on else 0.0)
        self.anim.start()

    def jump(self):
        self.anim.stop()
        self._set_pos(1.0 if self.isChecked() else 0.0)

    def set_hover(self, on):
        self.hover = on
        self.update()

    def enterEvent(self, e):
        self.set_hover(True)

    def leaveEvent(self, e):
        self.set_hover(False)

    def sizeHint(self):
        return QSize(44, 24)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(2, 2, 40, 20)
        if self.hasFocus():
            p.setPen(QPen(QColor(T["accent"]), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, 42, 22), 11, 11)
        off = T["border_strong"] if not self.hover else T["faint"]
        on = T["accent_hover"] if self.hover else T["accent"]
        p.setPen(Qt.NoPen)
        p.setBrush(mix(off, on, self.pos_))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 9, 9)
        k = 14
        x = r.left() + 4 + (r.width() - k - 8) * self.pos_
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, r.top() + 3, k, k))


class ToggleRow(QWidget):
    """Title + optional description on the left, switch on the right. Click anywhere on the row."""

    def __init__(self, text, desc=None, checked=False):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        lay = hbox(self, 16)
        col = vbox(spacing=2)
        self.title = label(text, wrap=True)
        col.addWidget(self.title)
        if desc:
            col.addWidget(label(desc, "small", wrap=True))
        lay.addLayout(col, 1)
        self.switch = Switch()
        self.switch.setChecked(checked)
        self.switch.jump()
        self.switch.setAccessibleName(text)
        lay.addWidget(self.switch, 0, Qt.AlignTop)
        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.toggled = self.switch.toggled

    def isChecked(self):
        return self.switch.isChecked()

    def setChecked(self, on):
        self.switch.setChecked(on)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.switch.toggle()

    def enterEvent(self, e):
        self.switch.set_hover(True)

    def leaveEvent(self, e):
        self.switch.set_hover(False)


class Combo(QComboBox):
    """Combo box that leaves the mouse wheel to the page, with a drawn chevron."""

    def __init__(self, items=(), editable=False):
        super().__init__()
        self.setEditable(editable)
        self.setMaxVisibleItems(12)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        for it in items:
            if isinstance(it, tuple):
                self.addItem(*it)
            else:
                self.addItem(it)

    def wheelEvent(self, e):
        e.ignore()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T["text"] if self.underMouse() else T["muted"]), 1.6, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        cx, cy = self.width() - 16, self.height() / 2
        path = QPainterPath(QPointF(cx - 4, cy - 2))
        path.lineTo(cx, cy + 2)
        path.lineTo(cx + 4, cy - 2)
        p.drawPath(path)


class Field(QWidget):
    """Label above an input, inline error and optional hint below."""

    def __init__(self, title, input_widget, hint=None, password=False):
        super().__init__()
        lay = vbox(self, 6)
        self.title = label(title, "strong")
        lay.addWidget(self.title)
        self.input = input_widget
        input_widget.setAccessibleName(title)
        self.row = hbox(spacing=8)
        self.row.addWidget(input_widget, 1)
        if password:
            input_widget.setEchoMode(QLineEdit.Password)
            self.eye = button("Show", self._toggle_show, "ghost")
            self.row.addWidget(self.eye)
        lay.addLayout(self.row)
        self.error = label("", "error", wrap=True)
        self.error.hide()
        lay.addWidget(self.error)
        self.hint = label(hint or "", "small", wrap=True)
        self.hint.setVisible(bool(hint))
        lay.addWidget(self.hint)
        self.shake_anim = animation(self, 340, self._shake_step, curve=QEasingCurve.Linear)

    def _toggle_show(self):
        hidden = self.input.echoMode() == QLineEdit.Password
        self.input.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
        self.eye.setText("Hide" if hidden else "Show")

    def set_error(self, msg):
        self.error.setText(msg or "")
        self.error.setVisible(bool(msg))
        set_prop(self.input, "error", bool(msg))

    def _shake_step(self, t):
        off = int(math.sin(t * math.pi * 4) * (1 - t) * 5)
        self.row.setContentsMargins(max(0, off), 0, max(0, -off), 0)

    def shake(self):
        """Wiggle the input sideways: 'look here'."""
        self.shake_anim.stop()
        self.shake_anim.start()
        self.input.setFocus()


# ---------------------------------------------------------------- containers

class Section(QFrame):
    """Rounded surface with an optional title row (title left, `aside` label right)."""

    def __init__(self, title=None, warn=False, padding=(20, 18, 20, 20)):
        super().__init__()
        self.setObjectName("section")
        self.setProperty("warn", warn)
        self.body = vbox(self, 0, padding)
        self.aside = label("", "small")
        if title:
            head = hbox(spacing=12)
            self.title = label(title, "head", wrap=True)
            head.addWidget(self.title, 1)
            head.addWidget(self.aside, 0, Qt.AlignTop)
            self.body.addLayout(head)
            self.body.addSpacing(14)


class Divider(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("divider")
        self.setFixedHeight(1)


class ChoiceCard(QFrame):
    """Selectable card: radio dot, title, a short meta line and a description. Click, Space or Enter picks it."""
    clicked = Signal()

    def __init__(self, title, meta, desc):
        super().__init__()
        self.setObjectName("choice")
        self.setProperty("selected", False)
        self.name = title
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # the grid picks the column count, not the text
        lay = vbox(self, 4, (14, 12, 14, 14))
        top = hbox(spacing=10)
        self.radio = Radio()
        top.addWidget(self.radio)
        top.addWidget(label(title, "head", wrap=True), 1)
        lay.addLayout(top)
        lay.addWidget(label(meta, "small"))
        lay.addSpacing(2)
        lay.addWidget(label(desc, "muted", wrap=True))
        lay.addStretch(1)
        for w in self.findChildren(QWidget):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_selected(self, on):
        set_prop(self, "selected", on)
        self.radio.set_on(on)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)


class Radio(QWidget):
    """Radio dot drawn to match the theme."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(18, 18)
        self.on = False

    def set_on(self, on):
        self.on = on
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T["accent"] if self.on else T["border_strong"]), 1.6))
        p.setBrush(QColor(T["surface"]))
        p.drawEllipse(QRectF(1, 1, 16, 16))
        if self.on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T["accent"]))
            p.drawEllipse(QRectF(5, 5, 8, 8))


class ResponsiveGrid(QWidget):
    """`max_cols` columns when there is room, one otherwise. add(widget, wide=True) spans all columns."""

    def __init__(self, min_two=560, max_cols=2, align=Qt.AlignTop):
        super().__init__()
        self.min_two, self.max_cols, self.align, self.cols = min_two, max_cols, align, 0
        self.items = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(18)

    def add(self, w, wide=False):
        self.items.append((w, wide))
        self.cols = 0
        self._reflow(self.width() or 0)

    def clear(self):
        for w, _ in self.items:
            self.grid.removeWidget(w)
            w.deleteLater()
        self.items, self.cols = [], 0

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow(e.size().width())

    def _reflow(self, width):
        cols = self.max_cols if width >= self.min_two else 1
        if cols == self.cols:
            return
        self.cols = cols
        for w, _ in self.items:
            self.grid.removeWidget(w)
        r = c = 0
        for w, wide in self.items:
            if wide or cols == 1:
                if c:
                    r, c = r + 1, 0
                self.grid.addWidget(w, r, 0, 1, cols, self.align)
                r += 1
            else:
                self.grid.addWidget(w, r, c, self.align)
                c += 1
                if c == cols:
                    r, c = r + 1, 0
        for i in range(self.max_cols):
            self.grid.setColumnStretch(i, 1 if i < cols else 0)


class DropZone(QFrame):
    """Big click-or-drop target for a file with one of `exts`."""
    dropped = Signal(str)
    clicked = Signal()

    def __init__(self, title, sub, exts=(".iso",)):
        super().__init__()
        self.setObjectName("drop")
        self.exts = exts
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setMinimumHeight(170)
        lay = vbox(self, 6, (24, 28, 24, 28))
        lay.addStretch(1)
        self.icon = DiscIcon()
        lay.addWidget(self.icon, 0, Qt.AlignHCenter)
        lay.addSpacing(6)
        t = label(title, "head", wrap=True)
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        s = label(sub, "small", wrap=True)
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(s)
        lay.addStretch(1)
        for w in self.findChildren(QWidget):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def _path(self, e):
        urls = e.mimeData().urls() if e.mimeData().hasUrls() else []
        if len(urls) == 1 and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith(self.exts):
            return urls[0].toLocalFile()
        return None

    def dragEnterEvent(self, e):
        if self._path(e):
            e.acceptProposedAction()
            set_prop(self, "over", True)

    def dragLeaveEvent(self, e):
        set_prop(self, "over", False)

    def dropEvent(self, e):
        set_prop(self, "over", False)
        p = self._path(e)
        if p:
            e.acceptProposedAction()
            self.dropped.emit(p)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.hasFocus():
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(T["accent"]), 2))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)


class DiscIcon(QWidget):
    """A disc, drawn so it needs no image files. `ok` adds a check badge."""

    def __init__(self, size=44, ok=False):
        super().__init__()
        self.ok = ok
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T["accent_soft"]))
        p.drawEllipse(QRectF(0, 0, s, s))
        p.setPen(QPen(QColor(T["accent"]), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(s * .22, s * .22, s * .56, s * .56))
        p.setBrush(QColor(T["accent"]))
        p.drawEllipse(QRectF(s * .43, s * .43, s * .14, s * .14))
        if self.ok:
            r = QRectF(s * .58, s * .58, s * .42, s * .42)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T["success"]))
            p.drawEllipse(r)
            p.setPen(QPen(QColor(T["surface"]), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            c = r.center()
            path = QPainterPath(QPointF(c.x() - r.width() * .22, c.y()))
            path.lineTo(c.x() - r.width() * .05, c.y() + r.height() * .17)
            path.lineTo(c.x() + r.width() * .24, c.y() - r.height() * .17)
            p.drawPath(path)


class ProgressBar(QWidget):
    """Rounded bar with eased value/color changes and a moving shimmer while busy."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(8)
        self.value, self.phase, self.busy = 0.0, 0.0, False
        self.color_key = "accent"
        self.v_anim = animation(self, 450, self._set_value)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._spin)

    def _set_value(self, v):
        self.value = v
        self.update()

    def set(self, value, ms=450):
        self.v_anim.stop()
        if ms <= 0:
            self._set_value(value)
            return
        self.v_anim.setDuration(ms)
        self.v_anim.setStartValue(float(self.value))
        self.v_anim.setEndValue(float(value))
        self.v_anim.start()

    def set_color(self, key):
        """A theme token name: accent, success or danger."""
        self.color_key = key
        self.update()

    def shimmer(self, on):
        self.busy = on
        self.timer.start() if on else self.timer.stop()
        self.update()

    def _spin(self):
        self.phase = (self.phase + 0.006) % 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        w, h = self.width(), self.height()
        p.setBrush(QColor(T["surface2"]))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        fw = w * self.value / 100
        if fw < 1:
            return
        color = QColor(T[self.color_key])
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(0, 0, max(fw, h), h), h / 2, h / 2)
        p.setBrush(color)
        p.drawPath(bar)
        if self.busy and fw > 30:
            sw = 110
            x0 = self.phase * (fw + sw) - sw
            g = QLinearGradient(x0, 0, x0 + sw, 0)
            glow = mix(color, "#FFFFFF", 0.35)
            g.setColorAt(0, QColor(0, 0, 0, 0))
            g.setColorAt(0.5, QColor(glow.red(), glow.green(), glow.blue(), 150))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setClipPath(bar)
            p.setBrush(g)
            p.drawRect(QRectF(x0, 0, sw, h))


class SmoothScrollArea(QScrollArea):
    """Mouse wheel notches glide instead of jumping; touchpads (pixel deltas) scroll as they are."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.target = None
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(lambda v: self.verticalScrollBar().setValue(int(v)))
        self.anim.finished.connect(self._anim_done)

    def _anim_done(self):
        self.target = None

    def wheelEvent(self, e):
        bar = self.verticalScrollBar()
        if not e.pixelDelta().isNull() or e.angleDelta().y() == 0:
            self.anim.stop()
            self.target = None
            super().wheelEvent(e)
            return
        base = self.target if self.target is not None else bar.value()
        self.target = max(bar.minimum(), min(bar.maximum(), base - e.angleDelta().y() / 120 * 90))
        self.anim.stop()
        self.anim.setStartValue(float(bar.value()))
        self.anim.setEndValue(float(self.target))
        self.anim.start()
        e.accept()


class Logo(QWidget):
    def __init__(self, size=28):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T["accent"]))
        s = self.width()
        p.drawRoundedRect(QRectF(0, 0, s, s), s * .28, s * .28)
        # four window panes
        p.setBrush(QColor(T["on_accent"]))
        g, m = s * .07, s * .26
        q = (s - 2 * m - g) / 2
        for dx in (0, 1):
            for dy in (0, 1):
                p.drawRoundedRect(QRectF(m + dx * (q + g), m + dy * (q + g), q, q), 1.5, 1.5)
