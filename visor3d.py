"""Visor de modelos 3D: solo muestra los modelos de impresora, sin conectar nada.

Reutiliza la misma escena de la vista 3D de la aplicación (view3d/Printer3D.qml) con datos
de ejemplo; arriba se elige el modelo (printer3d.MODELS). Mientras está abierto se recarga
solo cuando cambian los archivos de view3d (las mallas que escribe make_model.py o los
QML), para ver un modelo mientras se lo hace. Se abre con `python visor3d.py` (o visor.bat).
"""
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QVBoxLayout, QWidget)

import printer3d
from widgets import app_icon, apply_theme

VIEW3D = Path(__file__).resolve().parent / "view3d"
NIVELES = (85, 60, 40, 70)
# HP 667 / 664 / 662: one black and one tri-colour cartridge
DOS_CARTUCHOS = [("Negro", "#1d1d1f"), ("Tricolor", "#8a5fb0")]


def datos(style, dark):
    _, nombre, marca, tinta = printer3d.MODELS[style]
    d = printer3d.empty_data(dark=dark)
    d.update(connected=True, title=nombre, status="Vista previa", statusKind="ok",
             brand=marca, style=style, inkMeasured=True)
    colores = (DOS_CARTUCHOS if style == "hp_deskjet_2775"
               else [("Negro", "#1d1d1f")] if tinta == "toner"
               else [(i["name"], i["color"]) for i in d["inks"]])
    d["inks"] = [{"name": n, "color": c, "level": nivel}
                 for (n, c), nivel in zip(colores, NIVELES)]
    return d


class VisorBridge(printer3d.Bridge):
    """The app's bridge, but a slow frame never turns the view off: the viewer is for
    looking at models (it may run beside the app or another viewer), and the app's
    "3D off" preference must not change because of it."""

    @Slot(float)
    def reportLowFps(self, fps):
        pass


def huella():
    """Last change to the QML files and meshes of view3d (to reload on a change)."""
    archivos = list(VIEW3D.glob("*.qml")) + list(VIEW3D.glob("meshes/*/*.mesh"))
    try:
        return max(p.stat().st_mtime for p in archivos), len(archivos)
    except (OSError, ValueError):
        return 0, 0


class Visor(QMainWindow):
    def __init__(self, dark=True):
        super().__init__()
        self.setWindowTitle("InkOverflow - Visor de modelos 3D")
        self.setWindowIcon(app_icon())
        self.resize(1100, 760)
        self.dark = dark
        self.estilos = list(printer3d.MODELS)
        self.bridge = VisorBridge(self)
        self.page = printer3d.Printer3DPage(self.bridge)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(8, 8, 8, 8)
        row = QHBoxLayout()
        row.addWidget(QLabel("Modelo:"))
        self.combo = QComboBox()
        for style in self.estilos:
            self.combo.addItem(printer3d.MODELS[style][1])
        self.combo.currentIndexChanged.connect(self.mostrar)
        row.addWidget(self.combo)
        self.auto = QCheckBox("Recargar al cambiar los archivos")
        self.auto.setChecked(True)
        self.auto.setToolTip("Vuelve a cargar el modelo cuando se regeneran sus mallas o QML.")
        row.addWidget(self.auto)
        recargar = QPushButton("Recargar")
        recargar.clicked.connect(self.page.reload)
        row.addWidget(recargar)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(self.page, 1)
        self.setCentralWidget(central)
        self.mostrar(0)

        self._huella = huella()
        self._vigia = QTimer(self)
        self._vigia.timeout.connect(self._mirar)
        self._vigia.start(1000)

    def mostrar(self, i):
        self.bridge.set_data(datos(self.estilos[i], self.dark))

    def _mirar(self):
        ahora = huella()
        if ahora != self._huella:
            self._huella = ahora
            if self.auto.isChecked():
                # make_model.py writes a style's meshes one by one: wait until it is done
                QTimer.singleShot(1500, self.page.reload)


def main():
    app = QApplication(sys.argv)
    apply_theme(app, True)
    why = printer3d.available()
    ventana = Visor(dark=True)
    ventana.show()
    if why:
        print(why, file=sys.stderr)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
