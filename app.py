"""InkOverflow: Epson waste-ink and maintenance utility, PySide6 front end. HP printers
are read too (hp_backend.py), read only.

The Epson protocol lives in backend/epson_print_conf.py (Ircama/epson_print_conf,
EUPL-1.2), run as a separate process by backend_cli.py. Head cleaning and test
prints go to the Windows print queue through spooler.py.
"""
import base64
import csv
import ctypes
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
    QProgressBar, QScrollArea, QSpinBox, QSplitter, QStackedWidget, QStyleFactory,
    QTableWidget, QTableWidgetItem, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

import backend_cli as be
import cleaning
import detect
import diagnostic
import driver_jobs
import history
import hp_backend
import hp_models
import prefs
import printer3d
import printer_state
import report
import scanner
import spooler
from splash import InkSplash
import testpage
import icons
from widgets import (
    C, RIBBON_BUTTON_HEIGHT, Gauge, InkMeter, MessageBar, PageHeader, RibbonButton, RibbonGroup,
    Task, app_icon, apply_theme, group, is_dark, logo_pixmap,
)

APP_NAME = "InkOverflow"
BACKUP_DIR = be.ROOT / "backups"
SCANS_DIR = be.ROOT / "data" / "escaneos"  # scans of the diagnostic pattern
PAGES = ["Vista 3D", "Resumen", "Detalles", "Mantenimiento", "EEPROM", "Historial"]
TABS = ["Vista 3D", "Inicio", "Detalles", "Mantenimiento", "EEPROM", "Historial"]  # ribbon tab of each page
MONTHS = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
# Time the printer needs before its counters reflect a maintenance job (ms).
WAIT_MS = {"check": 60_000, "clean": 90_000, "power": 170_000, "feed": 15_000}
# First entry of the model selector: the model is whatever is plugged in right now.
AUTO_LABEL = "Automático"
RESET_HINT = ("Simular no escribe nada. El reseteo temporal se pierde al reiniciar la "
              "impresora. El permanente reescribe la EEPROM y guarda antes una copia en la "
              "carpeta backups. Ninguno sustituye a las almohadillas.")
HP_RESET_HINT = ("En las HP los reseteos están deshabilitados: HP no documenta un contador "
                 "de almohadillas ni una forma segura de resetearlo, e InkFlow no escribe "
                 "nada en una HP. Si el absorbente está lleno, se cambia en servicio técnico.")
HP_NO_MAINT = ("Los tests de inyectores y las limpiezas por USB de InkFlow son comandos "
               "Epson: no se mandan a una HP. En la HP se hacen desde su panel o desde HP "
               "Smart (Herramientas › Limpiar cabezales).")
HP_NO_EEPROM = "Las HP no tienen una EEPROM que InkFlow sepa leer."
HP_PADS = ("HP no publica un contador de almohadillas (absorbente de tinta) para sus "
           "impresoras de tanque, ni un reseteo documentado: no hay nada que leer ni "
           "resetear desde aquí. Si el absorbente se llena, la propia impresora lo avisa "
           "y aparece en Avisos.")
HP_USB_ONLY = ("Por USB, Windows solo identifica la HP (modelo y serie). Para leer tinta, "
               "estado y contadores escribí su IP en «HP por red» (la muestra su panel o "
               "la página de configuración de red) y pulsá Actualizar.")


@dataclass
class Reading:
    """What one Actualizar found: the detection always, the printer's data only when a
    model was known and the read worked."""
    found: detect.Detection
    model: str = ""
    info: dict = None
    cells: dict = None
    queues: list = None
    error: str = ""


def pct_text(pct):
    return "--" if pct is None else f"{pct:.1f}%"


def age_since(text):
    """'16 Mar 2020' -> (date, '6 años y 7 meses'), or (None, None)."""
    match = re.match(r"(\d+)\s+(\w{3})\w*\s+(\d{4})", text or "")
    if not match or match.group(2) not in MONTHS:
        return None, None
    first = date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)))
    months = (date.today().year - first.year) * 12 + date.today().month - first.month
    return first, f"{months // 12} años y {months % 12} meses"


def poweroff_text(snmp_text):
    match = re.search(r"ot:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})", snmp_text or "")
    if not match:
        return "--"
    minutes = int(match.group(2), 16)
    return "Desactivado" if minutes == 0xFFFF else f"{minutes} min"


def clean_progress(elapsed, typical):
    """Bar value (0-99) of a cleaning that usually takes `typical` seconds. It never
    reaches 100 by itself: only the printer going idle again ends the job."""
    return max(0, min(99, int(elapsed / typical * 100)))


def remaining_text(elapsed, typical):
    left = typical - elapsed
    if left > 5:
        return f"quedan unos {int(left) // 60}:{int(left) % 60:02d}"
    if elapsed <= typical + 30:
        return "debería terminar enseguida"
    return "tarda más de lo habitual; no toques la impresora"


def cell_tooltip(addr, value, is_reset_cell=False):
    """Hover text of one EEPROM cell: address and value in every base."""
    head = f"Celda {addr} (0x{addr:04X})"
    text = (f"{head}: sin lectura" if value is None
            else f"{head} = 0x{value:02X} · {value} · {value:08b}b")
    if is_reset_cell:
        text += "\nSe reescribe en el reseteo de contadores"
    return text


