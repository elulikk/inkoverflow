// Samsung Xpress M2020(W) (style "samsung_m2020w") and M2070(W) (style "samsung_m2070w"):
// white with a glossy black top, the toner MLT-D111S (drum included). Sizes from
// laser.py SPECS.
import QtQuick

LaserPrinter {
    mfp: app.style === "samsung_m2070w"
    defaultTitle: mfp ? "Samsung Xpress M2070W" : "Samsung Xpress M2020W"
    brand: "samsung"
    tonerCode: "MLT-D111S"
    w: mfp ? 4.06 : 3.31
    d: mfp ? 3.60 : 2.15
    h: mfp ? 2.53 : 1.78
    hasLcd: mfp
    bodyColor: "#eef0f2"
    coverColor: "#1f2124"
    scannerColor: "#eef0f2"
    floorColor: "#2a2c30"
    panelColor: "#1f2124"
    logoColor: "#5d646b"
    gloss: 0.5
}
