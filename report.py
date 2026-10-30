"""Service report (PDF) of one printer: identity, pad counters, usage and the latest
operations. Built from plain data so it can be tested without a printer."""
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Sequence

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter

REPORTS = Path(__file__).resolve().parent / "reports"
BRAND = "MAG Tecnología"
CONTACT = "WhatsApp +54 294 494-0567 · www.magtecnologia.com.ar"

LEVELS = ((90, "#b91c1c", "Crítico"), (70, "#b45309", "Alto"), (0, "#047857", "Normal"))


def _level(pct: float):
    for floor, color, label in LEVELS:
        if pct >= floor:
            return color, label
    return LEVELS[-1][1:]


def _rows(pairs: Sequence[tuple]) -> str:
    return "".join(
        f"<tr><td class='k'>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>" for k, v in pairs)


def _ink_text(inks) -> str:
    """'Negro no medido · Cian 40 % · Amarillo bajo' ('' without inks). Each ink is
    (name, level or None) or, for a printer with low-ink sensors (HP), (name, level or
    None, what the sensor says)."""
    parts = []
    for name, level, *rest in inks:
        state = rest[0] if rest else ""
        parts.append(f"{name} {f'{level} %' if level is not None else state or 'no medido'}")
    return " · ".join(parts)


def _ink_html(data: Dict) -> str:
    """Ink and printer warnings section ('' when the data has neither)."""
    inks, alerts = data.get("inks") or [], data.get("alerts") or []
    if not inks and not alerts and not data.get("refills"):
        return ""
    rows = []
    if inks:
        tanks = all(entry[1] is None for entry in inks)
        sensors = any(len(entry) > 2 and entry[2] for entry in inks)
        rows.append(("Tinta", _ink_text(inks) + (
            " (sensor de tinta baja: la impresora no da un porcentaje)" if tanks and sensors
            else " (la impresora no mide los tanques)" if tanks else "")))
    if data.get("refills"):
        rows.append(("Recargas registradas", data["refills"]))
    warn = ""
    if alerts:
        warn = "".join(
            f"<p class='warn'><b>{'Error' if severity == 'error' else 'Aviso'}:</b> "
            f"{escape(line)}</p>" if severity != "info" else f"<p>{escape(line)}</p>"
            for severity, line in alerts)
    else:
        rows.append(("Avisos", "La impresora no informa errores ni advertencias."))
    return f"<h2>Tinta y avisos</h2><table>{_rows(rows)}</table>{warn}"


