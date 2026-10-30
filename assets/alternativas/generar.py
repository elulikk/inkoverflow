"""Genera alternativas de la prueba de impresión MAG con menos tinta.

Uso:  python assets/alternativas/generar.py
Crea prueba_mag_A.pdf ... prueba_mag_D.pdf en esta carpeta (usa Chrome headless).
"""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]


def logo(color):
    data = (HERE / f"logo_mag_{color}.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }
:root { --mag:#0b3d91; --azul2:#1a6fd8; --cian:#22d3ee; --violeta:#a855f7;
        --magenta:#ff2d8a; --tinta:#0a0a1a; --gris:#6b7280; --linea:#9fb3d1;
        --grad: linear-gradient(90deg,#0b3d91,#1a6fd8 25%,#22d3ee 50%,#a855f7 75%,#ff2d8a); }
html, body { width:210mm; height:297mm; background:#fff; }
body { font-family:'Montserrat',sans-serif; color:var(--tinta); position:relative; overflow:hidden; }
.reg { position:absolute; width:9mm; height:9mm; }
.reg svg { width:100%; height:100%; }
body { display:flex; flex-direction:column; }
main { padding: 0 16mm var(--pb,26mm); flex:1; display:flex; flex-direction:column; justify-content:space-between; }
h2 { display:flex; align-items:center; gap:2.5mm; font-size:6.5pt; font-weight:700;
     letter-spacing:.28em; color:var(--mag); margin:5mm 0 2.5mm; }
h2 b { border:.3mm solid var(--mag); color:var(--mag); border-radius:1.2mm; padding:.3mm 1.6mm;
       letter-spacing:.1em; }
h2::after { content:''; flex:1; height:.25mm; background:var(--linea); }
.sw { display:flex; gap:var(--swgap,1.6mm); text-align:center; font-size:4.6pt; color:#333;
      line-height:1.25; }
.sw div { flex:1; }
.sw div.gap { flex:0 0 2mm; }
.sw div i { display:block; height:var(--h1,32mm); }
.sw div b { display:block; font-size:7pt; margin-top:1.2mm; color:var(--tinta); }
.sw div span { display:block; min-height:2.4em; }
.grays { display:grid; grid-template-columns:repeat(11,1fr); height:var(--hg,7mm); }
.bar { height:var(--hb,6.5mm); margin-top:1.6mm; border-radius:1mm; }
.lines { display:grid; grid-template-columns:1fr .9fr 1fr; gap:6mm; font-size:5pt; color:var(--gris); }
.lines .h i { display:block; background:#000; margin-bottom:1.4mm; }
.lines .v { display:flex; gap:1.4mm; height:12mm; align-items:stretch; }
.lines .v i { background:#000; display:block; }
.hatch { height:12mm; border:.25mm solid #000;
         background:repeating-linear-gradient(45deg,#000 0 .3mm,transparent .3mm 1.6mm); }
.cap { margin-top:1.2mm; }
.text { display:grid; grid-template-columns:1fr 1fr; gap:6mm; }
.neg { background:var(--tinta); color:#fff; border-radius:1.5mm; padding:var(--negp,3mm 3.5mm); }
.pill { border-radius:1.5mm; color:#fff; font-weight:700; font-size:9pt; padding:var(--pillp,2mm 3.5mm);
        margin-top:1.8mm; }
.shapes { display:flex; justify-content:space-between; align-items:center; height:var(--hs,20mm); }
.shapes svg { height:100%; }
.contact { display:flex; align-items:center; justify-content:space-between; margin-top:4mm;
           border:.35mm solid var(--mag); border-radius:6mm; padding:2mm 6mm; font-size:9pt;
           font-weight:700; color:var(--mag); }
.contact small { font-size:5.5pt; letter-spacing:.3em; color:var(--gris); font-weight:500; margin-right:3mm; }
.contact .sep { width:.25mm; height:5mm; background:var(--linea); }
"""

REG = ('<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="5.5" fill="none" stroke="{c}" stroke-width=".6"/>'
       '<path d="M10 0V20M0 10H20" stroke="{c}" stroke-width=".6"/></svg>')


def regs(color, top=True, bottom=True, inset="5mm"):
    out = []
    if top:
        out += [f'<div class="reg" style="top:{inset};left:{inset}">{REG.format(c=color)}</div>',
                f'<div class="reg" style="top:{inset};right:{inset}">{REG.format(c=color)}</div>']
    if bottom:
        out += [f'<div class="reg" style="bottom:{inset};left:{inset}">{REG.format(c=color)}</div>',
                f'<div class="reg" style="bottom:{inset};right:{inset}">{REG.format(c=color)}</div>']
    return "".join(out)


def body(compact=False):
    """Las 5 secciones de prueba. compact=True achica los bloques sólidos."""
    # Franjas verticales altas: un inyector tapado se ve como una raya blanca horizontal
    # que cruza la franja, en todos los colores a la vez.
    sw = [("#00aeef", "C", "CIAN"), ("#ec008c", "M", "MAGENTA"), ("#fff200", "Y", "AMARILLO"),
          ("#000", "K", "NEGRO"), ("#ed1c24", "R", "ROJO"), ("#00a651", "G", "VERDE"),
          ("#2e3192", "B", "AZUL"), None,
          ("#0b3d91", "", "AZUL MAG"), ("#1a6fd8", "", "AZUL 2"), ("#22d3ee", "", "CIAN NEÓN"),
          ("#a855f7", "", "VIOLETA"), ("#ff2d8a", "", "MAGENTA"), ("#0a0a1a", "", "TINTA")]
    cell = lambda x: ('<div class="gap"></div>' if x is None else
                      f'<div><i style="background:{x[0]}"></i><b>{x[1] or "&nbsp;"}</b><span>{x[2]}</span></div>')
    grays = "".join(f'<i style="background:hsl(0,0%,{v}%)"></i>' for v in range(0, 101, 10))
    hl = "".join(f'<i style="height:{w}mm"></i>' for w in (0.1, 0.2, 0.35, 0.5, 0.75, 1))
    vl = "".join(f'<i style="width:{w}mm"></i>' for w in (0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.4))
    sizes = [(4, "MAG Tecnología, soluciones para tu hogar y tu negocio.", 400),
             (5, "MAG Tecnología, soluciones para tu hogar y tu negocio.", 400),
             (6, "MAG Tecnología, soluciones para tu hogar.", 400),
             (8, "MAG Tecnología, soluciones para tu hogar.", 400),
             (10, "Tecnología que te acompaña", 700), (14, "Tecnología", 800)]
    txt = "".join(f'<div style="font-size:{s}pt;font-weight:{w};margin-bottom:.8mm">{s} pt · {t}</div>'
                  for s, t, w in sizes)
    txt += '<div style="font-size:20pt;font-weight:800;color:var(--mag)">20 pt · MAG</div>'
    pill_css = "background:none;border:.4mm solid {c};color:{c}" if compact else "background:{c}"
    pills = "".join(f'<div class="pill" style="{pill_css.format(c=c)}">{n} · ABCDEFG 0123456789</div>'
                    for c, n in (("var(--mag)", "AZUL"), ("var(--cian)", "CIAN"), ("var(--magenta)", "MAGENTA")))
    shapes = f"""
<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="19" fill="var(--mag)"/><circle cx="20" cy="20" r="11" fill="var(--cian)"/><circle cx="20" cy="20" r="6" fill="#fff"/><circle cx="20" cy="20" r="3" fill="var(--magenta)"/></svg>
<svg viewBox="0 0 40 40"><rect x="1" y="1" width="38" height="38" rx="5" fill="{'none' if compact else 'var(--tinta)'}" stroke="var(--tinta)" stroke-width="1"/><rect x="9" y="9" width="22" height="22" rx="3" fill="none" stroke="var(--cian)" stroke-width="2"/><rect x="14" y="14" width="12" height="12" rx="1.5" fill="var(--violeta)"/></svg>
<svg viewBox="0 0 40 40"><path d="M20 4 37 36H3Z" fill="none" stroke="var(--magenta)" stroke-width="4.5" stroke-linejoin="round"/></svg>
<svg viewBox="0 0 40 40"><path d="M20 1l5.6 12.2 13.4 1.4-10 9 2.9 13.2L20 30.1 8.1 36.8 11 23.6l-10-9 13.4-1.4z" fill="var(--mag)"/><circle cx="20" cy="21" r="5" fill="var(--cian)"/></svg>
<svg viewBox="0 0 40 40"><defs><radialGradient id="rg" cx=".4" cy=".35"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="var(--cian)"/><stop offset="1" stop-color="var(--mag)"/></radialGradient></defs><circle cx="20" cy="20" r="19" fill="url(#rg)"/></svg>
<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="14" fill="none" stroke="#000" stroke-width=".6"/><circle cx="20" cy="20" r="8" fill="none" stroke="#000" stroke-width=".6"/><circle cx="20" cy="20" r="2.6"/><path d="M20 0V40M0 20H40" stroke="#000" stroke-width=".5"/></svg>
<svg viewBox="0 0 40 40"><defs><pattern id="dt" width="2" height="2" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".6" fill="var(--azul2)"/></pattern><pattern id="dt2" width="2" height="2" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".4" fill="var(--magenta)" opacity=".6"/></pattern></defs><rect width="20" height="40" fill="url(#dt)"/><rect x="20" width="20" height="40" fill="url(#dt2)"/></svg>"""
    return f"""
<main><section>
<h2><b>01</b>COLORES PRIMARIOS Y SECUNDARIOS</h2>
<div class="sw">{''.join(cell(x) for x in sw)}</div>
</section><section><h2><b>02</b>ESCALA DE GRISES Y DEGRADADOS</h2>
<div class="grays">{grays}</div>
<div class="bar" style="background:linear-gradient(90deg,#000,#fff);border:.25mm solid #ccc"></div>
<div class="bar" style="background:var(--grad)"></div>
</section><section><h2><b>03</b>LÍNEAS FINAS Y TRAMA</h2>
<div class="lines">
 <div><div class="h">{hl}</div><div class="cap">0,1 · 0,2 · 0,35 · 0,5 · 0,75 · 1 mm</div></div>
 <div><div class="v">{vl}</div><div class="cap">Verticales · comprobar que no se corten</div></div>
 <div><div class="hatch"></div><div class="cap">Diagonales · moiré / bandas</div></div>
</div>
</section><section><h2><b>04</b>TAMAÑOS DE TEXTO</h2>
<div class="text">
 <div>{txt}</div>
 <div>
  <div class="neg"><div style="font-size:5pt">5 pt · texto en negativo sobre fondo oscuro</div>
   <div style="font-size:7pt;margin:.8mm 0">7 pt · texto en negativo sobre fondo oscuro</div>
   <div style="font-size:10pt;font-weight:700;color:var(--cian)">10 pt · negativo neón</div></div>
  {pills}
 </div>
</div>
</section><section><h2><b>05</b>FORMAS, ALINEACIÓN Y REGISTRO</h2>
<div class="shapes">{shapes}</div>
</section><div class="contact"><div><small>WHATSAPP</small>+54 294 494-0567</div><div class="sep"></div>
 <div><small>WEB</small>www.magtecnologia.com.ar</div></div>
</main>"""


FOOT_LIGHT = """
<footer style="position:absolute;left:0;right:0;bottom:0;height:22mm;padding:0 16mm;display:flex;
 align-items:center;gap:10mm">
 <div style="position:absolute;top:0;left:16mm;right:16mm;height:.8mm;background:var(--grad);border-radius:1mm"></div>
 <img src="{logo}" style="height:9mm">
 <div style="flex:1;font-size:6.5pt;line-height:1.5"><b style="letter-spacing:.2em;color:var(--mag)">MAG TECNOLOGÍA</b><br>
  Todo nítido, sin bandas ni cortes y con colores parejos: tu impresora está lista.</div>
 <div style="text-align:right"><div style="font-size:14pt;font-weight:800;color:var(--azul2)">✓ TEST OK</div>
  <div style="font-size:5pt;letter-spacing:.3em;color:var(--gris)">A4 · 210 × 297 mm</div></div>
</footer>"""

# --- Encabezados -----------------------------------------------------------

HEAD_A = """
<div style="height:2.2mm;background:var(--grad)"></div>
<header style="position:relative;height:42mm;padding:9mm 16mm 0 26mm;display:flex;gap:14mm;align-items:flex-start">
 <svg style="position:absolute;right:0;top:0;width:60mm;height:42mm" viewBox="0 0 60 42">
  <circle cx="48" cy="2" r="22" fill="none" stroke="var(--linea)" stroke-width=".35"/>
  <circle cx="48" cy="2" r="15" fill="none" stroke="var(--cian)" stroke-width=".35"/>
  <circle cx="34" cy="34" r="7" fill="none" stroke="var(--violeta)" stroke-width=".35"/></svg>
 <img src="{logo}" style="width:52mm">
 <div style="padding-top:1mm"><div style="font-size:21pt;font-weight:800;line-height:1.05;color:var(--mag)">PRUEBA DE<br>
  <span style="color:var(--azul2)">IMPRESIÓN</span></div>
  <div style="font-size:7pt;letter-spacing:.35em;color:var(--gris);margin-top:4mm">TEST DE COLOR · TRAZOS · TEXTO</div></div>
 <svg style="position:absolute;left:0;bottom:3mm;width:110mm;height:6mm" viewBox="0 0 110 6">
  <path d="M0 5H75L80 1H108" fill="none" stroke="var(--cian)" stroke-width=".4"/><circle cx="108" cy="1" r=".9" fill="var(--cian)"/></svg>
</header>"""

HEAD_B = """
<header style="height:24mm;background:var(--mag);padding:0 18mm 0 18mm;display:flex;align-items:center;
 justify-content:space-between">
 <img src="{logo}" style="height:15mm">
 <div style="text-align:right"><div style="font-size:15pt;font-weight:800;color:#fff">PRUEBA DE <span style="color:var(--cian)">IMPRESIÓN</span></div>
  <div style="font-size:6pt;letter-spacing:.35em;color:#c9d6ee;margin-top:1mm">TEST DE COLOR · TRAZOS · TEXTO</div></div>
</header>
<div style="height:1.2mm;background:var(--grad)"></div>"""

HEAD_C = """
<header style="position:relative;height:40mm;padding:8mm 16mm 0;display:flex;gap:9mm;align-items:center">
 <div style="width:62mm;height:26mm;background:var(--mag);border-radius:4mm;display:flex;align-items:center;
  justify-content:center;position:relative;overflow:hidden">
  <img src="{logo}" style="width:48mm">
  <div style="position:absolute;bottom:0;left:0;right:0;height:1mm;background:var(--grad)"></div></div>
 <div><div style="font-size:21pt;font-weight:800;line-height:1.05;color:var(--mag)">PRUEBA DE<br>
  <span style="color:var(--azul2)">IMPRESIÓN</span></div>
  <div style="font-size:7pt;letter-spacing:.35em;color:var(--gris);margin-top:3.5mm">TEST DE COLOR · TRAZOS · TEXTO</div></div>
</header>"""

HEAD_D = """
<header style="height:26mm;padding:9mm 16mm 0 18mm;display:flex;justify-content:space-between;align-items:flex-start">
 <img src="{logo}" style="height:12mm">
 <div style="text-align:right"><div style="font-size:14pt;font-weight:800;color:var(--tinta)">PRUEBA DE IMPRESIÓN</div>
  <div style="font-size:6pt;letter-spacing:.35em;color:var(--gris);margin-top:1mm">VERSIÓN AHORRO DE TINTA</div></div>
</header>
<div style="margin:0 16mm;height:.4mm;background:var(--grad)"></div>"""

FOOT_D = """
<footer style="position:absolute;left:16mm;right:16mm;bottom:9mm;display:flex;justify-content:space-between;
 align-items:baseline;font-size:6.5pt;color:var(--gris);border-top:.25mm solid var(--linea);padding-top:2mm">
 <span><b style="color:var(--tinta)">MAG TECNOLOGÍA</b> · Todo nítido y parejo: tu impresora está lista.</span>
 <b style="font-size:11pt;color:var(--tinta)">✓ TEST OK</b></footer>"""

COMPACT = ":root{--h1:22mm;--swgap:3.2mm;--hg:5mm;--hb:4mm;--hs:16mm;--negp:2.2mm 3mm;--pillp:1.4mm 3mm;--pb:18mm}"

VARIANTS = {
    "A": ("Blanca con acentos", HEAD_A.format(logo=logo("azul")), FOOT_LIGHT.format(logo=logo("azul")),
          regs("#000", top=False), "", False),
    "B": ("Franja angosta", HEAD_B.format(logo=logo("blanco")), FOOT_LIGHT.format(logo=logo("azul")),
          regs("#000", top=False), "", False),
    "C": ("Logo en tarjeta", HEAD_C.format(logo=logo("blanco")), FOOT_LIGHT.format(logo=logo("azul")),
          regs("#000", top=False), "", False),
    "D": ("Ahorro máximo", HEAD_D.format(logo=logo("azul")), FOOT_D, regs("#000", top=False, inset="3mm"),
          COMPACT, True),
}


def html(key):
    name, head, foot, marks, extra, compact = VARIANTS[key]
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Prueba MAG {key}</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>{CSS}{extra}</style></head><body>{head}{body(compact)}{foot}{marks}</body></html>"""


def main():
    chrome = next((c for c in CHROME if Path(c).exists()), None)
    if not chrome:
        sys.exit("No encontré Chrome ni Edge.")
    tmp = Path(tempfile.mkdtemp())
    for key in VARIANTS:
        src = tmp / f"prueba_mag_{key}.html"
        src.write_text(html(key), encoding="utf-8")
        out = HERE / f"prueba_mag_{key}.pdf"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=5000", f"--print-to-pdf={out}", src.as_uri()],
                       check=True, capture_output=True)
        print("ok", out.name)


if __name__ == "__main__":
    main()
