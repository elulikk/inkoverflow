// Brother HL-1210W-1212W (style "brother_hl1212w") and DCP-1610W-1612W (style
// "brother_dcp1612w"): black, the toner TN-1060 with its own drum unit. Sizes from
// laser.py SPECS.
import QtQuick

LaserPrinter {
    mfp: app.style === "brother_dcp1612w"
    defaultTitle: mfp ? "Brother DCP-1612W" : "Brother HL-1212W"
    brand: "brother"
    tonerCode: "TN-1060"
    w: mfp ? 3.85 : 3.40
    d: mfp ? 3.40 : 2.38
    h: mfp ? 2.55 : 1.89
    hasLcd: mfp
    bodyColor: "#25262a"
    coverColor: "#2c2e32"
    floorColor: "#303236"
    doorColor: "#2a2c30"
    panelColor: "#18191c"
    logoColor: "#c9cdd2"
    gloss: 0.35
}
