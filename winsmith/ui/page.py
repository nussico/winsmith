"""Page frame shared by all steps: scrolling centered column with a heading, and a footer bar."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QSizePolicy, QSpacerItem, QWidget

from .widgets import SmoothScrollArea, animation, hbox, label, vbox

MAX_W = 760
NARROW = 640


class Page(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        outer = vbox(self)
        self.scroll = SmoothScrollArea()
        holder = QWidget()
        self.row = hbox(holder)
        col = QWidget()
        col.setMaximumWidth(MAX_W)
        self.row.addStretch(1)
        self.row.addWidget(col, 1000)
        self.row.addStretch(1)
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll, 1)

        content = vbox(col)
        self.head = QWidget()
        head = hbox(self.head, 16)
        text = vbox(spacing=4)
        text.addWidget(label(title, "title"))
        text.addWidget(label(subtitle, "muted", wrap=True))
        head.addLayout(text, 1)
        self.head_right = vbox()
        self.head_right.setAlignment(Qt.AlignBottom)
        head.addLayout(self.head_right)
        content.addWidget(self.head)
        content.addSpacing(24)
        self.body = vbox(spacing=16)
        content.addLayout(self.body)
        content.addStretch(1)

        self.footer = QWidget()
        self.footer.setObjectName("footer")
        self.footer.setAttribute(Qt.WA_StyledBackground)
        self.foot = hbox(self.footer, 10)
        self.spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.foot.addItem(self.spacer)
        outer.addWidget(self.footer)
        self.right = []

        self.fade = QGraphicsOpacityEffect(self.head)
        self.fade.setEnabled(False)
        self.head.setGraphicsEffect(self.fade)
        self.fade_anim = animation(self, 180, self.fade.setOpacity)
        self.fade_anim.finished.connect(self._fade_done)
        self._narrow = None
        self._apply_width(1000)

    def add_left(self, w):
        self.foot.insertWidget(self.foot.indexOf(self.spacer), w)

    def add_right(self, w):
        self.foot.addWidget(w)
        self.right.append(w)
        self._size_right(w)

    def _size_right(self, w):
        w.setSizePolicy(QSizePolicy.Expanding if self._narrow else QSizePolicy.Preferred, QSizePolicy.Fixed)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_width(e.size().width())

    def _apply_width(self, width):
        narrow = width < NARROW
        if narrow == self._narrow:
            return
        self._narrow = narrow
        g = 16 if narrow else 32
        self.row.setContentsMargins(g, 24 if narrow else 32, g, 32)
        self.foot.setContentsMargins(g, 12, g, 12)
        # Narrow: the main buttons take the free width so they are easy to hit.
        self.spacer.changeSize(0, 0, QSizePolicy.Fixed if narrow else QSizePolicy.Expanding, QSizePolicy.Minimum)
        for w in self.right:
            self._size_right(w)
        self.foot.invalidate()

    def _fade_done(self):
        self.fade.setEnabled(False)

    def enter(self):
        """Back to the top and fade the heading in."""
        self.scroll.anim.stop()
        self.scroll.verticalScrollBar().setValue(0)
        self.fade.setOpacity(0)
        self.fade.setEnabled(True)
        self.fade_anim.start()
