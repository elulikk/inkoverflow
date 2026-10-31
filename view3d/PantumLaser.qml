// Pantum P2500(W) (style "pantum_p2500w") and M6500-M6550(NW) (style "pantum_m6550nw"):
// dark grey with a glossy black top, the toner PC-210 (drum included). Sizes from
// laser.py SPECS.
import QtQuick

LaserPrinter {
    mfp: app.style === "pantum_m6550nw"
    defaultTitle: mfp ? "Pantum M6550NW" : "Pantum P2500W"
    brand: "pantum"
    tonerCode: "PC-210"
    w: mfp ? 4.17 : 3.37
    d: mfp ? 3.05 : 2.20
    h: mfp ? 3.01 : 1.78
    hasLcd: mfp
    bodyColor: "#2c2d30"
    coverColor: "#1b1c1f"
    scannerColor: "#2c2d30"
    floorColor: "#2f3134"
    doorColor: "#2a2b2e"
    panelColor: "#151618"
    logoColor: "#b9bec4"
    gloss: 0.6
}