def build_html(data: Dict) -> str:
    """data keys: model, serial, firmware, status, pads [(label, points, max)],
    hidden (int), usage [(label, value)], events [dict], when (datetime); optional
    inks [(name, level or None[, sensor state])], refills (str), alerts [(severity, text)],
    pads_note (str: why there are no pad counters, HP), via (str: how it was read)."""
    pads = ""
    for label, points, maximum in data["pads"]:
        pct = points / maximum * 100
        color, word = _level(pct)
        pads += (f"<tr><td class='k'>{escape(label)}</td><td>{points} / {maximum} puntos</td>"
                 f"<td style='color:{color};font-weight:bold'>{pct:.1f}% · {word}</td></tr>")
    if not pads and data.get("pads_note"):
        pads = f"<tr><td>{escape(data['pads_note'])}</td></tr>"
    hidden = ""
    if data.get("hidden"):
        main_label, main_points, main_max = data["pads"][0]
        real = main_points + data["hidden"]
        hidden = (f"<p class='warn'>Hay <b>{data['hidden']} puntos</b> de tinta vertida que el contador "
                  f"no cuenta (limpiezas con el contador restaurado). Nivel real estimado de "
                  f"{escape(main_label.lower())}: <b>{real} / {main_max} ({real / main_max * 100:.1f}%)</b>.</p>")
    events = "".join(
        f"<tr><td>{escape(e.get('when', '')[:16].replace('T', ' '))}</td>"
        f"<td>{escape(e.get('kind', ''))}</td><td>{escape(e.get('detail', ''))}</td></tr>"
        for e in data["events"][:12]) or "<tr><td colspan='3'>Sin operaciones registradas.</td></tr>"
    return f"""
<html><head><style>
 body {{ font-family: 'Segoe UI'; font-size: 10pt; color: #111; }}
 h1 {{ color: #0b4a96; font-size: 20pt; margin: 0; }}
 h2 {{ color: #0b4a96; font-size: 12pt; margin: 14px 0 4px 0; border-bottom: 1px solid #9db4d6; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td {{ padding: 3px 6px; border-bottom: 1px solid #e3e8ef; }}
 td.k {{ color: #555; width: 34%; }}
 .warn {{ background: #fff4e5; border: 1px solid #f0b46a; padding: 6px; }}
 .foot {{ color: #666; font-size: 8.5pt; margin-top: 18px; }}
</style></head><body>
<h1>Informe de servicio</h1>
<p>{escape(BRAND)} · {data['when']:%d/%m/%Y %H:%M}</p>
<h2>Impresora</h2>
<table>{_rows([("Modelo", data['model']), ("Número de serie", data['serial']),
                ("Firmware", data['firmware']), ("Estado", data['status'])]
               + ([("Leída por", data['via'])] if data.get('via') else []))}</table>
<h2>Almohadillas de tinta residual</h2>
<table>{pads}</table>{hidden}
{_ink_html(data)}
<h2>Uso</h2>
<table>{_rows(data['usage'])}</table>
<h2>Últimas operaciones</h2>
<table><tr><td><b>Fecha</b></td><td><b>Operación</b></td><td><b>Detalle</b></td></tr>{events}</table>
<p class='foot'>El reseteo del contador solo quita el bloqueo del firmware: no sustituye a las
almohadillas ni al depósito de residuos. Este informe refleja lo leído de la impresora en el momento
indicado.<br>{escape(CONTACT)}</p>
</body></html>"""


def summary_text(data: Dict) -> str:
    """The same figures as the report as plain text, short enough for a chat message."""
    lines = [f"{data['model']} · serie {data['serial']}", f"Estado: {data['status']}", ""]
    for label, points, maximum in data["pads"]:
        pct = points / maximum * 100
        lines.append(f"{label}: {points} / {maximum} puntos ({pct:.1f}% · {_level(pct)[1]})")
    if not data["pads"] and data.get("pads_note"):
        lines.append(f"Almohadillas: {data['pads_note']}")
    if data.get("hidden") and data["pads"]:
        main_label, main_points, main_max = data["pads"][0]
        real = main_points + data["hidden"]
        lines.append(f"Tinta sin contar: {data['hidden']} puntos; nivel real estimado de "
                     f"{main_label.lower()}: {real} / {main_max} ({real / main_max * 100:.1f}%)")
    if data.get("inks"):
        lines.append(f"Tinta: {_ink_text(data['inks'])}")
    for severity, line in data.get("alerts") or ():
        lines.append(f"{'Error' if severity == 'error' else 'Aviso'}: {line}")
    lines.append("")
    lines += [f"{label}: {value}" for label, value in data["usage"]]
    lines += ["", f"{BRAND} · {data['when']:%d/%m/%Y %H:%M}"]
    return "\n".join(lines)


def save_pdf(html: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                      QPageLayout.Orientation.Portrait,
                                      QMarginsF(16, 14, 16, 14), QPageLayout.Unit.Millimeter))
    document = QTextDocument()
    document.setHtml(html)
    document.print_(printer)
    return path


def build(data: Dict, folder: Path = REPORTS) -> Path:
    stamp = data["when"].strftime("%Y%m%d_%H%M%S")
    return save_pdf(build_html(data), folder / f"Informe_{data['serial']}_{stamp}.pdf")


def sample() -> Dict:
    """Plain example data (also used by the tests)."""
    return {"model": "EPSON L3150 Series", "serial": "X5E9205615", "firmware": "VD02JA 02 Oct 2019",
            "status": "Idle (ready to print)", "when": datetime(2026, 10, 24, 12, 0),
            "pads": [("Almohadilla principal", 5718, 6346), ("Almohadilla del platen", 0, 3416)],
            "hidden": 0, "usage": [("Páginas impresas", 67), ("Escaneos", 676)], "events": []}
