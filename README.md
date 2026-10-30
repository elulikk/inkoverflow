# InkOverflow

Banco de trabajo para impresoras Epson EcoTank (antes «Epson Waste Ink Utility»). Interfaz PySide6 para leer y mantener impresoras Epson EcoTank por USB: contadores de
almohadillas, limpieza de cabezales, pruebas de impresión, reseteo de contadores, visor de
EEPROM, historial e informe de servicio en PDF. Probada con una **L3150**. El modelo se detecta
solo, a partir de la impresora que Windows ve conectada por USB en ese momento; la base de datos
incluye los 117 modelos del backend más la **XP-231** y la XP-230 (mapeadas, ver más abajo).

## Arrancar

```
iniciar.bat
```

o `.venv\Scripts\python.exe app.py`.

## Instalar en otra PC

Hace falta tener **Git** y **Python** instalados. El repositorio es privado: la primera vez,
`git clone` pide iniciar sesión con la cuenta de GitHub.

```
git clone https://github.com/elulikk/inkoverflow.git
cd inkoverflow
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Después se abre con `iniciar.bat`. La carpeta `.venv` (las librerías de Python, unos 765 MB) no
está en GitHub: los dos últimos comandos la crean. `backend/` ya viene incluido en el
repositorio, no hay que clonarlo aparte. `InkOverflow.lnk` apunta a la carpeta original; en una
PC nueva hay que recrear el acceso directo.

## Qué hace cada página

| Página | Contenido |
|---|---|
| Resumen | Indicadores de las almohadillas en puntos y %, **tinta por color**, **avisos de la impresora**, uso, copia y reseteos |
| Detalles | Todos los datos leídos, copia al portapapeles, JSON e **Informe PDF** |
| Mantenimiento | Tests de inyectores, **limpieza CL1/CL2/CL3/Power ink flushing**, página de prueba MAG, **diagnóstico por escaneo** |
| EEPROM | Visor hexadecimal de solo lectura y exportación a CSV |
| Historial | Cada operación hecha con la aplicación; se consulta **sin impresora** y por impresora o todas |

![InkOverflow](brand/banner.png)

## Marca

La carpeta `brand/` tiene el icono de la aplicación (`icon.svg`, `icon_16.png` … `icon_512.png`,
`inkoverflow.ico`), los logos para fondo oscuro y claro (`logo_dark`, `logo_light`, en SVG y PNG),
la marca sola (`mark_dark.svg`, `mark_light.svg`), el banner de este README y un muestrario
(`muestrario.png`). El texto de los SVG está convertido a contornos, así que no depende de ninguna
fuente instalada. Todo sale de un solo script; para regenerarlo tras cambiar colores o formas:

```
.venv\Scripts\python.exe brand\make_brand.py
```

`InkOverflow.lnk` es un acceso directo con el icono (copia o arrastra el archivo al escritorio; si
mueves la carpeta del proyecto hay que recrearlo). La aplicación usa su propio identificador de
Windows para que la barra de tareas muestre este icono y no el de Python.

## Comodidades

* **Atajos:** `F5` / `Ctrl+R` actualizan (solo si no hay nada en curso, igual que el botón);
  `Ctrl+1` … `Ctrl+5` cambian de página.
* **Botones desactivados con explicación:** pasa el ratón por encima y dice por qué (sin impresora,
  varias impresoras USB, modelo distinto, operación en curso...).
* **Sin impresora:** aviso en Resumen, guiones en lugar de los números de la última lectura y el
  Historial sigue disponible (doble clic en un informe o una copia para abrirlo; botones para abrir
  las carpetas y exportar a CSV).
* **Limpiezas:** barra de progreso con el tiempo estimado que queda, aviso sonoro y parpadeo en la
  barra de tareas al terminar, y la ventana no se deja cerrar mientras limpia (no se podría leer ni
  restaurar el contador).
* **Copiar resumen:** cifras clave en texto plano para pegar en un chat con el cliente.
* **EEPROM:** al pasar el ratón por una celda se ve su dirección y su valor en hex, decimal y binario.
* **Preferencias** (`data/prefs.json`): tamaño y posición de la ventana, última página y rango de
  EEPROM. Nunca se recuerda el modo de limpieza ni la casilla de restaurar el contador.

## Cómo funciona por dentro (y por qué)

* **Qué impresora hay conectada** (`pnp.py`, `detect.py`): al arrancar y en cada *Actualizar* la
  aplicación pregunta a Windows qué Epson USB está **presente ahora** (SetupAPI, solo los
  dispositivos presentes; los de impresoras ya desenchufadas no cuentan) y lee el nombre que
  Windows guarda de ella («EPSON L3150 Series» en la interfaz USB y «L3150 Series» en el
  dispositivo padre). Ese nombre se cruza con la base de modelos del backend, comparando el nombre
  entero (L315 no es L3150; «XP-231 235 Series» se lee como XP-231 y XP-235). **Las colas de Windows
  ya no deciden el modelo**: el PC acumula una por cada impresora que alguna vez se conectó. Es
  una lectura del registro de dispositivos: no abre la impresora, ni abre sesión D4, ni lanza el
  backend, así que es segura aunque la impresora esté imprimiendo, expulsando o limpiando.
  * **Cola «conectada»:** la cola de Windows de la impresora es la que está en el puerto
    (`USB017`...) del nodo `USBPRINT` presente. La descripción del puerto no sirve: suele ser
    «Puerto de impresora virtual para USB» también para la impresora enchufada.
  * **Ninguna impresora:** lo dice en el aviso, el selector queda en «Automático · sin impresora» y
    no se preselecciona ningún modelo ni se lanza el backend.
  * **Varias:** no adivina; hay que dejar conectada solo una (igual que para escribir).
  * **Modelo que el backend no tiene** (p. ej. L3210, L3250): lo dice con el nombre que da Windows
    y no se lee ni se resetea nada.
  * **Selector de modelo:** la primera opción es *Automático* (muestra el modelo detectado). Si
    eliges un modelo a mano, manda hasta que vuelvas a elegir *Automático*; es también la salida
    para una impresora que Windows no lista como impresora USB (otro driver). Si lo elegido a mano
    no es lo que Windows ve conectado, el registro lo avisa.
* **Lectura y reseteos:** `backend/epson_print_conf.py` se ejecuta como proceso aparte
  (`backend_cli.py`). `modeldb.py` vuelca su base de datos de modelos (almohadillas, celdas,
  claves).
* **XP-231 y XP-230** (`mapped_models.py`): el backend no las trae por nombre (el clon de
  `backend/` está al día con GitHub, commit del 19-10-2026; solo tiene XP-235/XP-225 como alias).
  Se mapean a la entrada **XP-432** porque el `epson.toml` de reinkpy (la otra base pública que el
  propio README del backend cita como fuente) las pone en el mismo registro que XP-235/432/433/435,
  con la misma clave de lectura (0x0585), la misma clave de escritura y las mismas celdas de
  almohadilla y reseteo que tiene el backend para XP-432. No se ha tocado `backend/`: la
  aplicación solo copia esa entrada y ejecuta el backend con `-m XP-432`. Si algún día el backend
  trae la XP-231 por nombre, manda su entrada. **No está verificada en una XP-231 real**: la
  aplicación lo avisa y conviene usar «Simular reseteo» y revisar la copia antes del permanente.
  La limpieza de cabezales sigue bloqueada en ellas (solo familia L3150). En la impresora real
  del taller Windows la llama **«EPSON XP-230 Series»** (USB 04B8:1102), por eso se añadió también
  la XP-230. La entrada XP-432 del backend no define celdas de número de serie, así que con estos
  modelos la serie sale como «--» y el historial no puede separar una impresora de otra.
* **Limpieza de cabezales** (`cleaning.py`): decodificada de una captura USB del programa
  original (`captures/limpiezas_original.pcap`). Es una sola orden por el socket de datos D4
  `0x40`: `1b 7c 00 06 00 <clave_lectura> 84 7b 42 <modo>`, con modo `01` CL1, `02` CL2, `03` CL3,
  `04` Power ink flushing. Se espera a que el estado vuelva a reposo y se muestran los puntos
  que subió el contador. **Verificada solo en la familia L3150**; en otros modelos está bloqueada.
* **XP-2100 / XP-2101** (`driver_jobs.py`): test de inyectores y limpieza copiados byte a byte
  del driver de Windows de Epson (captura `captures/xp2100_driver_mant.pcap`, driver 3.02.02.00).
  Van por la interfaz de impresión en modo remoto ESC/P2: `NC` (test) y `CH 02 00 00 00`
  (limpieza, un solo modo). Igual que el driver, no se le habla a la impresora durante los
  primeros 130 s de la limpieza; después se espera el reposo y se relee el contador. Sin
  restauración del contador. En la captura una limpieza gastó un 6-7 % de cada cartucho 206.
* **"No incrementar el contador":** el original no tiene una orden para eso; relee el contador
  antes, y lo **reescribe** al terminar. La tinta va igualmente a la almohadilla. Aquí la casilla
  viene desmarcada, pide confirmación reforzada y anota los puntos reescritos en
  `data/state.json`; el indicador muestra entonces el nivel real estimado. Un reseteo permanente
  pone esa cuenta a cero.
* **Tests de inyectores:** datos RAW directos al dispositivo USB (`spooler.send_direct`): la cola
  de Windows con el driver V4 de Epson los rechaza (evento 824). La página de prueba MAG, que es un
  documento normal, sí se imprime por la cola.
* **Página de prueba MAG:** igual que el mantenimiento directo, solo se envía si la impresora está
  lista (con estado Error no se manda nada: el trabajo se quedaría atascado en la cola). Mientras
  espera a que la cola se vacíe, la aplicación lee el estado del spooler de Windows (sin tráfico
  USB) y, si marca un error, lo dice en la franja de progreso en vez de parecer colgada. Espera
  como máximo 5 minutos; cancelar el trabajo en Windows la libera antes.
* **Tinta y avisos** (`printer_state.py`): salen del bloque de estado que el backend ya lee en
  cada *Actualizar* (`info["printer_status"]`, orden `st`), así que **no hay ninguna consulta
  nueva a la impresora**. Las impresoras de cartucho (la XP-230) informan un nivel de 0 a 100
  estimado por el chip. En las EcoTank **el tanque no se mide**: la L3150 de la captura informó
  105 en los cuatro colores en sus 838 respuestas, antes y después de las limpiezas. Por eso un
  valor mayor que 100 se muestra como «no medido», junto con las recargas registradas en la
  EEPROM. El código de error y las advertencias (sin papel, atasco, tapa abierta, tinta baja,
  almohadillas llenas…) se traducen a un mensaje con qué hacer y la luz que suele verse en el
  panel (orientativa: el patrón exacto depende del modelo). Se ven en el chip de la barra de
  estado, en la franja amarilla (solo los errores), en Resumen, en Detalles, en el registro,
  en el informe PDF y en *Copiar resumen*.
* **Regla de oro:** no abrir una sesión D4 nueva mientras la impresora imprime, expulsa o limpia
  (una consulta a destiempo cortó una hoja). Dentro de la sesión de limpieza se consulta el estado
  cada segundo, como hace el original.

## Diagnóstico por escaneo

Cinta **Mantenimiento › Diagnóstico por escaneo** (`diagnostic.py`, `scanner.py`):

1. **Imprimir patrón**: una hoja A4 por la cola de Windows elegida (mismas condiciones que la
   página MAG: impresora lista, cola «conectada»). Gasta poca tinta y va en vectores.
2. **Escanear y analizar**: escanea por WIA (el escáner de la multifunción u otro; si hay varios
   y ninguno coincide con el modelo, pregunta cuál), en color a 300 ppp, toda la superficie. Solo
   toca la parte escáner: no abre sesión D4 en la impresora, y no se puede usar mientras hay otra
   operación en curso. El escaneo crudo queda en `data/escaneos/`.
3. **Analizar imagen**: un escaneo guardado (PNG, JPG, BMP, TIFF o PDF), hecho con otro programa
   o con el celular. No hace falta impresora.

La hoja tiene cuatro marcas en las esquinas (como las de un código QR) y un cuadrito que indica
dónde va arriba: con ellas la imagen se endereza sola aunque la hoja esté torcida, al revés, más
chica o sea una foto en perspectiva. Qué se busca y en qué parte de la hoja:

| Bloque | Qué detecta |
|---|---|
| 1 · Cian, magenta, amarillo y negro macizos | **Inyectores tapados** (rayas blancas horizontales que cruzan el bloque de lado a lado; se ignoran las manchitas que no lo cruzan), un color que **no sale** o sale **flojo**, un color con **otro tono** (tinta mezclada) y un negro armado con colores |
| 2 · Líneas verticales finas | **Cabezal desalineado**: líneas escalonadas entre pasadas o dobles/borrosas |
| 3 · Líneas horizontales finas | **Avance de papel irregular**; en un escaneo plano, además, si el papel avanza de más o de menos (alto de la hoja contra su ancho) |
| 4 · Zona en blanco | **Manchas** de tinta, marcas de rodillos o del cabezal que roza (el polvo del vidrio, de menos de 0,5 mm, no cuenta) |

El resultado se ve en una ventana con la hoja enderezada y recuadros (rojo falla, ámbar revisar,
verde bien) y, para cada problema, qué hacer. La imagen marcada se guarda en `reports/` y la
operación queda en el Historial («diagnóstico»; doble clic la abre). Los umbrales están
pensados para papel común y un escáner plano; **todavía no se probaron con hojas impresas y
escaneadas de verdad**, solo con escaneos simulados.

## Impresoras HP (base: HP Smart Tank 580)

InkFlow también reconoce y **lee** impresoras HP. No escribe nada en una HP.

**Qué se lee y por dónde** (`hp_backend.py`, `hp_models.py`):

| Dato | Por USB (solo el registro de Windows) | Por red (IP de la HP) |
|---|---|---|
| Modelo | nombre que Windows le da («HP Smart Tank 580-590 series») | IPP `printer-make-and-model`, LEDM `ProductConfigDyn.xml` |
| Número de serie | final del id del dispositivo USB (`USB\VID_03F0&PID_xxxx\CN…`) | IPP `printer-device-id` (SN), LEDM |
| Firmware, número de producto | — | IPP, LEDM |
| Estado y avisos | estado de la cola de Windows (lo que el driver de HP informa) | IPP `printer-state-reasons`, LEDM `ProductStatusDyn.xml` |
| Tinta | — | LEDM `ConsumableConfigDyn.xml` (estado del sensor de cada tanque y de los cabezales), IPP `marker-levels` |
| Páginas, escaneos, copias, atascos | — | LEDM `ProductUsageDyn.xml` |

* **Una HP solo USB (Smart Tank 210-220) se lee sola, sin IP**: `hp_usb.py` le hace GET por su
  interfaz REST de USB (la de HP Smart) y trae tinta por tanque, cabezales, estado, firmware y
  páginas. Solo lee. Si HP Smart está abierto la interfaz está ocupada: la app lo avisa y muestra
  modelo y serie de Windows.
* La IP se escribe en **Inicio › HP por red (IP)** (se recuerda) o se toma sola de la cola de
  Windows de esa HP si es TCP/IP. Sin IP, una HP por USB muestra modelo y serie y la app explica
  cómo leer el resto. Con la IP y sin USB también se lee (HP por Wi-Fi).
* La Smart Tank 580 tiene **sensores de tinta baja**, no un medidor: la app muestra «con tinta» o
  «bajo» por tanque, y el porcentaje solo si la impresora lo informa.
* Por USB la app **no le manda nada** a la HP. HP contesta las consultas por su interfaz USB
  propia («REST»), no por la de impresión; HTTP o PJL mandados a la interfaz de impresión salen
  impresos como hojas de basura («GET /cdm/system/v1/status HTTP/1.1»).
* Por red solo se usan lecturas: `GET /DevMgmt/*Dyn.xml` y la operación IPP
  Get-Printer-Attributes (las pruebas lo comprueban sobre cada pedido).
* **Smart Tank 210-220**: se reconoce sola y usa su propio modelo 3D/2D (`hp_smart_tank_210`).
* **Sonda USB de HP** (`captures/hp_rest_probe.py`, no la usa la app): `GET` por la interfaz REST
  (MI_02, WinUSB, bulk 0x0a/0x8b) con HP Smart cerrado. HP Smart manda como `Host` la ruta del
  dispositivo USB (con `localhost` contesta 404). En Git Bash hay que poner `MSYS_NO_PATHCONV=1`,
  si no `/cdm/...` se convierte en una ruta de Windows. Lee estado, alertas, insumos e identidad.
  **No hay un comando para mover el carro**: se buscó en las capturas de HP Smart y en el
  firmware que expone la REST (`/cdm/supply/v1/cartridgeSetup` acepta PATCH, pero no respondió y
  no se sabe qué hace). El carro de la 210 solo se centra solo ante un error de cabezal.

**Almohadillas y reseteo en HP: deshabilitados.** HP no publica un contador de tinta residual
(absorbente) para sus impresoras de tanque, ni IPP ni LEDM lo informan, y no hay un reseteo
documentado. Los botones de copia y reseteo, los tests de inyectores, las limpiezas (son
comandos Epson) y la EEPROM quedan apagados con el motivo en el tooltip. Si la propia
impresora avisa del absorbente (`marker-waste-almost-full` / `marker-waste-full`), aparece en
Avisos. La página de prueba MAG sí se puede imprimir por la cola de Windows de la HP.

**Sin resolver:** leer tinta y estado por USB (habría que hablar HTTP por la interfaz «REST» de
HP, sin una HP para verificarlo); la API «CDM» (`/cdm/...`) de las HP más nuevas no se usa.

## Seguridad

* En una HP no se escribe nada (ver «Impresoras HP»).
* Solo se escribe con **una** impresora Epson conectada por USB (el mantenimiento y la limpieza
  lo exigen; con varias, la detección automática ni siquiera lee).
* La detección del modelo solo lee el registro de Windows: nunca abre la impresora.
* El reseteo permanente se bloquea si el modelo elegido no coincide con el de la impresora, y
  guarda siempre una copia en `backups/`.
* Un reseteo no sustituye a las almohadillas ni al depósito de residuos.

## Pruebas (sin impresora)

```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Comprueban, byte a byte contra la captura, los paquetes del canal de datos y las cuatro órdenes
de limpieza, la lectura de las respuestas de estado reales (reposo, limpiando, error) y todo el
flujo (éxito, restauración, error, impresora ocupada, tiempo agotado) contra una impresora simulada.
`tests/test_ui.py` recorre la ventana completa con esa impresora simulada y `tests/test_qol.py`
cubre las comodidades que no necesitan ventana, incluido el generador de la marca.
`tests/test_detect.py` cubre la detección (varias colas viejas y una impresora conectada, ninguna,
dos, un modelo que el backend no tiene, el modelo elegido a mano y volver a *Automático*, que
con nada conectado no se lanza ningún proceso del backend) y la XP-231 (en el selector, mismos
datos que XP-432, el backend se ejecuta con `-m XP-432`, limpieza bloqueada), además de la cola
«conectada», el caso de una impresora en estado Error (no se envía nada) y el estado de la cola
de Windows. `tests/test_printer_state.py` decodifica con el parser del backend las respuestas de
estado reales de la captura (reposo, limpiando, almohadillas llenas) y otras armadas a mano
(sin papel, atasco, tinta baja, cartuchos con nivel, código desconocido), y revisa el chip, la
franja, el Resumen, los Detalles y el informe. `tests/test_hp.py` lee una HP Smart Tank 580
simulada (`tests/fake_hp.py`: un servidor local que contesta IPP y LEDM como la impresora, y su
unidad USB como la lista Windows): detección, nombres reales de HP vistos en esta PC, lectura por
USB, por red, solo IPP, solo LEDM, sin respuesta, avisos, que solo lleguen lecturas, botones
apagados con motivo, Vista 3D, informe, resumen e Historial. `tests/test_diagnostic.py` imprime el patrón a PDF, lo «escanea» (girado, al revés, más chico, con ruido y desenfoque) con fallas pintadas encima y comprueba que se encuentren, y que una hoja limpia no dé falsas alarmas. 176 pruebas en total, todas contra
impresoras y listas de dispositivos simuladas.

## Licencias

El backend es EUPL-1.2 (Ircama/epson_print_conf); `epson-usb` y `epson-escp2` son sus
dependencias. Esta carpeta no incluye ni usa ningún archivo de las herramientas del fabricante.

## Vista 3D

La primera pestaña muestra la impresora en 3D (Qt Quick 3D, incluido en PySide6): se gira
con el ratón, los tanques muestran la tinta y la tapa trasera translúcida deja ver las
almohadillas manchadas según su porcentaje. Los botones de esa vista (reseteos, tests de
inyectores, patrón de color, página de prueba MAG y limpieza de cabezales) pulsan los mismos
botones de la cinta: mismas condiciones y confirmaciones.

- **Info al pasar / fija** (barra de cámara): por defecto, la info y los botones de la impresora,
  los tanques y las almohadillas aparecen en una tarjeta al pasar el cursor por esa pieza; «Info:
  fija» los deja siempre en pantalla. Se recuerda en `data/prefs.json` (`view3d_pinned`).
- **Imprimiendo / limpiando**: la carcasa se vuelve translúcida y se ve el carro moviéndose y la
  hoja saliendo, o el carro estacionado y la tinta bajando a las almohadillas (`view3d/Mechanism.qml`),
  con un cartel arriba (y el progreso, en la limpieza). «Interior» lo muestra a pedido.
- **FPS bajos**: si la vista va a menos de 20 cuadros por segundo durante 6 s seguidos, se apaga
  y queda apagada (`view3d_off`) hasta que se la reactive desde el aviso que la reemplaza, que
  también permite activarla sin ese control o pasar a la vista 2D.
- **Vista 2D** («Vista: 2D» en la barra de cámara): la misma impresora dibujada de frente con
  sprites 2D (`view3d/Printer2D.qml`), con los mismos paneles, tarjetas, botones e interior
  animado; no crea la escena 3D, así que es mucho más liviana y nunca se apaga por FPS bajos.
  Se arrastra para mover y la rueda acerca. Se recuerda en `view3d_2d`.
- **Tope de 30 FPS**: clic derecho sobre el contador de FPS (abajo a la derecha) limita la vista
  (3D o 2D) a 30 cuadros por segundo; otro clic derecho lo quita. Se recuerda en `view3d_fps30`.

Hay un modelo 3D por estilo de impresora, elegido por `data["style"]` según la impresora
conectada (sin estilo, o con uno desconocido, se ve la Epson):

| Estilo | Impresoras | Tanques | Almohadillas |
|---|---|---|---|
| `epson_l3150` | Epson L3150/L3250 | a la derecha, con visor | atrás, del lado de los tanques, tras una tapa translúcida |
| `hp_smart_tank_580` | HP Smart Tank 580 | al frente a la izquierda (K, C, M, Y) | en la base, a la derecha, bajo la estación de servicio; se ven por una ventana lateral que no existe en la impresora real |
| `hp_smart_tank_210` | HP Smart Tank 210-220 (la 580 sin escáner ni pantalla: tapa superior oscura y panel con botón de encendido, dos botones y luces) | igual que la 580 | igual que la 580 |
| `epson_xp2100` | Epson XP-2100/2101/2105 y XP-2150/2151/2155 (Windows llama a la XP-2101 «XP-2100 Series») | sin tanques: cuatro cartuchos Epson 206 (K, C, M, Y) en el carro, bajo el escáner. La cámara «Cartuchos» levanta el escáner y el carro va al centro, como para cambiarlos; un cartucho al 15 % o menos parpadea, igual que la luz de tinta del panel, y se avisa en la tarjeta de tinta | en la base, a la derecha, bajo la estación de servicio; ventana lateral que no existe en la impresora real |

- `printer3d.py`: puente entre la ventana y la escena (datos y pedidos); `STYLES` lista los estilos.
- `view3d/Printer3D.qml`: lo común a todos los estilos: piso, luces, cámara, etiquetas y HUD.
- `view3d/EpsonL3150.qml`, `view3d/HpSmartTank580.qml`, `view3d/HpSmartTank210.qml`, `view3d/EpsonXP2100.qml`: cada impresora (mallas, materiales,
  textos impresos, presets de cámara y adónde apuntan las etiquetas).
- `view3d/InkLiquid.qml`, `view3d/PadFelt.qml`, `view3d/Mechanism.qml` y `view3d/shaders/`: tinta, almohadillas y el interior animado, compartidos.
- `view3d/make_model.py`: genera las mallas (`view3d/meshes/<estilo>/`) con Blender, todos
  los estilos o solo el indicado:
  `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P view3d/make_model.py -- hp_smart_tank_580`
- `view3d/make_studio.py`: genera la iluminación de estudio `view3d/studio.hdr`.