class ConfirmDialog(QDialog):
    def __init__(self, parent, title, summary, check_text, ok_text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        head = QLabel(title)
        head.setObjectName("h1")
        lay.addWidget(head)
        body = QLabel(summary)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.check = QCheckBox(check_text)
        lay.addWidget(self.check)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        ok = buttons.button(QDialogButtonBox.Ok)
        ok.setText(ok_text)
        ok.setObjectName("danger")
        ok.setEnabled(False)
        self.check.toggled.connect(ok.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


class DiagnosticDialog(QDialog):
    """What the scan of the diagnostic pattern shows: the straightened sheet with every
    finding outlined, and the list of findings with what to do."""
    DOTS = {"ok": "ok", "info": "blue", "warn": "warn", "bad": "bad"}

    def __init__(self, parent, result, image_path):
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico por escaneo")
        self.result, self.image_path = result, image_path
        lay = QHBoxLayout(self)
        picture = QLabel()
        picture.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        pixmap = QPixmap.fromImage(diagnostic.annotated(result))
        picture.setPixmap(pixmap.scaledToHeight(620, Qt.SmoothTransformation))
        picture.setStyleSheet(f"border: 1px solid {C['line']}; background: #ffffff;")
        lay.addWidget(picture, 0, Qt.AlignTop)
        side = QVBoxLayout()
        headline = QLabel(self._headline(result))
        headline.setWordWrap(True)
        headline.setStyleSheet(f"font-size: 15px; font-weight: 600; "
                               f"color: {C[self.DOTS[result.level]]};")
        side.addWidget(headline)
        text = QTextBrowser()
        text.setOpenLinks(False)
        text.setHtml(self.html(result))
        text.setMinimumWidth(430)
        side.addWidget(text, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("Cerrar")
        if image_path:
            open_btn = buttons.addButton("Abrir imagen", QDialogButtonBox.ActionRole)
            open_btn.setToolTip(str(image_path))
            open_btn.clicked.connect(lambda: os.startfile(image_path))
        buttons.rejected.connect(self.reject)
        side.addWidget(buttons)
        lay.addLayout(side, 1)
        self.resize(960, 680)

    @staticmethod
    def _headline(result):
        problems = result.problems()
        if not problems:
            return "Sin fallas a la vista: la impresora imprime bien."
        return f"{len(problems)} problema(s) encontrado(s)."

    @classmethod
    def html(cls, result):
        parts = []
        for f in result.findings:
            if f.level == "ok":
                continue
            color = C[cls.DOTS[f.level]]
            block = (f"<p><span style='color:{color}'>&#9679;</span> <b>{escape(f.title)}</b>"
                     f"<br>{escape(f.detail)}")
            if f.action:
                block += f"<br><i>Qué hacer:</i> {escape(f.action)}"
            parts.append(block + "</p>")
        good = [f for f in result.findings if f.level == "ok"]
        if good:
            parts.append(f"<p><span style='color:{C['ok']}'>&#9679;</span> <b>Bien:</b> "
                         + "; ".join(f"{escape(f.title.split(':')[0])} "
                                     f"<span style='color:{C['muted']}'>({escape(f.detail)})"
                                     "</span>" for f in good) + "</p>")
        parts.append(f"<p style='color:{C['muted']}'>Recuadros en la hoja: rojo, falla; "
                     "ámbar, conviene revisar; verde, bien. La imagen marcada se guardó en la "
                     "carpeta de informes y queda en el Historial.</p>")
        return "".join(parts)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1120, 780)
        self.pool = QThreadPool.globalInstance()
        self.info, self.cells, self.points, self.queues, self.usb = {}, {}, {}, [], []
        self.alerts = []          # printer_state.Alert list of the last reading
        self.detection = None     # detect.Detection of the last Actualizar
        self.detected_model = ""  # the model plugged in, while the selector is on Automático
        self.brand = ""           # "epson" or "hp": who makes the printer that was read
        self.dump_cells = {}
        self._details_args = None  # last _render_details() arguments, to repaint on a theme change
        self._chip_state = ("Sin conexión", C["muted"])
        self.busy = False
        # what the printer is doing because of us, for the 3D view: ("printing" or
        # "cleaning", what), or ("", "") when nothing was sent
        self.activity = ("", "")
        self.on_booted = None  # called once the model database has loaded (the splash)
        self.points_before = None
        self.guarded = []  # buttons that need a connected, idle printer
        self._history_pinned = False  # the user picked a printer in the Historial list
        self._clean_state = {"text": "", "elapsed": 0.0, "typical": 190}
        self._clean_timer = QTimer(self)
        self._clean_timer.timeout.connect(self._tick_clean)

        # Vista 3D: another face of the same data; its requests go through the same
        # methods (and dialogs) as the ribbon buttons.
        self.bridge3d = printer3d.Bridge(self)
        self.bridge3d.refreshRequested.connect(self._refresh_shortcut)
        self.bridge3d.resetRequested.connect(self._reset_from_3d)
        self.bridge3d.backupRequested.connect(self._backup_from_3d)
        self.bridge3d.actionRequested.connect(self._action_from_3d)

        self.stack = QStackedWidget()
        for build in (self._page_3d, self._page_summary, self._page_details,
                      self._page_maintenance, self._page_eeprom, self._page_history):
            self.stack.addWidget(build())
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._ribbon())
        self.banner = MessageBar()
        self.banner.hide()
        outer.addWidget(self.banner)
        outer.addWidget(self._wait_strip())
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self.stack)
        split.addWidget(self._log_pane())
        split.setStretchFactor(0, 1)
        split.setSizes([560, 140])
        outer.addWidget(split, 1)
        self._status_bar()

        self._shortcuts = []
        self._add_shortcuts()
        self._restore_prefs()
        self._render_history()  # past work is readable before (or without) a printer
        self._log("Cargando la base de modelos...")
        self._run(be.models, self._booted)

    # ---- preferences, shortcuts, closing ----------------------------------
    def _add_shortcuts(self):
        def add(keys, slot):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)
            self._shortcuts.append(shortcut)

        add("F5", self._refresh_shortcut)
        add("Ctrl+R", self._refresh_shortcut)
        for index in range(len(PAGES)):
            add(f"Ctrl+{index + 1}", lambda i=index: self.nav.button(i).click())

    def _refresh_shortcut(self):
        # Same rule as the button: never a new USB session while something is running.
        if self.btn_refresh.isEnabled():
            self.refresh()

    def _restore_prefs(self):
        encoded = prefs.load().get("geometry")
        if isinstance(encoded, str):
            try:
                self.restoreGeometry(base64.b64decode(encoded))
            except ValueError:
                pass
        self.nav.button(prefs.get_int("page", 0, 0, len(PAGES) - 1)).click()
        self.sp_start.setValue(prefs.get_int("eeprom_start", 0, 0, 2047))
        self.sp_end.setValue(prefs.get_int("eeprom_end", 255, 0, 2047))
        host = prefs.load().get("hp_host")
        self.hp_host.setText(host if isinstance(host, str) else "")

    def closeEvent(self, event):
        if self._clean_timer.isActive():
            # The cleaning (and the counter restore after it) runs in this process.
            QMessageBox.warning(
                self, "Limpieza en curso",
                "La limpieza sigue en marcha y no se puede cancelar. Si cierras ahora, la "
                "aplicación no leerá el contador final ni lo anotará en el historial. "
                "Espera a que termine.")
            event.ignore()
            return
        prefs.save(geometry=base64.b64encode(bytes(self.saveGeometry())).decode("ascii"),
                   page=self.stack.currentIndex(), eeprom_start=self.sp_start.value(),
                   eeprom_end=self.sp_end.value())
        super().closeEvent(event)

    def _booted(self, db, error):
        if self.on_booted:
            hook, self.on_booted = self.on_booted, None
            hook()
        if error:
            self._log(f"Error: {error}")
            return
        # Entry 0 is Automático; the models follow. Nothing is preselected: which one is
        # plugged in is found by refresh(), from what Windows reports, before anything
        # remembered is read.
        self.model.blockSignals(True)
        for name in sorted(db):
            self.model.addItem(name, name)
        self.model.setCurrentIndex(0)
        self.model.blockSignals(False)
        self.model.currentIndexChanged.connect(lambda _: self.refresh())
        self._log(f"{len(db)} modelos disponibles.")
        self.refresh()

    # ---- layout: ribbon ---------------------------------------------------
    def _ribbon(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        tabrow = QFrame()
        tabrow.setObjectName("tabrow")
        row = QHBoxLayout(tabrow)
        row.setContentsMargins(2, 0, 8, 0)
        row.setSpacing(0)
        filebtn = QToolButton()
        filebtn.setObjectName("filebtn")
        filebtn.setText("Archivo")
        filebtn.setPopupMode(QToolButton.InstantPopup)
        filebtn.setMenu(self._file_menu())
        row.addWidget(filebtn, 0, Qt.AlignBottom)
        self.qa_refresh = QToolButton()
        self.qa_refresh.setObjectName("qat")
        self.qa_refresh.setIcon(icons.icon("refresh"))
        self.qa_refresh.setIconSize(QSize(16, 16))
        self.qa_refresh.setToolTip("Actualizar (F5)")
        self.qa_refresh.clicked.connect(self._refresh_shortcut)
        row.addWidget(self.qa_refresh, 0, Qt.AlignVCenter)
        row.addSpacing(6)
        self.nav = QButtonGroup(self)
        for index, name in enumerate(TABS):
            btn = QToolButton()
            btn.setObjectName("rtab")
            btn.setText(name)
            btn.setCheckable(True)
            btn.setChecked(index == 0)
            btn.setToolTip(f"{PAGES[index]} (Ctrl+{index + 1})")
            self.nav.addButton(btn, index)
            row.addWidget(btn, 0, Qt.AlignBottom)
        self.nav.idClicked.connect(self._select_page)
        row.addStretch()
        self.logo = QLabel()
        pixmap = logo_pixmap(height=20, light=not is_dark())
        if pixmap is None:
            self.logo.setText(APP_NAME)
            self.logo.setObjectName("h1")
        else:
            self.logo.setPixmap(pixmap)
        self.logo.setToolTip(f"{APP_NAME} · El contador miente. Nosotros llevamos la cuenta.")
        row.addWidget(self.logo, 0, Qt.AlignVCenter)
        lay.addWidget(tabrow)

        ribbon = QFrame()
        ribbon.setObjectName("ribbon")
        ribbon.setFixedHeight(RIBBON_BUTTON_HEIGHT + 24)
        inner = QHBoxLayout(ribbon)
        inner.setContentsMargins(2, 0, 2, 0)
        self.ribbon_stack = QStackedWidget()
        for build in (self._rb_3d, self._rb_home, self._rb_details, self._rb_maintenance,
                      self._rb_eeprom, self._rb_history):
            panel = QWidget()
            panel_lay = QHBoxLayout(panel)
            panel_lay.setContentsMargins(0, 0, 0, 0)
            panel_lay.setSpacing(0)
            for grp in build():
                panel_lay.addWidget(grp)
            panel_lay.addStretch()
            self.ribbon_stack.addWidget(panel)
        inner.addWidget(self.ribbon_stack)
        lay.addWidget(ribbon)
        return box

    def _file_menu(self):
        menu = QMenu(self)
        entries = [
            ("refresh", "Actualizar\tF5", self._refresh_shortcut),
            None,
            ("folder_report", "Abrir la carpeta de informes", lambda: self._open_folder(report.REPORTS)),
            ("folder_backup", "Abrir la carpeta de copias", lambda: self._open_folder(BACKUP_DIR)),
            ("csv", "Exportar el historial (CSV)...", lambda: self.export_history()),
            None,
            ("info", f"Acerca de {APP_NAME}", self._about),
            ("exit", "Salir", self.close),
        ]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            name, text, slot = entry
            menu.addAction(icons.icon(name), text).triggered.connect(slot)
            if name == "csv":
                self.act_dark = menu.addAction("Modo oscuro")
                self.act_dark.setCheckable(True)
                self.act_dark.setChecked(is_dark())
                self.act_dark.toggled.connect(self._set_dark)
        return menu

    def _set_dark(self, on):
        """Switch theme live and redo what was painted with the old colours."""
        apply_theme(QApplication.instance(), on)
        prefs.save(dark=bool(on))
        pixmap = logo_pixmap(height=20, light=not on)
        if pixmap is not None:
            self.logo.setPixmap(pixmap)
        self._set_chip(*self._chip_state)
        self.clean_note.setStyleSheet(f"color: {C['warn']}; font-weight: 600;")
        self.preview.setStyleSheet(f"border: 1px solid {C['line']}; background: {C['preview']};")
        if self._details_args:
            self._render_details(*self._details_args)
        if self.info:
            self._render_alerts()
        if self.dump_cells:
            self._dump_done(self.dump_cells, None, quiet=True)
        self._sync_3d()
        self.update()

    def _about(self):
        QMessageBox.about(
            self, f"Acerca de {APP_NAME}",
            f"<b>{APP_NAME}</b><br>El contador miente. Nosotros llevamos la cuenta.<br><br>"
            "Contadores de tinta residual, pruebas y limpieza de cabezales para impresoras "
            "Epson por USB. Lectura de impresoras HP (modelo, serie, estado, tinta y uso) "
            "por USB y por la red.<br><br>Creado por <b>Ulik</b><br>Arquitectura de software e "
            "ingeniería inversa de reseteadores.<br><br>Protocolo de impresora: "
            "Ircama/epson_print_conf (EUPL-1.2).<br>MAG Tecnología")

    def _select_page(self, index):
        self.stack.setCurrentIndex(index)
        self.ribbon_stack.setCurrentIndex(index)

    def _rb_3d(self):
        printer = RibbonGroup("Impresora")
        self.btn_refresh3d = printer.add(RibbonButton(
            "refresh", "Actualizar",
            "Busca la impresora Epson o HP conectada por USB (o la HP de la IP escrita) "
            "y lee su estado, contadores y datos. Solo lee: no escribe nada en la "
            "impresora.", shortcut="F5"))
        self.btn_refresh3d.clicked.connect(self.refresh)
        camera = RibbonGroup("Cámara")
        for icon, text, desc, name in (
                ("printer", "Frente", "Vuelve a la vista general de la impresora.", "front"),
                ("color", "Tanques", "Acerca la cámara a los tanques de tinta.", "tanks"),
                ("maintenance", "Almohadillas",
                 "Gira hasta la tapa trasera de las almohadillas de tinta residual.", "pads"),
                ("summary", "Girar", "Activa o detiene el giro automático.", "spin")):
            btn = camera.add(RibbonButton(icon, text, desc))
            btn.clicked.connect(lambda _=False, n=name: self.bridge3d.cameraRequested.emit(n))
        return printer, camera

    def _rb_home(self):
        printer = RibbonGroup("Impresora")
        self.btn_refresh = printer.add(RibbonButton(
            "refresh", "Actualizar",
            "Busca la impresora Epson o HP conectada por USB (o la HP de la IP escrita) "
            "y lee su estado, contadores y datos. Solo lee: no escribe nada en la "
            "impresora.", shortcut="F5"))
        self.btn_refresh.clicked.connect(self.refresh)
        self.model = QComboBox()
        self.model.addItem(f"{AUTO_LABEL} · buscando...", "")
        self.model.setMinimumWidth(240)
        self.model.setMaxVisibleItems(25)
        self.model.setToolTip("Automático: el modelo de la impresora conectada por USB. "
                              "Si eliges un modelo, manda tu elección hasta que vuelvas a "
                              "elegir Automático.")
        printer.column("Modelo:", self.model)
        self.hp_host = QLineEdit()
        self.hp_host.setPlaceholderText("IP de la HP (opcional)")
        self.hp_host.setClearButtonEnabled(True)
        self.hp_host.setToolTip(
            "Dirección de red de una HP (por ejemplo 192.168.0.25). Por USB, Windows solo "
            "identifica la HP; la tinta, el estado y los contadores se leen por la red "
            "(IPP y la página web de la impresora). Solo lectura. Si la HP tiene una cola "
            "de Windows por TCP/IP, la IP se toma de ahí.")
        self.hp_host.editingFinished.connect(
            lambda: prefs.save(hp_host=self.hp_host.text().strip()))
        printer.column("HP por red (IP):", self.hp_host, width=170)

        counters = RibbonGroup("Contadores de almohadillas")
        self.btn_backup = self._guard(counters.add(RibbonButton(
            "save", "Guardar\ncopia",
            "Lee las celdas de los contadores y las guarda en un archivo JSON en la "
            "carpeta backups. No escribe nada.")))
        self.btn_dry = self._guard(counters.add(RibbonButton(
            "simulate", "Simular\nreseteo",
            "Muestra lo que haría el reseteo sin escribir nada en la impresora.")))
        self.btn_temp = self._guard(counters.add(RibbonButton(
            "reset_temp", "Reseteo\ntemporal",
            "Quita el aviso de almohadillas hasta que se reinicie la impresora. No "
            "modifica la EEPROM.")))
        self.btn_perm = self._guard(counters.add(RibbonButton(
            "reset_perm", "Reseteo\npermanente",
            "Reescribe los contadores en la EEPROM. Antes guarda una copia en la carpeta "
            "backups. No sustituye a las almohadillas: si están saturadas, cámbialas.")))
        self.btn_backup.clicked.connect(self.backup)
        self.btn_dry.clicked.connect(lambda: self.reset("dry"))
        self.btn_temp.clicked.connect(lambda: self.reset("temp"))
        self.btn_perm.clicked.connect(lambda: self.reset("perm"))
        self.reset_buttons = (self.btn_backup, self.btn_dry, self.btn_temp, self.btn_perm)

        share = RibbonGroup("Informe")
        self.btn_report = self._guard(share.add(RibbonButton(
            "pdf", "Informe\nPDF",
            "Crea el informe de servicio en PDF (cabecera MAG) con los contadores, el uso y "
            "el historial de la impresora, y lo abre.")))
        self.btn_report.clicked.connect(self.make_report)
        self.btn_summary = self._guard(RibbonButton(
            "clipboard", "Copiar resumen",
            "Copia al portapapeles las cifras clave en texto, listas para pegar en un "
            "chat con el cliente.", large=False))
        self.btn_summary.clicked.connect(self.copy_summary)
        share.column(self.btn_summary)
        return printer, counters, share

    def _rb_details(self):
        data = RibbonGroup("Datos")
        self.btn_copy = data.add(RibbonButton(
            "copy", "Copiar\ntodo", "Copia la tabla de detalles al portapapeles como texto."))
        self.btn_json = data.add(RibbonButton(
            "json", "Exportar\nJSON",
            "Guarda todo lo que informó la impresora, sin procesar, en la carpeta backups."))
        self.btn_copy.clicked.connect(self.copy_details)
        self.btn_json.clicked.connect(self.export_json)
        share = RibbonGroup("Informe")
        self.btn_report2 = self._guard(share.add(RibbonButton(
            "pdf", "Informe\nPDF",
            "Crea el informe de servicio en PDF (cabecera MAG) y lo abre.")))
        self.btn_report2.clicked.connect(self.make_report)
        return data, share

    def _rb_maintenance(self):
        tests = RibbonGroup("Pruebas de impresión")
        self.btn_nozzle = self._guard(tests.add(RibbonButton(
            "nozzle", "Test de\ninyectores",
            "Imprime el patrón de inyectores directamente por USB. Usa una hoja y muy poca "
            "tinta: carga papel antes.")))
        self.btn_nozzle2 = self._guard(tests.add(RibbonButton(
            "nozzle2", "Test\nalternativo",
            "Variante del test de inyectores, para modelos que no responden al normal.")))
        self.btn_color = self._guard(tests.add(RibbonButton(
            "color", "Patrón\nde color", "Imprime el patrón de color de la impresora por USB.")))
        paper = RibbonGroup("Papel")
        self.btn_feed = self._guard(paper.add(RibbonButton(
            "feed", "Expulsar\nhoja",
            "Hace girar los rodillos una vez para sacar una hoja que quedó a medio salir "
            "(o pasar una en blanco). No usa tinta. No sirve para papel trabado: retíralo "
            "a mano.")))
        self.btn_feed.clicked.connect(lambda: self.maintenance(
            "Expulsar hoja", spooler.feed_sheet_job, "feed", False))
        self.maint_buttons = [self.btn_nozzle, self.btn_nozzle2, self.btn_color, self.btn_feed]
        self.btn_nozzle.clicked.connect(lambda: self.maintenance(
            "Test de inyectores", self._nozzle_job(), "check", False))
        self.btn_nozzle2.clicked.connect(lambda: self.maintenance(
            "Test de inyectores (alternativo)", lambda: spooler.nozzle_check(1), "check", False))
        self.btn_color.clicked.connect(lambda: self.maintenance(
            "Patrón de color", spooler.color_pattern, "check", False))

        clean = RibbonGroup("Limpieza de cabezales")
        self.clean_mode = QComboBox()
        for key, label, _byte, _typical, _patience in cleaning.MODES:
            self.clean_mode.addItem(label, key)
        self.restore_check = QCheckBox("Restaurar el contador al terminar")
        self.restore_check.setToolTip(
            "La limpieza no se cuenta en el contador, pero la tinta sí va a la "
            "almohadilla: esos puntos se anotan para estimar el nivel real.")
        clean.column("Modo:", self.clean_mode, self.restore_check, width=250)
        self.clean_mode.currentIndexChanged.connect(lambda *_: self._sync_3d())
        self.btn_clean = self._guard(clean.add(RibbonButton(
            "clean", "Limpiar\ncabezales",
            "Envía la limpieza elegida por USB. Dura unos minutos, no se puede cancelar y "
            "vierte tinta a las almohadillas.")))
        self.btn_clean.clicked.connect(self.clean_heads)

        page = RibbonGroup("Página de prueba MAG")
        self.print_queue = QComboBox()
        self.print_queue.setMinimumWidth(200)
        page.column("Cola de Windows:", self.print_queue)
        self.page_version = QComboBox()
        for key, (name, _path, ink) in testpage.VERSIONS.items():
            self.page_version.addItem(name, key)
            self.page_version.setItemData(self.page_version.count() - 1, ink, Qt.ToolTipRole)
        saved = prefs.load().get("testpage_version")
        index = self.page_version.findData(saved if saved in testpage.VERSIONS else testpage.DEFAULT)
        self.page_version.setCurrentIndex(max(index, 0))
        self.page_version.setToolTip("Qué versión de la página de prueba se imprime. «Ahorro "
                                     "máximo» gasta la cuarta parte de tinta que la original.")
        self.page_version.currentIndexChanged.connect(self._page_version_changed)
        page.column("Versión:", self.page_version, width=165)
        self._show_page_version()
        self.btn_testpage = self._guard(page.add(RibbonButton(
            "testpage", "Imprimir\npágina",
            "Imprime la página de prueba A4 elegida en «Versión» por la cola de Windows "
            "elegida.")))
        self.btn_testpage.clicked.connect(self.print_test_page)

        diag = RibbonGroup("Diagnóstico por escaneo")
        self.btn_diag_print = self._guard(diag.add(RibbonButton(
            "diag_print", "Imprimir\npatrón",
            "Imprime el patrón de diagnóstico (A4, poca tinta) por la cola elegida en «Página "
            "de prueba MAG». Después se escanea y la aplicación busca las fallas.")))
        self.btn_diag_print.clicked.connect(self.print_diagnostic)
        self.btn_diag_scan = diag.add(RibbonButton(
            "scan", "Escanear y\nanalizar",
            "Escanea el patrón impreso con el escáner de Windows (el de la multifunción u "
            "otro) y muestra qué fallas encontró. No usa la sesión de la impresora."))
        self.btn_diag_scan.clicked.connect(self.scan_diagnostic)
        self.btn_diag_open = diag.add(RibbonButton(
            "diag_open", "Analizar\nimagen",
            "Analiza un escaneo del patrón ya guardado (PNG, JPG, BMP, TIFF o PDF). No hace "
            "falta tener la impresora conectada."))
        self.btn_diag_open.clicked.connect(self.open_diagnostic)
        self.diag_free = [self.btn_diag_scan, self.btn_diag_open]  # only need an idle app
        return tests, paper, clean, page, diag

    def _rb_eeprom(self):
        span = RibbonGroup("Rango de celdas")
        self.sp_start, self.sp_end = QSpinBox(), QSpinBox()
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(2, 4, 2, 0)
        grid.setVerticalSpacing(4)
        for row, (text, sp, value) in enumerate((("Desde:", self.sp_start, 0),
                                                 ("Hasta:", self.sp_end, 255))):
            sp.setRange(0, 2047)
            sp.setValue(value)
            sp.setMinimumWidth(80)
            label = QLabel(text)
            label.setObjectName("rlabel")
            grid.addWidget(label, row, 0)
            grid.addWidget(sp, row, 1)
        grid.setRowStretch(2, 1)
        span.add(holder)
        read = RibbonGroup("Lectura")
        self.btn_dump = self._guard(read.add(RibbonButton(
            "chip_read", "Leer\nEEPROM",
            "Lee las celdas del rango elegido (unos 40 s para 2048 celdas). Solo lectura.")))
        self.btn_dump.clicked.connect(self.read_dump)
        self.btn_csv = read.add(RibbonButton(
            "csv", "Exportar\nCSV", "Guarda la última lectura en un archivo CSV."))
        self.btn_csv.clicked.connect(self.export_dump)
        return span, read

    def _rb_history(self):
        who = RibbonGroup("Impresora")
        self.history_who = QComboBox()
        self.history_who.setMinimumWidth(280)
        self.history_who.activated.connect(self._history_picked)
        who.column("Mostrar:", self.history_who)
        export = RibbonGroup("Exportar")
        self.btn_hist_csv = export.add(RibbonButton(
            "csv", "Exportar\nCSV", "Guarda en CSV las operaciones de la lista."))
        self.btn_hist_csv.clicked.connect(self.export_history)
        folders = RibbonGroup("Carpetas")
        self.btn_open_reports = folders.add(RibbonButton(
            "folder_report", "Informes", "Abre la carpeta con los informes PDF."))
        self.btn_open_reports.clicked.connect(lambda: self._open_folder(report.REPORTS))
        self.btn_open_backups = folders.add(RibbonButton(
            "folder_backup", "Copias",
            "Abre la carpeta con las copias de los contadores y las exportaciones."))
        self.btn_open_backups.clicked.connect(lambda: self._open_folder(BACKUP_DIR))
        return who, export, folders

    # ---- layout: message strips, log, status bar --------------------------
    def _wait_strip(self):
        """Progress of whatever is running, under the ribbon so every page shows it."""
        self.wait_frame = QFrame()
        self.wait_frame.setObjectName("waitbar")
        row = QHBoxLayout(self.wait_frame)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        pic = QLabel()
        pic.setPixmap(icons.icon("info").pixmap(16, 16))
        row.addWidget(pic, 0, Qt.AlignTop)
        self.wait_label = QLabel("")
        self.wait_label.setWordWrap(True)
        row.addWidget(self.wait_label, 1)
        self.wait_bar = QProgressBar()
        self.wait_bar.setRange(0, 0)
        self.wait_bar.setTextVisible(False)
        self.wait_bar.setFixedSize(220, 14)
        row.addWidget(self.wait_bar, 0, Qt.AlignVCenter)
        self.wait_frame.hide()
        return self.wait_frame

    def _log_pane(self):
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        caption = QLabel("Registro de actividad")
        caption.setObjectName("paneCaption")
        lay.addWidget(caption)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setObjectName("log")
        lay.addWidget(self.log)
        return pane

    def _status_bar(self):
        bar = self.statusBar()
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.title = QLabel("Impresora Epson")
        self.title.setObjectName("sbtext")
        self.title.setStyleSheet("font-weight: 600;")
        self.subtitle = QLabel("Buscando por USB...")
        self.subtitle.setObjectName("sbtext")
        bar.addWidget(self.chip)
        bar.addWidget(self.title)
        bar.addWidget(self.subtitle, 1)
        keys = QLabel(f"F5 Actualizar · Ctrl+1…{len(PAGES)} Pestañas")
        keys.setObjectName("sbtext")
        bar.addPermanentWidget(keys)
        self._set_chip("Sin conexión", C["muted"])

    # ---- layout: pages ----------------------------------------------------
    def _page(self, icon_name, title, desc):
        page = QWidget()
        page.setObjectName("page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(PageHeader(icon_name, title, desc))
        lay = QVBoxLayout()
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        outer.addLayout(lay, 1)
        return page, lay

    def _guard(self, button):
        self.guarded.append(button)
        return button

    def _page_3d(self):
        self.page3d = printer3d.Printer3DPage(self.bridge3d)
        return self.page3d

    def _page_summary(self):
        page, lay = self._page(
            "summary", "Resumen",
            "Nivel de las almohadillas de tinta residual, tinta, avisos y uso general de la "
            "impresora conectada. Los reseteos están en la cinta, grupo Contadores.")
        top = QHBoxLayout()
        top.setSpacing(10)
        waste = group("Almohadillas de tinta residual")
        self.gauge_row = QVBoxLayout()
        self.gauge_row.setSpacing(12)
        self.gauges = {}
        waste.lay.addLayout(self.gauge_row)
        self.waste_note = QLabel("")
        self.waste_note.setWordWrap(True)
        waste.lay.addWidget(self.waste_note)
        waste.lay.addStretch()
        top.addWidget(waste, 3)

        usage = group("Uso de la impresora")
        self.usage = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        for i, key in enumerate(["Estado", "Páginas impresas", "Pasadas del cabezal",
                                 "Escaneos", "Primera tinta instalada", "Antigüedad",
                                 "Depósito mantenimiento"]):
            k = QLabel(key + ":")
            k.setObjectName("key")
            v = QLabel("--")
            v.setObjectName("value")
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(k, i, 0, Qt.AlignTop)
            grid.addWidget(v, i, 1)
            self.usage[key] = v
        grid.setColumnStretch(1, 1)
        usage.lay.addLayout(grid)
        usage.lay.addStretch()
        top.addWidget(usage, 2)
        lay.addLayout(top, 1)

        middle = QHBoxLayout()
        middle.setSpacing(10)
        ink = group("Tinta")
        self.ink_row = QHBoxLayout()
        self.ink_row.setSpacing(4)
        ink.lay.addLayout(self.ink_row)
        self.ink_note = QLabel("Sin lectura.")
        self.ink_note.setObjectName("muted")
        self.ink_note.setWordWrap(True)
        ink.lay.addWidget(self.ink_note)
        ink.lay.addStretch()
        middle.addWidget(ink, 2)
        warnings = group("Avisos de la impresora")
        self.alerts_label = QLabel("Sin lectura.")
        self.alerts_label.setWordWrap(True)
        self.alerts_label.setTextFormat(Qt.RichText)
        self.alerts_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.alerts_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        warnings.lay.addWidget(self.alerts_label)
        warnings.lay.addStretch()
        middle.addWidget(warnings, 3)
        lay.addLayout(middle)

        notes = group("Sobre los reseteos")
        hint = QLabel(RESET_HINT)
        self.reset_hint = hint
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        notes.lay.addWidget(hint)
        lay.addWidget(notes)
        return page

    def _page_details(self):
        page, lay = self._page(
            "details", "Detalles",
            "Todo lo que informa la impresora: identificación, estado, uso, mantenimiento "
            "y conexión.")
        self.details = QTableWidget(0, 2)
        self.details.horizontalHeader().hide()
        self.details.verticalHeader().hide()
        self.details.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.details.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.details.setSelectionMode(QAbstractItemView.NoSelection)
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.setShowGrid(True)
        lay.addWidget(self.details, 1)
        return page

    def _page_maintenance(self):
        page, lay = self._page(
            "maintenance", "Mantenimiento",
            "Pruebas de impresión, limpieza de cabezales y página de prueba. Los comandos "
            "están en la cinta; aquí, a qué impresora van y qué conviene saber.")
        target = group("Destino")
        self.queue_note = QLabel("")
        self.queue_note.setWordWrap(True)
        target.lay.addWidget(self.queue_note)
        lay.addWidget(target)

        clean = group("Limpieza de cabezales")
        warn = QLabel("Cada limpieza vierte tinta a las almohadillas. Por defecto el "
                      "contador sube lo que sube la impresora y la aplicación muestra "
                      "cuánto. Si marcas «Restaurar el contador», vuelve a su valor anterior "
                      "pero la tinta ya está en la almohadilla: esos puntos se anotan para "
                      "estimar el nivel real.")
        warn.setObjectName("muted")
        warn.setWordWrap(True)
        clean.lay.addWidget(warn)
        self.clean_note = QLabel("")
        self.clean_note.setWordWrap(True)
        self.clean_note.setStyleSheet(f"color: {C['warn']}; font-weight: 600;")
        clean.lay.addWidget(self.clean_note)
        lay.addWidget(clean)

        mag = group("Página de prueba MAG")
        body = QHBoxLayout()
        body.setSpacing(12)
        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        preview.setStyleSheet(f"border: 1px solid {C['line']}; background: {C['preview']};")
        self.preview = preview
        preview.setFixedSize(152, 214)
        body.addWidget(preview)
        info = QLabel("Hoja A4 con franjas verticales de color (un inyector tapado se ve "
                      "como una raya blanca que las cruza), escala de grises, líneas finas, "
                      "tamaños de texto y marcas de registro. La versión se elige en la "
                      "cinta; «Ahorro máximo» es la que menos tinta gasta y no empapa la "
                      "hoja. Elige la cola marcada como «conectada».")
        info.setObjectName("muted")
        info.setWordWrap(True)
        self.version_note = QLabel("")
        self.version_note.setWordWrap(True)
        text = QVBoxLayout()
        text.addWidget(info)
        text.addWidget(self.version_note)
        text.addStretch()
        body.addLayout(text, 1)
        mag.lay.addLayout(body)
        lay.addWidget(mag)

        diag = group("Diagnóstico por escaneo")
        body = QHBoxLayout()
        body.setSpacing(12)
        sheet = QLabel()
        sheet.setAlignment(Qt.AlignCenter)
        sheet.setStyleSheet(f"border: 1px solid {C['line']}; background: #ffffff;")
        sheet.setPixmap(QPixmap.fromImage(diagnostic.render(18)))
        sheet.setFixedSize(152, 214)
        body.addWidget(sheet)
        about = QLabel(
            "1. «Imprimir patrón»: una hoja A4 con bloques de cian, magenta, amarillo y "
            "negro, líneas finas y una zona en blanco (gasta poca tinta).<br>"
            "2. «Escanear y analizar»: pon la hoja boca abajo en el vidrio del escáner; puede "
            "ir torcida o al revés. Si la escaneas con otro programa o con el celular, usa "
            "«Analizar imagen».<br>"
            "3. La aplicación marca lo que encontró y qué hacer: inyectores tapados (rayas "
            "blancas), un color que no sale, sale flojo o mezclado, el cabezal desalineado, el "
            "papel que avanza a tirones y manchas de tinta o de rodillos.")
        about.setObjectName("muted")
        about.setWordWrap(True)
        self.diag_note = QLabel("Todavía no se analizó ningún patrón en esta sesión.")
        self.diag_note.setWordWrap(True)
        text = QVBoxLayout()
        text.addWidget(about)
        text.addWidget(self.diag_note)
        text.addStretch()
        body.addLayout(text, 1)
        diag.lay.addLayout(body)
        lay.addWidget(diag)
        lay.addStretch()
        self._show_page_version()

        scroll = QScrollArea()  # the page is taller than a small window
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _page_eeprom(self):
        page, lay = self._page(
            "chip", "EEPROM (solo lectura)",
            "Las celdas en verde son las que reescribe el reseteo de contadores. Esta "
            "página nunca escribe en la EEPROM.")
        self.grid = QTableWidget(0, 16)
        self.grid.setHorizontalHeaderLabels([f"{i:X}" for i in range(16)])
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.setShowGrid(True)
        self.grid.setFont(QFont("Consolas", 10))
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.grid, 1)
        return page

    def _page_history(self):
        page, lay = self._page(
            "history", "Historial",
            "Operaciones hechas con esta aplicación. Se consulta sin impresora conectada. "
            "Doble clic en un informe o una copia para abrirlo.")
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Fecha", "Operación", "Detalle", "Impresora"])
        self.history_table.verticalHeader().hide()
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.cellDoubleClicked.connect(self._history_open)
        lay.addWidget(self.history_table, 1)
        return page

    # ---- helpers ----------------------------------------------------------
    def _history_picked(self, _index):
        self._history_pinned = True
        self._render_history()

    def _history_serial(self):
        """Serial the Historial page is showing: '' means every printer."""
        return self.history_who.currentData() or ""

    def _render_history(self):
        connected = self.info.get("serial_number", "")
        chosen = self._history_serial() if self._history_pinned else None
        combo = self.history_who
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todas las impresoras", "")
        for printer in history.printers():
            here = "  · conectada" if printer["serial"] == connected else ""
            combo.addItem(f"{printer['model']} · {printer['serial']}{here}", printer["serial"])
        wanted = chosen if chosen is not None else connected
        combo.setCurrentIndex(max(combo.findData(wanted), 0))
        combo.blockSignals(False)

        serial = self._history_serial()
        events = history.load(200, serial=serial)
        table = self.history_table
        table.setColumnHidden(3, bool(serial))  # the printer column only matters for "all"
        table.setRowCount(len(events))
        for row, event in enumerate(events):
            values = (event.get("when", "")[:16].replace("T", " "), event.get("kind", ""),
                      event.get("detail", ""),
                      f"{event.get('model', '')} · {event.get('serial', '')}")
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, event)
                if self._history_file(event):
                    item.setToolTip("Doble clic para abrir")
                table.setItem(row, col, item)
        table.resizeRowsToContents()

    @staticmethod
    def _history_file(event):
        """File an event refers to (a report or a backup), or None."""
        folder = {"informe": report.REPORTS, "copia": BACKUP_DIR,
                  "diagnóstico": report.REPORTS}.get(event.get("kind"))
        name = Path(str(event.get("file") or event.get("detail", ""))).name
        return folder / name if folder and name else None

    def _history_open(self, row, _col):
        event = self.history_table.item(row, 0).data(Qt.UserRole) or {}
        path = self._history_file(event)
        if path is None:
            return
        if not path.is_file():
            self._log(f"El archivo ya no existe: {path.name}")
            return
        self._open_path(path)

    def _open_path(self, path):
        try:
            os.startfile(path)
        except OSError as exc:
            self._log(f"No se pudo abrir {Path(path).name}: {exc}")

    def _open_folder(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def export_history(self):
        events = history.load(10 ** 9, serial=self._history_serial())
        if not events:
            self._log("No hay operaciones que exportar.")
            return
        self._save_csv("Exportar historial", f"historial_{datetime.now():%Y%m%d_%H%M%S}.csv",
                       ["fecha", "operacion", "detalle", "modelo", "serie"],
                       [[e.get("when", ""), e.get("kind", ""), e.get("detail", ""),
                         e.get("model", ""), e.get("serial", "")] for e in events])

    def _save_csv(self, title, name, header, rows):
        BACKUP_DIR.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, title, str(BACKUP_DIR / name), "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerows(rows)
            self._log(f"Exportado: {path}")

    def _set_chip(self, text, color):
        self._chip_state = (text, color)
        c = QColor(color)
        rgb = f"{c.red()}, {c.green()}, {c.blue()}"
        fg = c.lighter(115) if is_dark() else c.darker(115)
        self.chip.setText(text)
        self.chip.setStyleSheet(f"background: rgba({rgb}, 36); color: {fg.name()}; "
                                f"border: 1px solid rgba({rgb}, 120);")

    def _log(self, text):
        self.log.appendPlainText(f"[{datetime.now():%H:%M:%S}] {text}")

    def _why_disabled(self, kind):
        """Why a button of this kind ('read', 'reset', 'maint', 'clean') is off right
        now, in words for the tooltip; '' when it is on."""
        if self.busy:
            return "Hay una operación en curso."
        if not self.info:
            return ("No hay ninguna impresora leída: conéctala por USB, enciéndela y "
                    "pulsa Actualizar (F5).")
        if self.brand == "hp":
            return {"reset": hp_backend.NO_RESET, "maint": HP_NO_MAINT, "clean": HP_NO_MAINT,
                    "eeprom": HP_NO_EEPROM}.get(kind, "")
        if kind == "reset":
            if not self.points:
                return "El backend no define almohadillas para este modelo."
            if not be.can_reset(self.model_name):
                return f"El backend no tiene las celdas de reseteo de {self.model_name}."
        if kind in ("maint", "clean") and len(self.usb) != 1:
            # maintenance writes to the USB device directly: exactly one may be attached
            return (f"Hay {len(self.usb)} impresoras Epson por USB: deja conectada solo la "
                    "que quieres usar." if self.usb else
                    "Windows no ve ninguna impresora Epson por USB.")
        if kind == "clean" and not self._clean_ok():
            if self.model_name not in cleaning.SUPPORTED_MODELS:
                return (f"La limpieza solo está verificada en la familia L3150, la L3250 "
                        f"y la XP-2100/2101, no en {self.model_name}.")
            return "El modelo elegido no coincide con el que declara la impresora."
        return ""

    def _nozzle_job(self):
        """Payload of the nozzle check for the model chosen now: the Epson driver's own job
        where it was captured (driver_jobs.py), the generic ESC/P2 one otherwise."""
        if self.model_name in driver_jobs.DRIVER_MODELS:
            return driver_jobs.nozzle_check_job
        return lambda: spooler.nozzle_check(0)

    def _sync_clean_modes(self):
        """Cleaning modes of the chosen model; the driver's cleaning has one mode and no
        counter restore."""
        if not hasattr(self, "clean_mode"):
            return
        modes = cleaning.modes_for(self.model_name)
        keys = [m[0] for m in modes]
        if [self.clean_mode.itemData(i) for i in range(self.clean_mode.count())] != keys:
            self.clean_mode.blockSignals(True)
            self.clean_mode.clear()
            for key, label, *_rest in modes:
                self.clean_mode.addItem(label, key)
            self.clean_mode.blockSignals(False)
        driver = self.model_name in driver_jobs.DRIVER_MODELS
        if driver:
            self.restore_check.setChecked(False)
        self.restore_check.setEnabled(not driver and not self.busy)

    def _set_busy(self, busy):
        self.busy = busy
        self._sync_clean_modes()
        for b in self.guarded:
            kind = ("reset" if b in self.reset_buttons else "clean" if b is self.btn_clean
                    else "maint" if b in self.maint_buttons else
                    "eeprom" if b is self.btn_dump else "read")
            why = self._why_disabled(kind)
            b.setEnabled(not why)
            b.setToolTip(why)
        for b in getattr(self, "diag_free", []):
            b.setEnabled(not busy)
            b.setToolTip("Hay una operación en curso." if busy else "")
        self.btn_refresh.setEnabled(not busy)
        self.btn_refresh3d.setEnabled(not busy)
        self.qa_refresh.setEnabled(not busy)
        self.model.setEnabled(not busy)
        self._sync_3d()

    def _show_wait(self, text, determinate=False):
        """Progress strip at the top of the Mantenimiento page."""
        self.wait_label.setText(text)
        self.wait_bar.setRange(0, 100 if determinate else 0)
        self.wait_bar.setValue(0)
        self.wait_bar.show()
        self.wait_frame.show()

    def _hide_wait(self):
        self.wait_bar.hide()
        self.wait_label.setText("")
        self.wait_frame.hide()

    def _notify(self):
        """A beep and a flashing taskbar button: these jobs last minutes and the user
        has usually walked away from the screen."""
        QApplication.beep()
        QApplication.alert(self, 0)

    def _set_banner(self, text):
        self.banner.setText(text)
        self.banner.setVisible(bool(text))

    def _clear_readings(self):
        """No printer: show dashes, never the numbers of the last one that was read."""
        for label in self.usage.values():
            label.setText("--")
        self.details.setRowCount(0)
        self.title.setText("Impresora Epson")
        self.setWindowTitle(APP_NAME)
        self.alerts = []
        self._render_ink()
        self._render_alerts()
        self._sync_3d()

    def _run(self, fn, callback):
        self._set_busy(True)
        task = Task(fn, callback)
        task.signals.done.connect(self._complete)  # bound QObject method: UI thread
        self.pool.start(task)

    def _complete(self, callback, result, error):
        self._set_busy(False)
        callback(result, error)

    def _manual_model(self):
        """The model the user picked by hand, or '' while the selector is on Automático."""
        return self.model.currentData() or ""

    @property
    def model_name(self):
        """The model in use: the user's choice if there is one, else the printer found."""
        return self._manual_model() or self.detected_model

    # ---- refresh ----------------------------------------------------------
    def refresh(self, *_, attempts=1):
        """Find out which Epson is plugged in and read it. The model comes first: it is the
        one Windows reports as attached right now, not the last one remembered. A model
        picked by hand wins over it. attempts > 1 retries, for a printer that is still busy.

        Detection only reads the Windows device registry (pnp.py); no backend process and
        no USB session is started until a model is known, so nothing is ever opened while
        no printer is there."""
        self._log("Buscando la impresora (Epson o HP) conectada por USB...")
        manual = self._manual_model()
        host_text = self.hp_host.text().strip()
        self.subtitle.setText("Consultando...")
        self._set_banner("")

        def work():
            db = be.models()
            for attempt in range(attempts):
                last = attempt == attempts - 1
                found = detect.detect(db, spooler.usb_printers())
                if not manual and ((found.brand == "hp" and found.status == detect.SINGLE)
                                   or (found.status == detect.NONE and host_text)):
                    return self._read_hp(found, host_text)
                model = manual or found.model
                if not model:
                    if found.status == detect.NONE and not last:
                        time.sleep(10)   # unplugged or rebooting after a job: look again
                        continue
                    return Reading(found)
                try:
                    info = be.read_info(model)
                except be.BackendError as exc:
                    if last:
                        return Reading(found, model, error=str(exc))
                    time.sleep(10)
                    continue
                # The first USB session after the printer is plugged in or the app starts
                # can drop a cell even though the status read just worked (seen on an
                # L3250 with XF26P8), so the cells get a few short retries of their own.
                cells, error = {}, None
                for _ in range(3) if be.cells_for(model) else ():
                    try:
                        cells, error = be.read_cells(model, be.cells_for(model)), None
                        break
                    except be.BackendError as exc:
                        error = exc
                        time.sleep(3)
                if error and not (info or {}).get("printer_status"):
                    return Reading(found, model, error=str(error))
                if error:
                    # A printer that stopped on an error (paper out, jam...) still answers
                    # its status but may refuse the counters: show the status and its
                    # error instead of "Sin conexión".
                    info = dict(info, cells_error=str(error))
                    cells = {}
                names = be.family(model)
                queues = [q for q in spooler.epson_queues() if any(n in q.name for n in names)]
                return Reading(found, model, info, cells, queues)

        self._run(work, self._refreshed)

    @staticmethod
    def _read_hp(found, host_text):
        """Read an HP (runs on the worker thread): the USB unit Windows sees, if any, and
        the network address typed by the user or, failing that, the one of its Windows
        TCP/IP queue. Only reads."""
        printer = found.printers[0] if found.brand == "hp" and found.printers else None
        model = found.model if printer else ""
        try:
            queues = spooler.hp_queues()
        except Exception:  # spooler unreachable: no queues to offer
            queues = []
        host = host_text or next((q.host for q in queues
                                  if q.host and hp_models.same_model(q.name, model)), "")
        spool = None
        live = next((q for q in queues if printer and q.port.upper() in printer.ports), None)
        if live:
            try:
                jobs, problem = spooler.queue_state(live.name)
                spool = {"queue": live.name, "jobs": jobs, "problem": problem}
            except Exception:
                spool = None
        try:
            info = hp_backend.read(printer, host, spooler=spool)
        except hp_backend.HpError as exc:
            return Reading(found, model, error=str(exc))
        if host and not host_text:
            info["host_from_queue"] = True
        model = model or info.get("model", "HP")
        mine = [q for q in queues if hp_models.same_model(q.name, model)]
        return Reading(found, model, info, {}, mine)

    def _refreshed(self, result, error):
        if error:
            self._read_failed(str(error))
            return
        found = result.found
        hp_read = bool(result.info) and result.info.get("brand") == "hp"
        self.detection = found
        self.detected_model = found.model or (result.model if hp_read else "")
        self.usb = [printer.instance for printer in found.printers]
        self.model.setItemText(0, f"{AUTO_LABEL} · {found.summary}")
        self._log(found.message)
        manual = self._manual_model()
        if manual and found.model and manual != found.model:
            self._log(f"Aviso: elegiste {manual} a mano, pero Windows ve conectada una {found.model}.")
        if result.error:
            self._read_failed(result.error)
            return
        if result.info is None:
            self._no_printer(found)
            return
        self.info, self.cells, self.queues = result.info, result.cells, result.queues
        self.brand = self.info.get("brand", "epson")
        cells_error = self.info.get("cells_error", "")
        self.points = ({} if self.brand == "hp" or cells_error
                       else be.pad_points(self.model_name, self.cells))
        self._render()
        self._set_busy(False)
        self._log("Datos actualizados.")
        if self.brand == "hp":
            self._log(f"{self.model_name}: leída por "
                      f"{' + '.join(self.info.get('via') or ['--'])}"
                      + (f" ({self.info['host']}" + (", IP de la cola de Windows"
                                                     if self.info.get("host_from_queue")
                                                     else "") + ")"
                         if self.info.get("host") else "") + ". Solo lectura.")
            for problem in self.info.get("network_errors") or ():
                self._log(f"Red: {problem}")
        elif cells_error:
            self._log(f"La impresora respondió su estado pero no los contadores ({cells_error}). "
                      "Si está en error (luz de papel), retira o carga el papel, pulsa su botón "
                      "y vuelve a Actualizar (F5).")
        elif not self.points:
            self._log(f"{self.model_name}: el backend no define almohadillas; solo lectura.")
        if self.points_before is not None and not cells_error:
            self._log_delta()

    def _no_printer(self, found):
        """Nothing to read: no printer, several of them, or a model the backend lacks. The
        old numbers are cleared and no model is assumed."""
        self.info, self.cells, self.points, self.queues = {}, {}, {}, []
        self.brand = ""
        self._render_gauges()
        self._clear_readings()
        self._render_history()
        self._set_chip("Sin conexión", C["bad"] if found.status == detect.NONE else C["warn"])
        self.subtitle.setText(found.summary[:1].upper() + found.summary[1:])
        self._set_banner(found.message + " Mientras tanto puedes consultar el Historial.")
        self._set_busy(False)

    def _read_failed(self, error):
        self.info, self.points = {}, {}
        self.brand = ""
        self._render_gauges()
        self._clear_readings()
        self._render_history()
        self._set_chip("Sin conexión", C["bad"])
        self.subtitle.setText("No se pudo leer la impresora")
        self._set_banner("No se pudo leer la impresora. Comprueba que está encendida y "
                         "conectada por USB y pulsa Actualizar (F5). Mientras tanto "
                         "puedes consultar el Historial.")
        self._log(f"Error: {error}")
        if "EEPROM" in error:
            self._log(f"Si la impresora está conectada, comprueba que {self.model_name} "
                      "es su modelo: cada modelo usa una clave distinta.")
        self._set_busy(False)

    def _log_delta(self):
        for name, (after, maximum) in self.points.items():
            before = self.points_before.get(name, (after,))[0]
            self._log(f"{be.PAD_LABELS[name]}: {before} -> {after} puntos "
                      f"({after - before:+d}) de {maximum}")
        self.points_before = None

    def _model_matches(self):
        """True if the printer's own description contains the selected model (or, for a
        mapped model, one of the names that share its configuration)."""
        if self.brand == "hp":
            return True   # an HP is named by Windows and by itself: nothing to pick by hand
        if not self.model_name:
            return False
        ident = self.info.get("device_identification", {})
        desc = (ident.get("Description") or [""])[0].upper()
        return any(name.upper() in desc for name in be.family(self.model_name))

    def _render(self):
        if self.brand == "hp":
            self._render_hp()
            return
        info, status = self.info, self.info.get("printer_status", {})
        ident, stats = info.get("device_identification", {}), info.get("stats", {})
        self.reset_hint.setText(RESET_HINT)
        self.title.setText((ident.get("Description") or ["Impresora Epson"])[0])
        self.subtitle.setText(f"Serie {info.get('serial_number', '--')}")
        self.setWindowTitle(f"{APP_NAME} — {self.title.text()} · "
                            f"{info.get('serial_number', '--')}")
        self.alerts = printer_state.alerts(status, self._worst_pct())
        text, kind = printer_state.chip(status, self.alerts)
        self._set_chip(text, C[kind])
        errors = [a for a in self.alerts if a.severity == printer_state.ERROR]
        if errors:
            self._set_banner(f"La impresora informa: {printer_state.alert_line(errors[0])}")
        for alert in self.alerts:
            self._log(f"Aviso de la impresora: {printer_state.alert_line(alert)}")

        self._render_gauges()
        self._render_ink()
        self._render_alerts()

        first, age = age_since(stats.get("First TI received time"))
        values = {
            "Estado": printer_state.status_text(status),
            "Páginas impresas": stats.get("Total print page counter", "--"),
            "Pasadas del cabezal": stats.get("Total print pass counter", "--"),
            "Escaneos": stats.get("Total scan counter", "--"),
            "Primera tinta instalada": first.strftime("%d/%m/%Y") if first else "--",
            "Antigüedad": age or "--",
            "Depósito mantenimiento": printer_state.box_text(status, 1),
        }
        for key, value in values.items():
            self.usage[key].setText(str(value))
        self._render_details(first, age)
        self._render_queues()
        self._render_history()
        self.clean_note.setText(
            "" if self._clean_ok() else
            f"Los modos solo están verificados en la familia L3150 y la L3250; con {self.model_name} "
            "la limpieza está desactivada.")
        self._sync_3d()

    def _render_hp(self):
        info = self.info
        status = printer_state.hp_status(info)
        serial = info.get("serial_number") or "--"
        self.title.setText(info.get("model") or "Impresora HP")
        self.subtitle.setText(f"Serie {serial} · {' + '.join(info.get('via') or [])}")
        self.setWindowTitle(f"{APP_NAME} — {self.title.text()} · {serial}")
        self.alerts = printer_state.hp_alerts(info)
        text, kind = printer_state.chip(status, self.alerts)
        self._set_chip(text, C[kind])
        errors = [a for a in self.alerts if a.severity == printer_state.ERROR]
        if errors:
            self._set_banner(f"La impresora informa: {printer_state.alert_line(errors[0])}")
        elif not info.get("host"):
            self._set_banner(HP_USB_ONLY if not info.get("network_errors") else
                             "La HP no respondió por la red: " + info["network_errors"][0]
                             + ". Revisá la IP y que esté en la misma red.")
        for alert in self.alerts:
            self._log(f"Aviso de la impresora: {printer_state.alert_line(alert)}")
        self._render_gauges()
        self._render_ink()
        self._render_alerts()
        usage = info.get("usage") or {}
        dash = lambda value: "--" if value in (None, "") else value
        values = {
            "Estado": printer_state.hp_status_text(info),
            "Páginas impresas": dash(usage.get("total")),
            "Pasadas del cabezal": "--",
            "Escaneos": dash(usage.get("scans")),
            "Primera tinta instalada": "--",
            "Antigüedad": "--",
            "Depósito mantenimiento": "sin contador legible (HP)",
        }
        for key, value in values.items():
            self.usage[key].setText(str(value))
        self._render_details(None, None)
        self._render_queues()
        self._render_history()
        self.clean_note.setText(HP_NO_MAINT)
        self.reset_hint.setText(HP_RESET_HINT)
        self._sync_3d()

    def _worst_pct(self):
        """Fullest waste pad in %, counting uncounted ink; None without counters."""
        if not self.points:
            return None
        _label, points, maximum = self._worst_pad()
        return points / maximum * 100

    def _ink_refills(self):
        """'N 3 · C 2 · M 2 · A 1' from the EEPROM refill counters, '' when the model
        has none."""
        stats = self.info.get("stats", {})
        parts = [f"{short} {stats['Ink replacement counter - ' + colour]}"
                 for colour, short in (("Black", "N"), ("Cyan", "C"), ("Magenta", "M"),
                                       ("Yellow", "A"))
                 if stats.get("Ink replacement counter - " + colour) not in (None, "")]
        return " · ".join(parts)

    def _render_ink(self):
        while self.ink_row.count():
            widget = self.ink_row.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        status = self.info.get("printer_status", {})
        hp = self.brand == "hp"
        inks = printer_state.hp_inks(self.info) if hp else printer_state.inks(status)
        for ink in inks:
            self.ink_row.addWidget(InkMeter(ink.name, ink.swatch, ink.level, ink.state))
        self.ink_row.addStretch()
        measured = printer_state.ink_measured(status)
        if hp:
            self.ink_note.setText(self._hp_ink_note(inks))
            return
        if not self.info:
            note = "Sin lectura."
        elif measured is None:
            note = "La impresora no informó la tinta."
        elif measured:
            note = ("Nivel estimado por la impresora (chip del cartucho o contador de "
                    "consumo), no medido dentro del cartucho.")
        else:
            note = ("La impresora no mide el nivel de los tanques: informa los colores sin "
                    "nivel. Mirá el visor de cada tanque.")
        refills = self._ink_refills()
        if self.info and refills:
            note += f" Recargas registradas: {refills}."
        self.ink_note.setText(note)

    def _hp_ink_note(self, inks):
        if not inks:
            return ("Por USB no se lee la tinta de una HP: escribí su IP en «HP por red» y "
                    "pulsá Actualizar." if not self.info.get("host") else
                    "La impresora no informó la tinta.")
        if any(ink.level is not None for ink in inks):
            note = "Nivel estimado por la impresora, no medido dentro del tanque."
        else:
            note = ("La Smart Tank no da un porcentaje: tiene sensores que avisan cuando un "
                    "tanque está bajo. Mirá el visor de cada tanque.")
        heads = self._hp_heads()
        return note + (f" Cabezales: {heads}." if heads else "")

    def _hp_heads(self):
        """'negro bien · tricolor bien' from the printheads the HP reports."""
        words = {"ok": "bien", "missing": "falta", "low": "por cambiar", "out": "agotado"}
        parts = []
        for head in self.info.get("printheads") or ():
            colour = hp_backend.colour_word(head.get("key")) or hp_backend.colour_word(
                head.get("label"))
            name = printer_state.HP_INKS.get(colour, (head.get("key") or "cabezal",))[0]
            state = str(head.get("state", "")).lower()
            parts.append(f"{name.lower()} {words.get(state, state or 'sin estado')}")
        return " · ".join(parts)

    def _render_alerts(self):
        if not self.info:
            self.alerts_label.setText("Sin lectura.")
            return
        if not self.alerts:
            self.alerts_label.setText(
                f"<span style='color:{C['ok']}'>Sin avisos:</span> la impresora no informa "
                "errores ni advertencias.")
            return
        colour = {printer_state.ERROR: C["bad"], printer_state.WARNING: C["warn"],
                  printer_state.INFO: C["muted"]}
        rows = []
        for alert in self.alerts:
            line = (f"<b style='color:{colour[alert.severity]}'>{escape(alert.title)}</b>")
            if alert.action:
                line += f" — {escape(alert.action)}"
            if alert.light:
                line += (f"<br><span style='color:{C['muted']}'>En la impresora: "
                         f"{escape(alert.light.lower())} (habitual; depende del modelo)."
                         "</span>")
            rows.append(line)
        self.alerts_label.setText("<br>".join(rows))

    def _render_gauges(self):
        while self.gauge_row.count():
            widget = self.gauge_row.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self.gauges = {}
        worst = 0.0
        hidden = self._hidden()
        for name, (points, maximum) in self.points.items():
            gauge = Gauge(be.PAD_LABELS[name])
            real = points + (hidden if name == "main_waste" else 0)
            pct = real / maximum * 100
            worst = max(worst, pct)
            detail = f"{points} / {maximum} puntos"
            if name == "main_waste" and hidden:
                detail = f"contador {points} · real ≈ {real} / {maximum}"
            gauge.set_value(pct, detail)
            self.gauge_row.addWidget(gauge)
            self.gauges[name] = gauge
        if not self.info:
            self.waste_note.setText("Sin lectura: conecta la impresora y pulsa Actualizar.")
        elif self.brand == "hp":
            self.waste_note.setText(HP_PADS)
        elif not self.points:
            self.waste_note.setText("Este modelo no tiene contadores de almohadillas "
                                    "definidos en el backend.")
        else:
            level = ("Nivel crítico: la impresora puede bloquearse. Revisa o cambia las almohadillas."
                     if worst >= 90 else
                     "Nivel alto: planifica el mantenimiento de las almohadillas."
                     if worst >= 70 else "Nivel normal.")
            if hidden:
                level += (f"  Hay {hidden} puntos de tinta que el contador no cuenta "
                          "(limpiezas con el contador restaurado); el porcentaje mostrado "
                          "ya los incluye.")
            self.waste_note.setText(level)
        if self.info and not self._model_matches():
            self.waste_note.setText(
                self.waste_note.text() + f"  Aviso: el modelo elegido ({self.model_name}) "
                "no coincide con el que declara la impresora; el reseteo permanente "
                "queda bloqueado.")
        if self.info and self._mapped_note():
            self.waste_note.setText(self.waste_note.text() + "  " + self._mapped_note())

    def _mapped_note(self):
        """Warning for a model the backend does not list by name ('' for the others)."""
        model = self.model_name
        if not model or not be.is_mapped(model):
            return ""
        return (f"{model} no figura por nombre en el backend: se usa la configuración de "
                f"{be.backend_model(model)}, que otra base de datos publicada (reinkpy) "
                "agrupa con ella. No está verificado en una impresora real: simula el "
                "reseteo y revisa la copia antes de resetear.")

    def _hidden(self):
        """Ink points poured but not counted for the connected printer (see history.py)."""
        serial = self.info.get("serial_number", "")
        return history.hidden_points(serial) if serial else 0

    def _worst_pad(self):
        """(label, points, maximum) of the fullest pad, counting uncounted ink."""
        hidden = self._hidden()

        def real(name):
            return self.points[name][0] + (hidden if name == "main_waste" else 0)

        name = max(self.points, key=lambda n: real(n) / self.points[n][1])
        return be.PAD_LABELS[name], real(name), self.points[name][1]

    def _detail_rows(self, first, age):
        info, status = self.info, self.info.get("printer_status", {})
        ident, stats = info.get("device_identification", {}), info.get("stats", {})
        first_of = lambda key: (ident.get(key) or ["--"])[0]
        p = self.points
        return [
            ("Identificación", [
                ("Modelo", first_of("Description")),
                ("Número de serie", info.get("serial_number", "--")),
                ("Firmware", info.get("firmware_version", "--")),
                ("Fabricante", first_of("FG")),
                ("Comandos admitidos", first_of("Commands")),
                ("Identificadores", f"CID {first_of('CID')} · DDS {first_of('DDS')} · "
                                    f"ELG {first_of('ELG')} · RID {first_of('RID')}"),
            ]),
            ("Estado", [
                ("Estado", f"{printer_state.status_text(status)}"
                           + (f" ({status['status'][1]})" if status.get("status") else "")),
                ("Lista para imprimir", "Sí" if status.get("ready") else "No"),
                ("Código de cancelación", status.get("cancel_code", "--")),
                ("Trabajo actual", status.get("jobname", "--")),
                ("Ruta de carga", status.get("loading_path", "--")),
                ("Apagado automático", poweroff_text(
                    info.get("snmp_info", {}).get("Power Off Timer"))),
            ]),
            ("Tinta y avisos", [
                *[(f"Tinta {ink.name.lower()}",
                   "no medido (tanque)" if ink.level is None else f"{ink.level} %")
                  for ink in printer_state.inks(status)],
                *[({printer_state.ERROR: "Error", printer_state.WARNING: "Aviso",
                    printer_state.INFO: "Información"}[a.severity],
                   printer_state.alert_line(a) + (f" [{a.code}]" if a.code else ""))
                  for a in self.alerts],
                ("Código de error", status.get("errcode", "ninguno")),
                ("Advertencias", ", ".join(map(str, status.get("warning_code") or ()))
                 or "ninguna"),
            ]),
            ("Uso", [
                ("Páginas impresas", stats.get("Total print page counter", "--")),
                ("Pasadas del cabezal", stats.get("Total print pass counter", "--")),
                ("Escaneos", stats.get("Total scan counter", "--")),
                ("Primera tinta instalada", f"{first:%d/%m/%Y} ({age})" if first else "--"),
                ("Cambios de tinta", " · ".join(
                    f"{c[0]} {stats.get('Ink replacement counter - ' + c, '--')}"
                    for c in ("Black", "Cyan", "Magenta", "Yellow"))),
            ]),
            ("Mantenimiento", [
                *[(be.PAD_LABELS[name], f"{pts} / {maximum} puntos ({pts / maximum * 100:.2f}%)")
                  for name, (pts, maximum) in p.items()],
                *([("Tinta sin contar", f"{self._hidden()} puntos (limpiezas con el "
                                        "contador restaurado)")] if self._hidden() else []),
                ("Nivel de aviso (contador 1 / 2)",
                 f"{stats.get('Maintenance required level of 1st waste ink counter', '--')} / "
                 f"{stats.get('Maintenance required level of 2nd waste ink counter', '--')}"),
                ("Depósito 1 / 2", f"{status.get('maintenance_box_1', '--')} / "
                                   f"{status.get('maintenance_box_2', '--')}"),
                ("Reseteos del depósito (1 / 2)",
                 f"{status.get('maintenance_box_reset_count_1', '--')} / "
                 f"{status.get('maintenance_box_reset_count_2', '--')}"),
            ]),
            ("Conexión", [
                ("Impresoras Epson por USB", len(self.usb)),
                ("Windows las llama", ", ".join(
                    p.name for p in (self.detection.printers if self.detection else ())) or "--"),
                ("Modelo usado", f"{self.model_name} ("
                                 + ("elegido a mano" if self._manual_model() else "automático") + ")"),
                ("Colas de Windows activas", ", ".join(
                    f"{q.name} ({q.port})" for q in self.queues if q.active) or "ninguna"),
            ]),
        ]

    def _detail_rows_hp(self):
        info = self.info
        usage, state = info.get("usage") or {}, info.get("state") or {}
        device = info.get("device_id") or {}
        dash = lambda value: "--" if value in (None, "") else value
        ready = info.get("ready")
        spool = state.get("spooler")
        inks = printer_state.hp_inks(info)
        return [
            ("Identificación", [
                ("Marca", "HP"),
                ("Modelo", dash(info.get("model"))),
                ("Número de serie", dash(info.get("serial_number"))),
                ("Número de producto", dash(info.get("product_number") or device.get("DES"))),
                ("Firmware", dash(info.get("firmware_version"))),
                ("Comandos admitidos", dash(device.get("CMD"))),
                ("Identificadores", f"CID {dash(device.get('CID'))} · "
                                    f"LEDM {dash(device.get('LEDMDIS'))}"),
            ]),
            ("Estado", [
                ("Estado", printer_state.hp_status_text(info)),
                ("Lista para imprimir", "--" if ready is None else "Sí" if ready else "No"),
                ("Estado LEDM", dash(state.get("category"))),
                ("Estado IPP", dash(state.get("ipp")) + (
                    f" ({', '.join(state['reasons'])})" if state.get("reasons") else "")),
                ("Mensaje de la impresora", dash(state.get("message"))),
                ("Cola de Windows", f"{spool['queue']}: {spool['problem'] or 'sin problemas'}"
                 if spool else "--"),
            ]),
            ("Tinta y avisos", [
                *[(f"Tinta {ink.name.lower()}",
                   f"{ink.level} %" if ink.level is not None else ink.state or "no informado")
                  for ink in inks],
                *([("Cabezales", self._hp_heads())] if self._hp_heads() else []),
                *[({printer_state.ERROR: "Error", printer_state.WARNING: "Aviso",
                    printer_state.INFO: "Información"}[a.severity],
                   printer_state.alert_line(a) + (f" [{a.code}]" if a.code else ""))
                  for a in self.alerts],
            ]),
            ("Uso", [
                ("Páginas impresas", dash(usage.get("total"))),
                ("Páginas en negro", dash(usage.get("mono"))),
                ("Páginas en color", dash(usage.get("color"))),
                ("Escaneos", dash(usage.get("scans"))),
                ("Copias", dash(usage.get("copies"))),
                ("Atascos de papel", dash(usage.get("jams"))),
                ("Fallas al tomar la hoja", dash(usage.get("mispicks"))),
            ]),
            ("Mantenimiento", [
                ("Almohadillas (absorbente)", "HP no publica un contador legible"),
                ("Reseteo de contadores", "Deshabilitado para HP"),
            ]),
            ("Conexión", [
                ("Leída por", " + ".join(info.get("via") or []) or "--"),
                ("Dirección de red", (info.get("host") or "ninguna") + (
                    " (de la cola de Windows)" if info.get("host_from_queue") else "")),
                *[("Error de red", problem) for problem in info.get("network_errors") or ()],
                ("Impresoras por USB", len(self.usb)),
                ("Windows las llama", ", ".join(
                    p.name for p in (self.detection.printers if self.detection else ())) or "--"),
                ("PID USB", dash((info.get("usb") or {}).get("usb_pid"))),
                ("Colas de Windows", ", ".join(
                    f"{q.name} ({q.port})" for q in self.queues if q.active) or "ninguna"),
            ]),
        ]

    def _render_details(self, first, age):
        self._details_args = (first, age)
        sections = (self._detail_rows_hp() if self.brand == "hp"
                    else self._detail_rows(first, age))
        self.details.setRowCount(0)
        for section, rows in sections:
            r = self.details.rowCount()
            self.details.insertRow(r)
            item = QTableWidgetItem(section.upper())
            item.setForeground(QBrush(QColor(C["blue"])))
            item.setBackground(QBrush(QColor(C["section"])))
            font = QFont("Segoe UI", 9)
            font.setBold(True)
            item.setFont(font)
            self.details.setItem(r, 0, item)
            self.details.setSpan(r, 0, 1, 2)
            for label, value in rows:
                r = self.details.rowCount()
                self.details.insertRow(r)
                key = QTableWidgetItem(label)
                key.setForeground(QBrush(QColor(C["muted"])))
                self.details.setItem(r, 0, key)
                self.details.setItem(r, 1, QTableWidgetItem(str(value)))
        self.details.resizeRowsToContents()

    def _render_queues(self):
        self.print_queue.clear()
        for q in self.queues:
            self.print_queue.addItem(
                f"{q.name}  ({q.port})" + ("  · conectada" if q.active else ""), q)
        serial = self.info.get("serial_number", "--")
        if self.brand == "hp":
            self.queue_note.setText(
                f"HP (serie {serial}): la página de prueba MAG va por la cola de Windows "
                "elegida, con el driver de HP. " + HP_NO_MAINT)
        elif len(self.usb) == 1:
            self.queue_note.setText(
                f"Se envía directamente a la impresora conectada por USB (serie {serial}), "
                "sin pasar por la cola de Windows: el driver V4 de Epson rechaza estos "
                "datos. Mientras trabaja, la aplicación no la consulta.")
        else:
            self.queue_note.setText(
                f"Hay {len(self.usb)} impresoras Epson conectadas por USB. Deja conectada "
                "solo la que quieres usar: el mantenimiento queda desactivado para que "
                "los datos no lleguen a otra unidad.")

    # ---- details actions --------------------------------------------------
    def copy_details(self):
        lines = []
        for r in range(self.details.rowCount()):
            a, b = self.details.item(r, 0), self.details.item(r, 1)
            lines.append(a.text() if b is None else f"{a.text()}: {b.text()}")
        QApplication.clipboard().setText("\n".join(lines))
        self._log("Detalles copiados al portapapeles.")

    def _report_data_hp(self):
        info = self.info
        usage = info.get("usage") or {}
        serial = info.get("serial_number", "")
        dash = lambda value: "--" if value in (None, "") else value
        return {
            "model": info.get("model") or self.model_name,
            "serial": serial or "--",
            "firmware": dash(info.get("firmware_version")),
            "status": printer_state.hp_status_text(info),
            "via": " + ".join(info.get("via") or []),
            "inks": [(ink.name, ink.level, ink.state) for ink in printer_state.hp_inks(info)],
            "refills": "",
            "alerts": [(a.severity, printer_state.alert_line(a)) for a in self.alerts],
            "when": datetime.now(),
            "pads": [], "pads_note": HP_PADS, "hidden": 0,
            "usage": [("Páginas impresas", dash(usage.get("total"))),
                      ("Páginas en negro", dash(usage.get("mono"))),
                      ("Páginas en color", dash(usage.get("color"))),
                      ("Escaneos", dash(usage.get("scans"))),
                      ("Copias", dash(usage.get("copies")))],
            "events": history.load(12, serial=serial),
        }

    def _report_data(self):
        if self.brand == "hp":
            return self._report_data_hp()
        info, status = self.info, self.info.get("printer_status", {})
        ident, stats = info.get("device_identification", {}), info.get("stats", {})
        first, age = age_since(stats.get("First TI received time"))
        serial = info.get("serial_number", "")
        return {
            "model": (ident.get("Description") or [self.model_name])[0],
            "serial": serial or "--",
            "firmware": info.get("firmware_version", "--"),
            "status": printer_state.status_text(status),
            "inks": [(ink.name, ink.level) for ink in printer_state.inks(status)],
            "refills": self._ink_refills(),
            "alerts": [(a.severity, printer_state.alert_line(a)) for a in self.alerts],
            "when": datetime.now(),
            "pads": [(be.PAD_LABELS[n], p, m) for n, (p, m) in self.points.items()],
            "hidden": self._hidden(),
            "usage": [("Páginas impresas", stats.get("Total print page counter", "--")),
                      ("Pasadas del cabezal", stats.get("Total print pass counter", "--")),
                      ("Escaneos", stats.get("Total scan counter", "--")),
                      ("Primera tinta instalada",
                       f"{first:%d/%m/%Y} ({age})" if first else "--")],
            "events": history.load(12, serial=serial),
        }

    def copy_summary(self):
        """The key figures as plain text, ready to paste into a chat with the customer."""
        data = self._report_data()
        if not data["pads"] and not data.get("pads_note"):
            self._log("Este modelo no tiene almohadillas definidas: no hay resumen.")
            return
        QApplication.clipboard().setText(report.summary_text(data))
        self._log("Resumen copiado al portapapeles.")

    def make_report(self):
        data = self._report_data()
        serial = data["serial"] if data["serial"] != "--" else ""
        if not data["pads"] and not data.get("pads_note"):
            self._log("Este modelo no tiene almohadillas definidas: no hay informe.")
            return
        try:
            path = report.build(data)
        except Exception as exc:  # a broken report must not take the app down
            self._log(f"No se pudo crear el informe: {exc}")
            return
        history.record("informe", self.model_name, serial, detail=path.name)
        self._render_history()
        self._log(f"Informe guardado: reports/{path.name}")
        try:
            os.startfile(path)
        except OSError:
            pass

    def export_json(self):
        BACKUP_DIR.mkdir(exist_ok=True)
        path = BACKUP_DIR / f"info_{self.info.get('serial_number', 'x')}_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(self.info, indent=2, default=repr), encoding="utf-8")
        self._log(f"Exportado: {path.name}")

    # ---- counters ---------------------------------------------------------
    def _save_backup(self):
        cells = be.read_cells(self.model_name, be.cells_for(self.model_name))
        BACKUP_DIR.mkdir(exist_ok=True)
        serial = self.info.get("serial_number", "desconocida")
        path = BACKUP_DIR / f"{self.model_name}_{serial}_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps({
            "model": self.model_name, "serial": serial,
            "date": datetime.now().isoformat(timespec="seconds"),
            "eeprom": {str(k): v for k, v in sorted(cells.items())},
        }, indent=2), encoding="utf-8")
        return path

    # ---- Vista 3D --------------------------------------------------------------
    def _sync_3d(self):
        """Hand the 3D view what the other pages show (it reads nothing by itself)."""
        if not hasattr(self, "bridge3d") or not hasattr(self, "usage"):
            return
        data = printer3d.empty_data(dark=is_dark())
        why = self._why_disabled("reset")
        brand = self.brand or (self.detection.brand if self.detection else "") or "epson"
        data.update(busy=self.busy, canRead=not self.busy, canReset=not why, why=why,
                    brand=brand, style=hp_models.style_for(brand, self.model_name))
        data.update(self._activity_3d())
        data.update(actions=self._actions_3d(),
                    cleanLabel=self.clean_mode.currentText() if hasattr(self, "clean_mode") else "",
                    pageName=testpage.VERSIONS[self._page_version_key()][0])
        if self.info and self.brand == "hp":
            info, inks = self.info, printer_state.hp_inks(self.info)
            data.update(
                connected=True, title=info.get("model") or "Impresora HP",
                model=self.model_name or "", serial=info.get("serial_number") or "--",
                status=printer_state.hp_status_text(info),
                inkMeasured=any(ink.level is not None for ink in inks),
                pads=[], worst=-1.0, note=HP_PADS,
                stats=[[key, self.usage[key].text()] for key in ("Páginas impresas", "Escaneos")
                       if self.usage[key].text() not in ("", "--")])
            if inks:
                data["inks"] = [{"name": ink.name, "color": ink.swatch, "state": ink.state,
                                 "level": -1 if ink.level is None else ink.level}
                                for ink in inks]
        elif self.info:
            info, status = self.info, self.info.get("printer_status", {})
            ident = info.get("device_identification", {})
            inks = printer_state.inks(status)
            hidden = self._hidden()
            pads = []
            for name, (points, maximum) in self.points.items():
                real = points + (hidden if name == "main_waste" else 0)
                pads.append({"label": be.PAD_LABELS[name], "pct": real / maximum * 100,
                             "detail": f"{real} / {maximum} puntos"})
            worst = self._worst_pct()
            data.update(
                connected=True,
                title=(ident.get("Description") or ["Impresora Epson"])[0],
                model=self.model_name or "", serial=info.get("serial_number", "--"),
                status=printer_state.status_text(status),
                inkMeasured=bool(printer_state.ink_measured(status)),
                pads=pads, worst=-1.0 if worst is None else worst,
                stats=[[key, self.usage[key].text()] for key in
                       ("Páginas impresas", "Escaneos", "Antigüedad", "Depósito mantenimiento")
                       if self.usage[key].text() not in ("", "--")])
            if inks:
                data["inks"] = [{"name": ink.name, "color": ink.swatch, "state": ink.state,
                                 "level": -1 if ink.level is None else ink.level}
                                for ink in inks]
        self.bridge3d.set_data(data)

    def _activity_3d(self):
        """activity, activityText and progress for the 3D view: what we sent, else what
        the printer said it was doing at the last reading."""
        kind, text = self.activity
        progress = -1.0
        if kind == "cleaning":
            state = self._clean_state
            progress = clean_progress(state["elapsed"], state["typical"]) / 100
            text = f"{state['text']} · {remaining_text(state['elapsed'], state['typical'])}"
        elif not kind and self.info and not self.busy:
            if self.brand == "hp":
                state = self.info.get("state") or {}
                if "processing" in (state.get("category"), state.get("ipp")):
                    kind, text = "printing", "La impresora informa que está imprimiendo"
            else:
                code = (self.info.get("printer_status", {}).get("status") or (None, ""))[0]
                if code == 0x07:
                    kind, text = "cleaning", "La impresora informa que está limpiando"
                elif code == 0x01:
                    kind, text = "printing", "La impresora informa que está imprimiendo"
        return {"activity": kind, "activityText": text, "progress": progress}

    def _action_buttons(self):
        return {"nozzle": self.btn_nozzle, "nozzle2": self.btn_nozzle2, "color": self.btn_color,
                "page": self.btn_testpage, "clean": self.btn_clean, "feed": self.btn_feed}

    def _actions_3d(self):
        """Why each 3D action is off ('' = on): the tooltip of its ribbon button."""
        if not hasattr(self, "btn_clean"):
            return printer3d.empty_data()["actions"]
        out = {}
        for name, button in self._action_buttons().items():
            out[name] = "" if button.isEnabled() else (button.toolTip() or "No disponible ahora.")
        return out

    def _action_from_3d(self, name):
        # the ribbon button itself: same gate, same dialogs
        button = self._action_buttons().get(name)
        if button is not None and button.isEnabled():
            button.click()

    def _set_activity(self, kind="", text=""):
        self.activity = (kind, text)
        self._sync_3d()

    def _reset_from_3d(self, mode):
        # same gate as the ribbon buttons: the 3D view may be a frame behind
        if not self._why_disabled("reset"):
            self.reset(mode)

    def _backup_from_3d(self):
        if not self._why_disabled("reset"):
            self.backup()

    def _refuse_hp(self, what):
        """True (and a line in the log) when an Epson-only action is asked of an HP."""
        if self.brand != "hp":
            return False
        self._log(f"{what}: no disponible para HP. {self._why_disabled('reset')}")
        return True

    def backup(self):
        if self._refuse_hp("Copia de contadores"):
            return
        self._log("Guardando copia de los contadores...")
        self._run(self._save_backup, self._backup_done)

    def _backup_done(self, path, error):
        if error:
            self._log(f"Error: {error}")
            return
        self._log(f"Copia guardada: {path.name}")
        history.record("copia", self.model_name, self.info.get("serial_number", ""),
                       detail=path.name)
        self._render_history()

    def reset(self, mode):
        if self._refuse_hp("Reseteo"):
            return
        model = self.model_name
        if mode == "temp":
            if QMessageBox.question(
                    self, "Reseteo temporal",
                    "Quita el aviso hasta que reinicies la impresora. No modifica "
                    "la EEPROM. ¿Continuar?") != QMessageBox.Yes:
                return
        if mode == "perm":
            if not self._model_matches():
                desc = (self.info.get("device_identification", {}).get("Description") or ["?"])[0]
                QMessageBox.warning(
                    self, "Modelo distinto",
                    f"El modelo elegido ({model}) no coincide con la impresora conectada "
                    f"({desc}). Escribir las celdas de otro modelo puede corromper la "
                    "EEPROM. Elige el modelo correcto en el selector.")
                return
            label, pts, maximum = self._worst_pad()
            dialog = ConfirmDialog(
                self, "Reseteo permanente",
                f"Se reescribirán en la EEPROM los contadores de {model} "
                f"({label.lower()}: {pts} / {maximum} puntos).\n\n"
                "Primero se guarda una copia en la carpeta backups. El reseteo solo "
                "quita el bloqueo: si las almohadillas están saturadas, la tinta puede "
                "derramarse. No apagues la impresora ni desconectes el cable."
                + (f"\n\n{self._mapped_note()}" if self._mapped_note() else ""),
                "Entiendo que esto no sustituye las almohadillas", "Resetear")
            if dialog.exec() != QDialog.Accepted:
                return
        self._log({"dry": "Simulación del reseteo (no escribe)...",
                   "temp": "Reseteo temporal...",
                   "perm": "Guardando copia y escribiendo el reseteo permanente..."}[mode])

        def work():
            path = self._save_backup() if mode == "perm" else None
            ok, message = be.reset(model, mode)
            return path, ok, message

        self._run(work, lambda result, err: self._reset_done(mode, result, err))

    def _reset_done(self, mode, result, error):
        if error:
            self._log(f"Error: {error}")
            return
        path, ok, message = result
        if path:
            self._log(f"Copia guardada: {path.name}")
        self._log(message)
        serial = self.info.get("serial_number", "")
        if mode != "dry":
            history.record({"temp": "reseteo temporal", "perm": "reseteo permanente"}[mode],
                           self.model_name, serial,
                           detail=("hecho" if ok else "no confirmado") + (
                               f"; copia {path.name}" if path else ""))
            if ok and mode == "perm":
                history.clear_hidden(serial)  # counter and tally start over together
            self._render_history()
        if mode != "dry":
            if ok:
                QMessageBox.information(
                    self, "Reseteo completado",
                    "Apaga y vuelve a encender la impresora y pulsa Actualizar "
                    "para comprobar los contadores.")
            else:
                QMessageBox.warning(self, "No se completó",
                                    "El backend no confirmó el reseteo. Revisa el registro.")
            self.refresh()

    # ---- maintenance ------------------------------------------------------
    def _clean_ok(self):
        """Cleaning modes are only known for the L3150 family and the L3250 (see
        cleaning.py), and only when the selected model is the one the printer declares."""
        return self.model_name in cleaning.SUPPORTED_MODELS and self._model_matches()

    def clean_heads(self):
        if self._refuse_hp("Limpieza de cabezales"):
            return
        key = self.clean_mode.currentData()
        _key, label, _byte, typical, _patience = cleaning.MODE_BY_KEY[key]
        restore = self.restore_check.isChecked()
        if len(self.usb) != 1 or not self._clean_ok():
            QMessageBox.warning(self, label, "La limpieza necesita exactamente una impresora "
                                "Epson por USB y el modelo correcto elegido.")
            return
        pad_name, pts, maximum = self._worst_pad()
        pct = pts / maximum * 100
        text = (f"Se enviará «{label}» a la impresora por USB. Dura unos {typical // 60} min "
                f"{typical % 60:02d} s y no se puede cancelar.\n\n"
                f"{pad_name} (con la tinta sin contar): {pts} / {maximum} puntos ({pct:.1f}%).")
        risky = pct >= 85 or key == "power"
        if key == "power":
            text += ("\n\nEl Power ink flushing vierte MUCHA más tinta a las almohadillas: "
                     "el depósito de residuos puede rebosar.")
        if pct >= 85:
            text += "\n\nLa almohadilla ya está muy llena: revisa o sustituye antes de seguir."
        if restore:
            text += ("\n\nEl contador se devolverá a su valor anterior: la tinta NO se contará "
                     "y el nivel mostrado quedará por debajo del real.")
            risky = True
        if risky:
            dialog = ConfirmDialog(self, "Confirmar limpieza", text,
                                   "Entiendo que la tinta va a la almohadilla aunque el "
                                   "contador no la cuente", "Limpiar")
            if dialog.exec() != QDialog.Accepted:
                return
        else:
            box = QMessageBox(QMessageBox.Question, "Confirmar limpieza", text,
                              QMessageBox.Yes | QMessageBox.Cancel, self)
            box.button(QMessageBox.Yes).setText("Limpiar")
            box.button(QMessageBox.Cancel).setText("Cancelar")
            box.setDefaultButton(QMessageBox.Cancel)
            if box.exec() != QMessageBox.Yes:
                return
        model = self.model_name
        serial = self.info.get("serial_number", "")
        self._clean_state = {"text": f"{label}: preparando", "elapsed": 0.0, "typical": typical}
        self.activity = ("cleaning", label)
        self._log(f"Iniciando «{label}»" + (" con restauración del contador" if restore else "")
                  + ". No se toca la impresora mientras limpia.")
        self._show_wait("", determinate=True)
        self._tick_clean()
        self._clean_timer.start(1000)

        def progress(text, elapsed):  # runs on the worker thread: only stores a value
            self._clean_state = {"text": text, "elapsed": elapsed, "typical": typical}

        self._run(lambda: cleaning.run(model, key, restore, on_progress=progress),
                  lambda result, err: self._cleaning_done(label, serial, restore, result, err))

    def _tick_clean(self):
        state = self._clean_state
        self._sync_3d()
        self.wait_bar.setValue(clean_progress(state["elapsed"], state["typical"]))
        self.wait_label.setText(
            f"{state['text']} · {state['elapsed']:.0f} s, "
            f"{remaining_text(state['elapsed'], state['typical'])} "
            "(no se puede cancelar ni conviene tocar la impresora)")

    def _cleaning_done(self, label, serial, restore, result, error):
        self._clean_timer.stop()
        self._set_activity()
        self._hide_wait()
        self._notify()
        model = self.model_name
        if error:
            self._log(f"Limpieza fallida: {error}")
            history.record("limpieza fallida", model, serial, detail=f"{label}: {error}")
            QMessageBox.warning(self, "La limpieza no terminó bien", error)
            self._render_history()
            self.refresh(attempts=3)
            return
        for line in result.log:
            self._log(line)
        detail = (f"{label}: {result.before['main_waste'][0]} -> {result.after['main_waste'][0]} "
                  f"puntos ({result.delta_main:+d}), {result.seconds:.0f} s")
        total_hidden = history.hidden_points(serial)
        if result.restored:
            total_hidden = history.add_hidden(serial, result.hidden_points)
            detail += f"; contador restaurado, {result.hidden_points} puntos sin contar"
        history.record("limpieza", model, serial, detail=detail)
        summary = (f"{label} terminada en {result.seconds:.0f} s.\n\n"
                   f"Contador principal: {result.before['main_waste'][0]} → "
                   f"{result.after['main_waste'][0]} puntos ({result.delta_main:+d}).")
        if result.restored:
            summary += (f"\nSe restauró a {result.before['main_waste'][0]}. Tinta sin contar en "
                        f"total: {total_hidden} puntos.")
        QMessageBox.information(self, "Limpieza terminada", summary)
        self._render_history()
        self.refresh(attempts=3)

    def maintenance(self, title, payload, kind, consumes):
        if self._refuse_hp(title):
            return
        if len(self.usb) != 1:
            QMessageBox.warning(self, title, "Debe haber exactamente una impresora Epson "
                                "conectada por USB.")
            return
        text = f"Se enviará «{title}» directamente a la impresora conectada por USB."
        if consumes and self.points:
            label, pts, maximum = self._worst_pad()
            pct = pts / maximum * 100
            text += (f"\n\n{label} ahora: {pts} / {maximum} puntos ({pct:.1f}%). "
                     "La limpieza añade tinta a las almohadillas.")
            if pct >= 90 or (kind == "power" and pct >= 80):
                text += ("\n\nEl contador ya está alto: esta limpieza podría dejarlo "
                         "en el límite y bloquear la impresora.")
        elif consumes:
            text += "\n\nLa limpieza añade tinta a las almohadillas."
        elif kind == "feed":
            text += ("\n\nLos rodillos giran una vez: sacan la hoja que quedó a medio salir o, "
                     "si no hay ninguna adentro, pasan una hoja en blanco de la bandeja. No "
                     "usa tinta.\n\nSi hay papel arrugado o trabado, NO lo uses: retíralo a "
                     "mano, porque los rodillos podrían romperlo y dejar pedazos adentro."
                     "\n\nDeja al menos una hoja en la bandeja trasera: sin papel, la "
                     "impresora se detiene con la luz de papel encendida hasta que cargues "
                     "papel y pulses su botón.")
        else:
            text += "\n\nLa impresora imprimirá una hoja: comprueba que tiene papel."
        box = QMessageBox(QMessageBox.Question, title, text,
                          QMessageBox.Yes | QMessageBox.Cancel, self)
        box.button(QMessageBox.Yes).setText("Enviar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setDefaultButton(QMessageBox.Cancel)
        if box.exec() != QMessageBox.Yes:
            return
        self._log(f"Enviando «{title}» por USB...")
        model = self.model_name
        self.activity = ("feeding" if kind == "feed" else "printing", title)

        def work():
            # Fresh check right before writing: only an idle, ready printer gets a job.
            status = be.read_info(model).get("printer_status", {})
            if not status.get("ready"):
                raise RuntimeError("La impresora no está lista: "
                                   f"{status.get('status', ('', 'sin estado'))[1]}")
            return spooler.send_direct(payload())

        self._run(work, lambda sent, err: self._maintenance_sent(title, kind, sent, err))

    def _maintenance_sent(self, title, kind, sent, error):
        if error:
            self._log(f"Error al enviar: {error}")
            self._set_activity()
            return
        self._log(f"{sent} bytes enviados. No se consulta la impresora hasta que termine.")
        history.record("prueba", self.model_name, self.info.get("serial_number", ""), detail=title)
        self._render_history()
        self.points_before = dict(self.points)
        self._show_wait(f"«{title}» en curso. Se releerán los contadores al terminar.")
        self._set_busy(True)
        QTimer.singleShot(WAIT_MS[kind], self._maintenance_finished)

    def _page_version_key(self):
        combo = getattr(self, "page_version", None)  # the ribbon may not be built yet
        return (combo.currentData() if combo else None) or testpage.DEFAULT

    def _page_version_changed(self, *_):
        prefs.save(testpage_version=self._page_version_key())
        self._show_page_version()
        self._sync_3d()

    def _show_page_version(self):
        """Preview and note of the chosen version on the maintenance page."""
        if not hasattr(self, "preview"):  # the maintenance page is not built yet
            return
        key = self._page_version_key()
        name, _path, ink = testpage.VERSIONS[key]
        try:
            self.preview.setPixmap(QPixmap.fromImage(
                testpage.render_page(150, testpage.version_path(key))))
        except RuntimeError:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("sin vista previa")
        self.version_note.setText(f"Versión elegida: {name} ({ink}).")

    def _queue_ready(self, title):
        """The chosen Windows queue when a job can go to it now; None after saying why."""
        queue = self.print_queue.currentData()
        if queue is None or not queue.active:
            QMessageBox.warning(self, title,
                                "Elige la cola marcada como «conectada»: las demás son de "
                                "impresoras que ya no están enchufadas.")
            return None
        status = self.info.get("printer_status", {})
        if not status.get("ready"):
            # Like the direct USB path: only a ready printer gets a job. Otherwise the job
            # sits in the Windows queue and this window waits for it.
            QMessageBox.warning(
                self, title,
                f"La impresora no está lista ({status.get('status', ('', 'sin estado'))[1]}): "
                "no se envía nada, porque el trabajo se quedaría atascado en la cola de "
                "Windows. Mira su pantalla o luces, resuelve el aviso y pulsa Actualizar (F5).")
            return None
        return queue

    def _confirm_print(self, title, text):
        box = QMessageBox(QMessageBox.Question, title, text,
                          QMessageBox.Yes | QMessageBox.Cancel, self)
        box.button(QMessageBox.Yes).setText("Imprimir")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Yes

    def _send_job(self, queue, label, send, wait_text):
        """Send a document to a Windows queue and wait (reading nothing from the printer)
        until it has left the queue."""
        try:
            old_jobs = spooler.job_ids(queue.name)  # only wait for the job sent now
        except Exception:
            old_jobs = set()
        try:
            send()
        except RuntimeError as exc:
            self._log(f"Error al imprimir: {exc}")
            return
        self.activity = ("printing", label)
        self._log(f"{label} enviada a «{queue.name}». Esperando a que termine...")
        history.record("prueba", self.model_name, self.info.get("serial_number", ""),
                       detail=f"{label} en {queue.name}")
        self._render_history()
        self.points_before = dict(self.points)
        self._spool_text = wait_text
        self._show_wait(wait_text)
        self._set_busy(True)
        self._spool_deadline = time.time() + 300
        self._spool_problem = ""
        self._spool_label = label
        QTimer.singleShot(3000, lambda: self._check_spool(queue.name, old_jobs))

    def print_test_page(self):
        queue = self._queue_ready("Página de prueba")
        if queue is None:
            return
        key = self._page_version_key()
        name, _path, ink = testpage.VERSIONS[key]
        if not self._confirm_print(
                "Página de prueba MAG",
                f"Se imprimirá la página de prueba «{name}» (A4, {ink}) en «{queue.name}».\n\n"
                "Comprueba que hay papel A4. No se consulta la impresora hasta que termine."):
            return
        self._send_job(queue, f"Página de prueba MAG ({name})",
                       lambda: testpage.print_pdf(queue=queue.name,
                                                  path=testpage.version_path(key)),
                       "Imprimiendo la página de prueba. Se releerán los contadores al terminar.")

    def _check_spool(self, queue, old_jobs=()):
        try:
            pending, problem = spooler.queue_state(queue, ignore=old_jobs)
        except Exception:  # spooler unreachable: fall back to a fixed wait
            pending, problem = 0, ""
        left = self._spool_deadline - time.time()
        if not pending:
            problem = ""
        if problem != getattr(self, "_spool_problem", ""):
            self._spool_problem_changed(queue, old_jobs, problem)
        if pending and left > 0:
            text = getattr(self, "_spool_text", "") or (
                "Imprimiendo la página de prueba. Se releerán los contadores al terminar.")
            if problem:
                text = (f"Windows marca un problema en «{queue}»: {problem}. La impresora no "
                        "está imprimiendo: mira su pantalla o luces. La aplicación no la "
                        "consulta mientras el trabajo siga en la cola; espera "
                        f"{int(left) // 60}:{int(left) % 60:02d} más. Cancelar el trabajo en "
                        "Windows (Impresoras y escáneres, abrir la cola) la libera antes.")
            self.wait_label.setText(text)
            QTimer.singleShot(3000, lambda: self._check_spool(queue, old_jobs))
            return
        if pending:
            self._log("El trabajo sigue en la cola de Windows: se deja de esperar. Revisa la "
                      "impresora y cancela el trabajo si no va a imprimirse.")
        self._close_spool_box()
        QTimer.singleShot(12_000, self._maintenance_finished)  # paper still ejecting

    @staticmethod
    def _paper_title(problem):
        """Short title for a spooler problem text from spooler.queue_state()."""
        if "atasco" in problem or "papel" in problem:
            # Epson drivers report a jam as "sin papel" too: the printer cannot tell them apart
            return "Sin papel o papel trabado"
        if "tapa" in problem:
            return "Tapa abierta"
        return "La impresora informa un error"

    def _spool_problem_changed(self, queue, old_jobs, problem):
        """A problem appeared on (or left) the job we sent: show it everywhere, not only in
        the wait banner. Reads the spooler only; the printer is still left alone."""
        self._spool_problem = problem
        label = getattr(self, "_spool_label", "") or "Trabajo"
        if not problem:
            self._close_spool_box()
            self._log("Windows ya no marca problemas: la impresora sigue con el trabajo.")
            self._set_chip("Imprimiendo", C["warn"])
            self._set_activity("printing", label)
            return
        title = self._paper_title(problem)
        self._log(f"ERROR durante «{label}»: {title} (Windows: {problem}).")
        self._set_chip(f"Error: {title}", C["bad"])
        self._set_activity("error", f"{title}. Revisa la impresora.")
        history.record("error", self.model_name, self.info.get("serial_number", ""),
                       detail=f"{title} durante {label} ({problem})")
        self._render_history()
        QApplication.alert(self)  # flash the taskbar button
        if getattr(self, "_spool_box", None) is not None:
            return
        box = QMessageBox(QMessageBox.Warning, title,
                          f"La impresora se detuvo durante «{label}».\n\n"
                          f"Windows informa: {problem}.\n\n"
                          "Si la hoja quedó trabada, retírala con cuidado desde la bandeja de "
                          "salida (o desde atrás) y pulsa el botón de la impresora para seguir. "
                          "Si quieres anular la impresión, cancela el trabajo.", parent=self)
        cancel = box.addButton("Cancelar el trabajo", QMessageBox.DestructiveRole)
        box.addButton("Esperar", QMessageBox.RejectRole)
        box.setModal(False)

        def answered(_button):
            self._spool_box = None
            if box.clickedButton() is not cancel:
                return
            try:
                count = spooler.cancel_jobs(queue, ignore=old_jobs)
                self._log(f"Trabajo cancelado en «{queue}» ({count}). Si quedó una hoja "
                          "dentro, retírala y pulsa el botón de la impresora.")
            except Exception as exc:
                self._log(f"No se pudo cancelar el trabajo: {exc}. Cancélalo desde "
                          "Impresoras y escáneres de Windows.")

        box.buttonClicked.connect(answered)
        self._spool_box = box
        box.show()

    def _close_spool_box(self):
        box = getattr(self, "_spool_box", None)
        self._spool_box = None
        if box is not None:
            box.close()

    # ---- diagnostic pattern (print, scan, analyse) --------------------------------
    def print_diagnostic(self):
        title = "Patrón de diagnóstico"
        queue = self._queue_ready(title)
        if queue is None:
            return
        if not self._confirm_print(
                title,
                f"Se imprimirá el patrón de diagnóstico (A4, poca tinta) en «{queue.name}».\n\n"
                "Usa papel común blanco, sin arrugas. Cuando salga, escanéalo con «Escanear y "
                "analizar» (o con otro programa y «Analizar imagen»)."):
            return
        stamp = diagnostic.stamp_text(self.model_name, self.info.get("serial_number", ""))
        self._send_job(queue, title,
                       lambda: diagnostic.print_pattern(queue=queue.name, stamp=stamp),
                       "Imprimiendo el patrón de diagnóstico. Cuando salga, escanéalo con "
                       "«Escanear y analizar».")

    def scan_diagnostic(self):
        if self.busy:
            return
        self._log("Buscando escáneres (WIA)...")
        self._run(scanner.list_scanners, self._scanners_found)

    def _scanners_found(self, found, error):
        title = "Escanear el patrón"
        if error:
            self._log(f"No se pudo consultar los escáneres de Windows: {error}")
            return
        if not found:
            QMessageBox.warning(
                self, title,
                "Windows no ve ningún escáner (WIA). Enciende la multifunción y revisa que "
                "aparezca en «Impresoras y escáneres», o escanea la hoja con otro programa o "
                "con el celular y usa «Analizar imagen».")
            return
        chosen = scanner.pick(found, self.model_name)
        if chosen is None:
            names = [s.name for s in found]
            name, ok = QInputDialog.getItem(self, title, "¿Con qué escáner?", names, 0, False)
            if not ok:
                return
            chosen = found[names.index(name)]
        box = QMessageBox(
            QMessageBox.Question, title,
            f"Pon la hoja del patrón boca abajo en el vidrio de «{chosen.name}» y cierra la "
            "tapa. Puede ir torcida o al revés; tienen que entrar las cuatro marcas de las "
            "esquinas.\n\nSe escanea en color a 300 ppp (tarda menos de un minuto).",
            QMessageBox.Yes | QMessageBox.Cancel, self)
        box.button(QMessageBox.Yes).setText("Escanear")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        if box.exec() != QMessageBox.Yes:
            return
        path = SCANS_DIR / f"patron_{datetime.now():%Y%m%d_%H%M%S}.png"
        hp = self.brand == "hp"

        def work():
            saved = scanner.scan(chosen.id, path, dpi=300)
            return saved, diagnostic.analyze(diagnostic.load(saved), hp=hp)
        self._log(f"Escaneando con «{chosen.name}»...")
        self._show_wait(f"Escaneando el patrón con «{chosen.name}» y buscando fallas...")
        self._run(work, self._diagnostic_done)

    def open_diagnostic(self):
        if self.busy:
            return
        start = str(SCANS_DIR if SCANS_DIR.is_dir() else Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Analizar un escaneo del patrón", start,
            "Imágenes y PDF (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf);;Todos (*.*)")
        if not path:
            return
        hp = self.brand == "hp"
        self._log(f"Analizando {Path(path).name}...")
        self._show_wait("Buscando fallas en el escaneo del patrón...")
        self._run(lambda: (Path(path), diagnostic.analyze(diagnostic.load(path), hp=hp)),
                  self._diagnostic_done)

    def _diagnostic_done(self, result, error):
        self._hide_wait()
        if error:
            self._log(f"Diagnóstico: {error}")
            QMessageBox.warning(self, "Diagnóstico por escaneo", error)
            return
        source, found = result
        serial = self.info.get("serial_number", "") or "sin-serie"
        report.REPORTS.mkdir(parents=True, exist_ok=True)
        image_path = report.REPORTS / f"Diagnostico_{serial}_{datetime.now():%Y%m%d_%H%M%S}.png"
        if not diagnostic.annotated(found).save(str(image_path)):
            image_path = None
        self._log(found.summary())
        problems = [f.title for f in found.problems()]
        history.record("diagnóstico", self.model_name, self.info.get("serial_number", ""),
                       detail="; ".join(problems) or "sin fallas a la vista",
                       file=image_path.name if image_path else "", scan=str(source))
        self._render_history()
        color = {"ok": C["ok"], "info": C["ok"], "warn": C["warn"], "bad": C["bad"]}[found.level]
        self.diag_note.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.diag_note.setText(f"Último análisis ({datetime.now():%H:%M}): "
                               + ("; ".join(problems) or "sin fallas a la vista") + ".")
        DiagnosticDialog(self, found, image_path).exec()

    def _maintenance_finished(self):
        self.activity = ("", "")
        self._hide_wait()
        self._notify()
        self._set_busy(False)
        self.refresh(attempts=6)  # still ejecting paper? retry every 10 s

    # ---- eeprom -----------------------------------------------------------
    def read_dump(self):
        if self._refuse_hp("Lectura de EEPROM"):
            return
        start, end = self.sp_start.value(), self.sp_end.value()
        if end < start:
            QMessageBox.warning(self, "EEPROM", "El final debe ser mayor que el inicio.")
            return
        self._log(f"Leyendo EEPROM {start}-{end} (unos 40 s para 2048 celdas)...")
        model = self.model_name
        self._run(lambda: be.dump(model, start, end), self._dump_done)

    def _dump_done(self, cells, error, quiet=False):
        if error or not cells:
            self._log(f"Error: {error or 'sin datos'}")
            return
        self.dump_cells = cells
        first, last = min(cells) // 16, max(cells) // 16
        self.grid.setRowCount(0)
        self.grid.setRowCount(last - first + 1)
        self.grid.setVerticalHeaderLabels([f"{r * 16:04X}" for r in range(first, last + 1)])
        reset_cells = set(be.cells_for(self.model_name))
        for addr, value in cells.items():
            item = QTableWidgetItem("--" if value is None else f"{value:02X}")
            item.setTextAlignment(Qt.AlignCenter)
            item.setToolTip(cell_tooltip(addr, value, addr in reset_cells))
            if addr in reset_cells:
                item.setForeground(QBrush(QColor(C["ok"])))
            elif value:
                item.setForeground(QBrush(QColor(C["text"])))
            else:
                item.setForeground(QBrush(QColor(C["muted"])))
            self.grid.setItem(addr // 16 - first, addr % 16, item)
        if not quiet:
            self._log(f"EEPROM leída: {len(cells)} celdas.")

    def export_dump(self):
        if not self.dump_cells:
            self._log("Primero lee la EEPROM.")
            return
        self._save_csv("Exportar EEPROM", f"eeprom_{datetime.now():%Y%m%d_%H%M%S}.csv",
                       ["address", "hex", "decimal"],
                       [[addr, "" if value is None else f"{value:02X}", value]
                        for addr, value in sorted(self.dump_cells.items())])


def set_taskbar_identity():
    """Without its own AppUserModelID Windows groups pythonw.exe under the Python icon;
    with one, the taskbar shows this app's icon and name."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"MAG.{APP_NAME}.1")
    except (AttributeError, OSError):
        pass


def main():
    set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setFont(QFont("Segoe UI", 9))
    # light: classic native controls (windowsvista), not the rounded Win11 look
    apply_theme(app, prefs.load().get("dark") is not False)  # dark unless turned off
    splash = InkSplash(APP_NAME)
    splash.set_message("Cargando la base de modelos...")
    splash.show()
    app.processEvents()
    shown_at = time.monotonic()
    win = MainWindow()

    def ready():
        # Keep the splash long enough to be seen, then fill it up and open the window.
        wait = max(0, int(1800 - (time.monotonic() - shown_at) * 1000))
        QTimer.singleShot(wait, lambda: splash.finish(win.show))

    win.on_booted = ready

    def fallback():  # never stay on the splash if loading hangs
        if win.on_booted:
            win.on_booted = None
            splash.finish(win.show)

    QTimer.singleShot(10_000, fallback)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
