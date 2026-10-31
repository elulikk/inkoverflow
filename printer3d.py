"""Vista 3D: the printer as a 3D model (Qt Quick 3D), another face of the same data.
It can also draw the printer as flat 2D sprites (Bridge.mode2d, view3d/Printer2D.qml), much
lighter, and cap itself at 30 frames per second (Bridge.fps30, right-click on the FPS counter).

The scene is view3d/Printer3D.qml; each printer style has its own QML file and meshes
(built by view3d/make_model.py), picked by data["style"]. Python
hands it one dict (Bridge.data) and gets back requests (refresh, reset, backup, the
maintenance jobs in ACTIONS) that MainWindow answers with the same methods, dialogs and
checks as the ribbon buttons.
"""
import os
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QStackedLayout, QVBoxLayout,
                               QWidget)

import prefs

HERE = Path(__file__).resolve().parent
QML = HERE / "view3d" / "Printer3D.qml"

# 3D models (data["style"]): style -> (view3d/<QML file>, name, brand, ink), meshes in
# view3d/meshes/<style>/ (built by view3d/make_model.py). The one list of them: the scene
# (Bridge.styleFiles), the 2D view and the model viewer (visor3d.py) read it from here.
# `ink` is "tanks", "cartridges" or "toner". An unknown or missing style draws the Epson.
MODELS = {
    "epson_l3150": ("EpsonL3150.qml", "Epson L3150", "epson", "tanks"),
    "epson_xp2100": ("EpsonXP2100.qml", "Epson XP-2100", "epson", "cartridges"),
    "hp_smart_tank_580": ("HpSmartTank580.qml", "HP Smart Tank 580", "hp", "tanks"),
    "hp_smart_tank_210": ("HpSmartTank210.qml", "HP Smart Tank 210", "hp", "tanks"),
    "hp_ink_tank_415": ("HpInkTank415.qml", "HP Ink Tank 415", "hp", "tanks"),
    "hp_deskjet_2775": ("HpDeskJet2775.qml", "HP DeskJet Ink Advantage 2775", "hp",
                        "cartridges"),
    "canon_g3110": ("CanonG3110.qml", "Canon PIXMA G3110", "canon", "tanks"),
    "brother_t420w": ("BrotherT420W.qml", "Brother DCP-T420W", "brother", "tanks"),
    # mono lasers: one family file each for the printer and its multifunction
    "hp_laserjet_m111": ("HpLaserJet.qml", "HP LaserJet M111w", "hp", "toner"),
    "hp_laserjet_m141": ("HpLaserJet.qml", "HP LaserJet MFP M141w", "hp", "toner"),
    "brother_hl1212w": ("BrotherLaser.qml", "Brother HL-1212W", "brother", "toner"),
    "brother_dcp1612w": ("BrotherLaser.qml", "Brother DCP-1612W", "brother", "toner"),
    "pantum_p2500w": ("PantumLaser.qml", "Pantum P2500W", "pantum", "toner"),
    "pantum_m6550nw": ("PantumLaser.qml", "Pantum M6550NW", "pantum", "toner"),
    "samsung_m2020w": ("SamsungLaser.qml", "Samsung Xpress M2020W", "samsung", "toner"),
    "samsung_m2070w": ("SamsungLaser.qml", "Samsung Xpress M2070W", "samsung", "toner"),
}
STYLES = {style: model[0] for style, model in MODELS.items()}

# L3150 family: what the tanks show before (or without) a reading
DEFAULT_INKS = [("Negro", "#1d1d1f"), ("Cian", "#00a3e0"), ("Magenta", "#d6007e"),
                ("Amarillo", "#f5d000")]

# What the 3D view can ask for besides refresh/reset/backup: the same jobs as the ribbon's
# Mantenimiento buttons (MainWindow answers each with that button's own checks and dialogs).
ACTIONS = ("nozzle", "nozzle2", "color", "page", "clean", "feed")

# Below this many frames per second (for FPS_SECONDS in a row) the 3D view turns itself off.
MIN_FPS = 20
FPS_SECONDS = 6


def empty_data(dark=True):
    return {
        "connected": False, "busy": False, "dark": dark,
        "title": "Epson L3150", "model": "", "serial": "--", "status": "Sin conexión",
        "statusKind": "muted", "inks": [{"name": n, "color": c, "level": -1}
                                        for n, c in DEFAULT_INKS],
        "inkMeasured": False, "pads": [], "worst": -1.0, "stats": [],
        "canReset": False, "canRead": False, "why": "", "note": "",
        # which 3D model to draw: "epson_l3150", "epson_xp2100" or "hp_smart_tank_580"
        # (see STYLES)
        "brand": "epson", "style": "epson_l3150",
        # what the printer is doing, drawn in 3D: "" (nothing), "printing", "feeding"
        # (rollers only), "cleaning" or "error";
        # progress 0-1, or -1 when unknown
        "activity": "", "activityText": "", "progress": -1.0,
        # why each of ACTIONS is off right now ("" = it can run), and what it would use
        "actions": {name: "Conecta la impresora y pulsa Actualizar." for name in ACTIONS},
        "cleanLabel": "", "pageName": "",
    }


