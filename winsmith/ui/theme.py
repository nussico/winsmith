"""Light and dark color tokens, the app stylesheet built from them, and live switching with the OS setting."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette

LIGHT = {
    "bg": "#F5F6F8", "surface": "#FFFFFF", "surface2": "#F0F2F5", "hover": "#E9ECF1",
    "border": "#E1E4EA", "border_strong": "#C8CDD5",
    "text": "#16191F", "muted": "#5F6774", "faint": "#9AA1AC",
    "accent": "#2563EB", "accent_hover": "#1D4FD7", "accent_soft": "#E7EEFD", "on_accent": "#FFFFFF",
    "success": "#16803C", "warn": "#B45309", "warn_soft": "#FEF3E2", "danger": "#D92D20",
}
DARK = {
    "bg": "#111317", "surface": "#191C22", "surface2": "#20242B", "hover": "#262B33",
    "border": "#2A2F37", "border_strong": "#3B414B",
    "text": "#E9EBEE", "muted": "#9CA3AE", "faint": "#646B76",
    "accent": "#5B8DEF", "accent_hover": "#7BA3F4", "accent_soft": "#1C2740", "on_accent": "#FFFFFF",
    "success": "#4ADE80", "warn": "#FBBF24", "warn_soft": "#2A2316", "danger": "#F87171",
}

T = dict(LIGHT)  # the active tokens; widgets read them when they paint
SANS, MONO = "Segoe UI", "Consolas"


def is_dark():
    forced = os.environ.get("WINSMITH_THEME", "").lower()
    if forced in ("light", "dark"):
        return forced == "dark"
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def _pick_fonts():
    global SANS, MONO
    fams = set(QFontDatabase.families())
    SANS = next((f for f in ["Segoe UI Variable Text", "Segoe UI", "Inter", "Cantarell", "Noto Sans", "DejaVu Sans"]
                 if f in fams), QGuiApplication.font().family())
    MONO = next((f for f in ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"] if f in fams),
                "monospace")


def font(pt=10, weight=QFont.Normal):
    f = QFont(SANS)
    f.setPointSizeF(pt)
    f.setWeight(weight)
    return f


def apply(app):
    """Set fonts, palette and stylesheet, and follow the OS light/dark setting from now on."""
    _pick_fonts()
    f = font(10)
    f.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(f)
    _restyle(app)
    if not getattr(app, "_winsmith_theme", False):
        app._winsmith_theme = True
        app.styleHints().colorSchemeChanged.connect(lambda _: _restyle(app))


def _restyle(app):
    T.clear()
    T.update(DARK if is_dark() else LIGHT)
    pal = QPalette()
    for role, key in [(QPalette.Window, "bg"), (QPalette.Base, "surface"), (QPalette.AlternateBase, "surface2"),
                      (QPalette.Button, "surface"), (QPalette.Text, "text"), (QPalette.WindowText, "text"),
                      (QPalette.ButtonText, "text"), (QPalette.ToolTipBase, "surface"), (QPalette.ToolTipText, "text"),
                      (QPalette.Highlight, "accent"), (QPalette.HighlightedText, "on_accent"),
                      (QPalette.PlaceholderText, "faint"), (QPalette.Link, "accent")]:
        pal.setColor(role, QColor(T[key]))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(T))
    for w in app.allWidgets():  # custom-painted widgets pick up the new tokens
        w.update()


def stylesheet(t):
    return f"""
    QWidget {{ color: {t['text']}; }}
    #root {{ background: {t['bg']}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="muted"] {{ color: {t['muted']}; }}
    QLabel[role="small"] {{ color: {t['muted']}; font-size: 9pt; }}
    QLabel[role="error"] {{ color: {t['danger']}; font-size: 9pt; }}
    QLabel[role="title"] {{ font-size: 19pt; font-weight: 600; }}
    QLabel[role="head"] {{ font-size: 11pt; font-weight: 600; }}
    QLabel[role="big"] {{ font-size: 13pt; font-weight: 600; }}
    QLabel[role="strong"] {{ font-weight: 600; }}
    QLabel[role="ok"] {{ color: {t['success']}; font-size: 9pt; font-weight: 600; }}
    QLabel[role="accent"] {{ color: {t['accent']}; font-weight: 600; }}

    #appbar {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
    #brand {{ font-size: 12pt; font-weight: 600; }}
    #version {{ color: {t['faint']}; font-size: 9pt; }}
    #footer {{ background: {t['surface']}; border-top: 1px solid {t['border']}; }}

    QFrame#section {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px; }}
    QFrame#section[warn="true"] {{ background: {t['warn_soft']}; border-color: {t['warn']}; }}
    QFrame#divider {{ background: {t['border']}; border: none; }}

    QFrame#drop {{ background: {t['surface']}; border: 2px dashed {t['border_strong']}; border-radius: 12px; }}
    QFrame#drop:hover, QFrame#drop[over="true"] {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
    QFrame#drop[error="true"] {{ border-color: {t['danger']}; }}
    QFrame#file {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px; }}

    QLineEdit, QComboBox {{ background: {t['surface']}; border: 1px solid {t['border_strong']}; border-radius: 8px;
                            padding: 7px 10px; min-height: 20px;
                            selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
    QLineEdit:hover, QComboBox:hover {{ border-color: {t['muted']}; }}
    QLineEdit:focus, QComboBox:focus, QComboBox:on {{ border: 2px solid {t['accent']}; padding: 6px 9px; }}
    QLineEdit[error="true"], QComboBox[error="true"] {{ border-color: {t['danger']}; }}
    QComboBox {{ combobox-popup: 0; padding-right: 30px; }}
    QComboBox:focus {{ padding-right: 29px; }}
    QComboBox::drop-down {{ border: none; width: 30px; }}
    QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
    QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['border']}; outline: 0;
                                   padding: 4px; }}
    QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 0 8px; border-radius: 6px; }}
    QComboBox QAbstractItemView::item:hover {{ background: {t['hover']}; }}
    QComboBox QAbstractItemView::item:selected {{ background: {t['accent']}; color: {t['on_accent']}; }}

    QPushButton {{ background: {t['surface']}; border: 1px solid {t['border_strong']}; border-radius: 8px;
                   padding: 8px 16px; font-weight: 500; }}
    QPushButton:hover {{ background: {t['hover']}; }}
    QPushButton:pressed {{ background: {t['border']}; }}
    QPushButton:focus {{ border: 2px solid {t['accent']}; padding: 7px 15px; }}
    QPushButton:disabled {{ color: {t['faint']}; }}
    QPushButton[kind="primary"] {{ background: {t['accent']}; border-color: {t['accent']}; color: {t['on_accent']};
                                   font-weight: 600; }}
    QPushButton[kind="primary"]:hover {{ background: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
    QPushButton[kind="primary"]:focus {{ border: 2px solid {t['text']}; }}
    QPushButton[kind="primary"]:disabled {{ background: {t['border']}; border-color: {t['border']};
                                            color: {t['faint']}; }}
    QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid transparent; color: {t['muted']}; }}
    QPushButton[kind="ghost"]:hover {{ background: {t['hover']}; color: {t['text']}; }}
    QPushButton[kind="link"] {{ background: transparent; border: none; color: {t['accent']}; padding: 2px 0;
                                font-weight: 500; text-align: left; }}
    QPushButton[kind="link"]:hover {{ color: {t['accent_hover']}; text-decoration: underline; }}
    QPushButton[kind="link"]:focus {{ border: none; padding: 2px 0; text-decoration: underline; }}
    QPushButton[kind="primary"][big="true"] {{ padding: 10px 24px; }}
    QPushButton::menu-indicator {{ image: none; width: 0; }}

    QFrame#choice {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px;
                     padding: 1px; }}
    QFrame#choice:hover {{ background: {t['hover']}; border-color: {t['border_strong']}; }}
    QFrame#choice:focus {{ border: 2px solid {t['accent']}; padding: 0; }}
    QFrame#choice[selected="true"] {{ background: {t['accent_soft']}; border: 2px solid {t['accent']}; padding: 0; }}

    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
    QScrollBar::handle:vertical {{ background: {t['border_strong']}; border-radius: 4px; min-height: 32px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['faint']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QPlainTextEdit {{ background: {t['surface2']}; border: 1px solid {t['border']}; border-radius: 8px;
                      color: {t['muted']}; padding: 6px; font-family: "{MONO}"; font-size: 9pt; }}
    QLabel#cmd {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 6px 10px;
                  font-family: "{MONO}"; font-size: 9pt; }}
    QMenu {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 4px; }}
    QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {t['hover']}; }}
    QMenu::item:disabled {{ color: {t['faint']}; }}
    QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 6px; }}
    QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px; }}
    QMessageBox, QInputDialog {{ background: {t['bg']}; }}
    """
