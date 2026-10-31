// HP LaserJet M110-M111w (style "hp_laserjet_m111") and LaserJet MFP M140-M141w (style
// "hp_laserjet_m141"): small and white, the toner HP 150A. Sizes from laser.py SPECS.
import QtQuick

LaserPrinter {
    mfp: app.style === "hp_laserjet_m141"
    defaultTitle: mfp ? "HP LaserJet MFP M141w" : "HP LaserJet M111w"
    brand: "hp"
    tonerCode: "150A"
    w: mfp ? 3.60 : 3.46
    d: mfp ? 2.64 : 1.89
    h: mfp ? 1.97 : 1.59
    bodyColor: "#eceef0"
    coverColor: "#e4e6e9"
    floorColor: "#a7acb2"
    panelColor: "#c9cdd2"
    logoColor: "#a0a6ac"
    gloss: 0.3
}