class Bridge(QObject):
    """The one object the QML sees, as `bridge`."""
    dataChanged = Signal()
    refreshRequested = Signal()
    resetRequested = Signal(str)        # "dry", "temp" or "perm"
    backupRequested = Signal()
    actionRequested = Signal(str)       # one of ACTIONS
    lowFps = Signal(float)              # the view ran below MIN_FPS: turn it off
    cameraRequested = Signal(str)       # Python -> QML: "front", "tanks", "pads", "spin"
    pinnedChanged = Signal()
    fpsGuardChanged = Signal()
    mode2dChanged = Signal()
    fps30Changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = empty_data()
        saved = prefs.load()
        # info panels: always shown (True) or only while the cursor is on that part (False)
        self._pinned = saved.get("view3d_pinned") is True
        self._fps_guard = saved.get("view3d_fps_guard") is not False
        # the printer as flat 2D sprites (view3d/Printer2D.qml) instead of the 3D scene
        self._mode2d = saved.get("view3d_2d") is True
        # at most 30 frames per second (right-click on the FPS counter)
        self._fps30 = saved.get("view3d_fps30") is True

    def _get(self):
        return self._data

    def set_data(self, data):
        self._data = data
        self.dataChanged.emit()

    data = Property("QVariantMap", _get, notify=dataChanged)

    def _get_pinned(self):
        return self._pinned

    def _set_pinned(self, on):
        on = bool(on)
        if on != self._pinned:
            self._pinned = on
            prefs.save(view3d_pinned=on)
            self.pinnedChanged.emit()

    pinned = Property(bool, _get_pinned, _set_pinned, notify=pinnedChanged)

    def _get_fps_guard(self):
        return self._fps_guard

    def _set_fps_guard(self, on):
        on = bool(on)
        if on != self._fps_guard:
            self._fps_guard = on
            prefs.save(view3d_fps_guard=on)
            self.fpsGuardChanged.emit()

    fpsGuard = Property(bool, _get_fps_guard, _set_fps_guard, notify=fpsGuardChanged)

    def _get_mode2d(self):
        return self._mode2d

    def _set_mode2d(self, on):
        on = bool(on)
        if on != self._mode2d:
            self._mode2d = on
            prefs.save(view3d_2d=on)
            self.mode2dChanged.emit()

    mode2d = Property(bool, _get_mode2d, _set_mode2d, notify=mode2dChanged)

    def _get_fps30(self):
        return self._fps30

    def _set_fps30(self, on):
        on = bool(on)
        if on != self._fps30:
            self._fps30 = on
            prefs.save(view3d_fps30=on)
            self.fps30Changed.emit()

    fps30 = Property(bool, _get_fps30, _set_fps30, notify=fps30Changed)

    def _min_fps(self):
        return MIN_FPS

    def _fps_seconds(self):
        return FPS_SECONDS

    def _style_files(self):
        return dict(STYLES)

    styleFiles = Property("QVariantMap", _style_files, constant=True)
    minFps = Property(int, _min_fps, constant=True)
    fpsSeconds = Property(int, _fps_seconds, constant=True)

    # Requests are answered on the next turn of the event loop, not inside the QML click:
    # their dialogs run a nested loop, and meanwhile the hover card that holds the button
    # may close and destroy it, which crashes Qt if its click handler is still running.
    @staticmethod
    def _later(signal, *args):
        QTimer.singleShot(0, lambda: signal.emit(*args))

    @Slot()
    def refresh(self):
        self._later(self.refreshRequested)

    @Slot(str)
    def reset(self, mode):
        if mode in ("dry", "temp", "perm"):
            self._later(self.resetRequested, mode)

    @Slot()
    def backup(self):
        self._later(self.backupRequested)

    @Slot(str)
    def action(self, name):
        if name in ACTIONS:
            self._later(self.actionRequested, name)

    @Slot(float)
    def reportLowFps(self, fps):
        if self._fps_guard and not self._mode2d:     # 2D is the light fallback: never off
            self.lowFps.emit(fps)


def available():
    """'' when the 3D view can run here, else why not (in words)."""
    if os.environ.get("QT_QPA_PLATFORM", "") in ("offscreen", "minimal"):
        return "La vista 3D necesita una pantalla (no funciona en modo sin ventana)."
    if not QML.is_file() or not (HERE / "view3d" / "meshes").is_dir():
        return "Faltan los archivos de la vista 3D (carpeta view3d)."
    return ""


