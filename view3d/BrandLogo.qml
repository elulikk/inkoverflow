// A maker's logo as printed lettering (Label3D), shared by every printer style. Set
// `brand` (epson, hp, canon, brother, pantum, samsung), `size` (mm), `color` and the
// position; the word, typeface and spacing come from the brand. Fonts are the ones every
// Windows has, picked to read like each logo.
import QtQuick
import QtQuick3D

Label3D {
    property string brand: "epson"
    readonly property var looks: ({
        "epson":   { text: "EPSON",   family: "Arial",     weight: Font.Bold,  italic: false, spacing: 0.04 },
        "hp":      { text: "hp",      family: "Segoe UI",  weight: Font.Bold,  italic: true,  spacing: 0, dy: -0.057 },
        "canon":   { text: "Canon",   family: "Georgia",   weight: Font.Bold,  italic: false, spacing: -0.02 },
        "brother": { text: "brother", family: "Arial",     weight: Font.Black, italic: false, spacing: -0.01 },
        "pantum":  { text: "PANTUM",  family: "Arial",     weight: Font.Bold,  italic: false, spacing: 0.08 },
        "samsung": { text: "SAMSUNG", family: "Arial",     weight: Font.Bold,  italic: false, spacing: 0.06 },
    })
    readonly property var look: looks[brand] || looks.epson

    text: look.text
    family: look.family
    weight: look.weight
    italic: look.italic
    spacing: look.spacing
    dy: look.dy || 0
}
