"""Start-up screen: the brand's cup, as wide as the window, filling with CMYK ink while the
model database loads. All the text lives inside the cup, on top of the ink.

The level creeps towards 85 % on its own; finish() fills it to the brim, lets one drop
overflow and then closes the splash and runs the callback (showing the main window).
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

OUTLINE = QColor("#1b2028")
TEAL = QColor("#11869a")
CMYK = (QColor("#00a0e0"), QColor("#e0007a"), QColor("#f2c800"), QColor("#1f2328"))


class InkSplash(QWidget):
    W, H = 500, 300
    CUP = QRectF(30, 52, 440, 214)   # inside of the cup (the whole window)

    def __init__(self, app_name, tagline="El contador miente. Nosotros llevamos la cuenta."):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.app_name, self.tagline = app_name, tagline
        self.setFixedSize(self.W, self.H)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.level, self.phase = 0.2, 0.0
        self.message = "Iniciando..."
        self.drops = []            # [x, y, speed, colour] of drops falling into the cup
        self.spill = None          # y of the drop running down the outside once full
        self._done = None          # callback once full; None while still loading
        self._hold = 0             # ticks spent full before closing
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())

    # ---- control -----------------------------------------------------------
    def set_message(self, text):
        self.message = text
        self.update()

    def finish(self, callback):
        """Fill up, overflow, close, then call `callback` (called once)."""
        if self._done is None:
            self._done = callback
            self.message = "Listo"

    # ---- animation ---------------------------------------------------------
    def _tick(self):
        self.phase += 0.11
        if self._done is None:
            self.level += (0.85 - self.level) * 0.012
        elif self.level < 1.0:
            self.level = min(1.0, self.level + max(0.012, (1.0 - self.level) * 0.09))
        if self.level < 0.995 and random.random() < 0.22:
            self.drops.append([random.uniform(self.CUP.left() + 20, self.CUP.right() - 20), 6.0,
                               random.uniform(3.5, 5.5), random.randrange(4)])
        surface = self._surface_y()
        for drop in self.drops:
            drop[1] += drop[2]
            drop[2] += 0.25
        self.drops = [d for d in self.drops if d[1] < surface]
        if self.level >= 1.0 and self._done is not None:
            if self.spill is None:
                self.spill = self.CUP.top() - 16
            self.spill += 2.2
            self._hold += 1
            if self._hold > 42:
                self._timer.stop()
                done, self._done = self._done, (lambda: None)
                self.close()
                done()
        self.update()

    def _surface_y(self):
        # 100 % is the lip of the cup, where the ink starts to spill over
        return self.CUP.bottom() - (self.CUP.height() + 14) * min(self.level, 1.0)

    # ---- painting ------------------------------------------------------------
    def _cup_path(self):
        """Inside of the cup: straight sides, rounded bottom."""
        r, c = 26.0, self.CUP
        path = QPainterPath()
        path.moveTo(c.left(), c.top() - 14)
        path.lineTo(c.left(), c.bottom() - r)
        path.quadTo(c.left(), c.bottom(), c.left() + r, c.bottom())
        path.lineTo(c.right() - r, c.bottom())
        path.quadTo(c.right(), c.bottom(), c.right(), c.bottom() - r)
        path.lineTo(c.right(), c.top() - 14)
        path.closeSubpath()
        return path

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cup = self._cup_path()
        c = self.CUP
        # glass and ink
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#eef6f8"))
        p.drawPath(cup)
        surface = self._surface_y()
        wave = QPainterPath()
        wave.moveTo(c.left() - 2, c.bottom() + 2)
        amp = 3.5 if self.level < 0.995 else 1.5
        x = c.left() - 2
        while x <= c.right() + 2:
            y = (surface + amp * math.sin(x / 13 + self.phase)
                 + amp * 0.5 * math.sin(x / 6.5 - self.phase * 1.4))
            wave.lineTo(x, y)
            x += 2
        wave.lineTo(c.right() + 2, c.bottom() + 2)
        wave.closeSubpath()
        ink = wave.intersected(cup)
        p.save()
        p.setClipPath(cup)
        band = c.width() / 4
        for i, color in enumerate(CMYK):   # four vertical bands: C M Y K
            p.save()
            p.setClipRect(QRectF(c.left() + i * band, 0, band + (1 if i < 3 else 8), self.H),
                          Qt.IntersectClip)
            grad = QLinearGradient(0, c.top(), 0, c.bottom())
            grad.setColorAt(0, color.lighter(118))
            grad.setColorAt(1, color)
            p.setBrush(grad)
            p.drawPath(ink)
            p.restore()
        # a few bubbles rising in the ink
        p.setBrush(QColor(255, 255, 255, 90))
        for i in range(9):
            bx = c.left() + 26 + i * 50
            by = c.bottom() - ((self.phase * 9 + i * 37) % max(1.0, c.bottom() - surface))
            if by > surface + 6:
                p.drawEllipse(QPointF(bx + 3 * math.sin(self.phase + i), by), 2.2, 2.2)
        p.restore()

        # graduation marks, like a measuring beaker
        p.setFont(QFont("Segoe UI", 7))
        for pct in (25, 50, 75):
            y = c.bottom() - c.height() * pct / 100
            p.setPen(QPen(QColor(255, 255, 255, 200) if y > surface else QColor(27, 32, 40, 150), 1.2))
            p.drawLine(QPointF(c.left() + 4, y), QPointF(c.left() + 14, y))

        # cup outline, as in the logo (white halo so it reads on any desktop)
        pen = QPen(QColor("#ffffff"), 15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        halo_pen, pen = pen, QPen(OUTLINE, 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setBrush(Qt.NoBrush)
        r = 26.0
        outline = QPainterPath()
        outline.moveTo(c.left() - 4.5, c.top() - 18)
        outline.lineTo(c.left() - 4.5, c.bottom() - r)
        outline.quadTo(c.left() - 4.5, c.bottom() + 4.5, c.left() + r, c.bottom() + 4.5)
        outline.lineTo(c.right() - r, c.bottom() + 4.5)
        outline.quadTo(c.right() + 4.5, c.bottom() + 4.5, c.right() + 4.5, c.bottom() - r)
        outline.lineTo(c.right() + 4.5, c.top() - 18)
        p.setPen(halo_pen)
        p.drawPath(outline)
        p.setPen(pen)
        p.drawPath(outline)

        # drops falling in
        p.setPen(Qt.NoPen)
        for x, y, _speed, ci in self.drops:
            p.setBrush(CMYK[ci])
            self._drop(p, x, y, 4.2)
        # overflow: one drop running down the outside of the right wall
        if self.spill is not None:
            p.setBrush(CMYK[3])
            sx = c.right() + 11
            if self.spill < c.bottom():
                trail = QRectF(sx - 2.2, c.top() - 18, 4.4, self.spill - c.top() + 18)
                p.drawRoundedRect(trail, 2.2, 2.2)
            self._drop(p, sx, min(self.spill, c.bottom() + 24), 5.5)

        # text: everything sits inside the cup; a white halo keeps it legible on every colour
        tx = c.left() + 36
        name = self.app_name
        name_font = QFont("Segoe UI", 26, QFont.Bold)
        if name.startswith("Ink"):
            ink_w = QFontMetricsF(name_font).horizontalAdvance("Ink")
            self._text(p, tx, 128, "Ink", name_font, OUTLINE)
            self._text(p, tx + ink_w, 128, name[3:], name_font, TEAL.darker(130))
        else:
            self._text(p, tx, 128, name, name_font, OUTLINE)
        self._text(p, tx, 156, self.tagline, QFont("Segoe UI", 10), QColor("#10151c"))
        self._text(p, tx, 206, self.message, QFont("Segoe UI", 10), QColor("#10151c"))
        self._text(p, tx, 240, f"{min(self.level, 1.0) * 100:.0f} %",
                   QFont("Segoe UI", 18, QFont.DemiBold), OUTLINE)
        small = QFont("Segoe UI", 9)
        self._text(p, c.right() - 28 - QFontMetricsF(small).horizontalAdvance("MAG Tecnología"),
                   240, "MAG Tecnología", small, QColor("#10151c"))

    @staticmethod
    def _text(p, x, y, text, font, color):
        path = QPainterPath()
        path.addText(x, y, font, text)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 235), 4.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    @staticmethod
    def _drop(p, x, y, size):
        path = QPainterPath()
        path.moveTo(x, y - size * 1.9)
        path.cubicTo(x + size * 0.4, y - size * 0.9, x + size, y - size * 0.4, x + size, y + size * 0.2)
        path.arcTo(QRectF(x - size, y - size * 0.8, size * 2, size * 2), 0, -180)
        path.cubicTo(x - size, y - size * 0.4, x - size * 0.4, y - size * 0.9, x, y - size * 1.9)
        p.drawPath(path)