def off_text(fps):
    return (f"La vista 3D se apagó sola porque iba a {float(fps):.0f} cuadros por segundo "
            f"(menos de {MIN_FPS}): esta computadora no la mueve con fluidez y frenaba "
            "toda la aplicación.\n\nLa vista 2D muestra lo mismo con dibujos planos y es "
            "mucho más liviana. Los mismos datos y botones también están en Resumen y "
            "Mantenimiento.")


class Printer3DPage(QWidget):
    """Holds the QQuickWidget, created the first time the page is shown, so the 3D
    engine costs nothing at start-up or on machines that never open it. If the view runs
    too slowly (Bridge.lowFps) it is destroyed and stays off, also in later sessions,
    until the user turns it back on from the note shown in its place."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.view = None
        self._stack = QStackedLayout(self)
        self._holder = QWidget()
        lay = QVBoxLayout(self._holder)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)
        self._note = QLabel("Cargando la vista 3D...")
        self._note.setObjectName("muted")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)
        row = QHBoxLayout()
        self.btn_2d = QPushButton("Usar la vista 2D")
        self.btn_2d.setToolTip("La misma vista con dibujos planos (sprites 2D): mucho más liviana.")
        self.btn_2d.clicked.connect(self.use_2d)
        self.btn_retry = QPushButton("Volver a activar la vista 3D")
        self.btn_retry.setToolTip("Vuelve a crear la vista 3D. Si sigue lenta, se apaga otra vez.")
        self.btn_force = QPushButton("Activar sin control de FPS")
        self.btn_force.setToolTip("Vuelve a crear la vista 3D y no la apaga aunque vaya lenta.")
        self.btn_retry.clicked.connect(lambda: self.enable_3d(guard=True))
        self.btn_force.clicked.connect(lambda: self.enable_3d(guard=False))
        for b in (self.btn_2d, self.btn_retry, self.btn_force):
            b.hide()
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        self._stack.addWidget(self._holder)
        bridge.lowFps.connect(self._on_low_fps)

    def showEvent(self, event):
        super().showEvent(event)
        if self.view is None:
            self._create()
        self._set_active(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._set_active(False)

    def preload(self):
        """Build the view while the user is on another page (QML + meshes load now, not on
        the first visit). It stays inactive, so it draws nothing until the page is shown."""
        if self.view is None and not self.isVisible():
            self._create()
            self._set_active(False)

    def _set_active(self, on):
        root = self.view.rootObject() if self.view else None
        if root is not None:
            root.setProperty("active", on)

    def _show_off(self, text, buttons):
        self.view = False
        self._note.setText(text)
        self.btn_2d.setVisible(buttons)
        self.btn_retry.setVisible(buttons)
        self.btn_force.setVisible(buttons)
        self._stack.setCurrentWidget(self._holder)

    def _on_low_fps(self, fps):
        # comes from inside a QML frame: tear the view down once that frame is over
        QTimer.singleShot(0, lambda: self.disable_3d(fps))

    def disable_3d(self, fps):
        """Turn the 3D view off (it ran at `fps`) and remember it for the next sessions."""
        prefs.save(view3d_off=round(float(fps), 1))
        if self.view:
            self._stack.removeWidget(self.view)
            self.view.deleteLater()
        self._show_off(off_text(fps), True)

    def use_2d(self):
        """Bring the view back as 2D sprites (from the note shown after a low-FPS shutdown)."""
        self.bridge.mode2d = True
        self.enable_3d(guard=True)

    def enable_3d(self, guard=True):
        prefs.save(view3d_off=None)
        self.bridge.fpsGuard = guard
        self.view = None
        if self.isVisible():
            self._create()
            self._set_active(True)

    def reload(self):
        """Build the view again from its files (QML and meshes just rebuilt)."""
        if self.view:
            self._stack.removeWidget(self.view)
            self.view.deleteLater()
        self.view = None
        if self.isVisible():
            self._create()
            self._set_active(True)

    def _create(self):
        why = available()
        if why:
            self._show_off(why, False)
            return
        off = prefs.load().get("view3d_off")
        if (isinstance(off, (int, float)) and not isinstance(off, bool)
                and not self.bridge.mode2d):            # the 2D view never gets turned off
            self._show_off(off_text(off), True)
            return
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtGui import QSurfaceFormat

        self._note.setText("Cargando la vista 3D...")
        self.btn_2d.hide()
        self.btn_retry.hide()
        self.btn_force.hide()
        view = QQuickWidget(self)
        fmt = QSurfaceFormat()
        fmt.setSamples(4)
        view.setFormat(fmt)
        view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        view.rootContext().setContextProperty("bridge", self.bridge)
        view.setSource(QUrl.fromLocalFile(str(QML)))
        if view.status() == QQuickWidget.Error:
            errors = "\n".join(e.toString() for e in view.errors())
            view.deleteLater()
            self._show_off(f"No se pudo abrir la vista 3D.\n\n{errors}", False)
            return
        self.view = view
        self._stack.addWidget(view)
        self._stack.setCurrentWidget(view)
