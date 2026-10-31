// Lettering printed on a printer face, shared by every printer style: 2D text centred on
// `position` (scene units, 1 mm), facing +Z unless the node is turned. `size` is the font
// size in mm; `spacing` and `dy` are fractions of it (letter spacing, vertical nudge for
// glyphs that sit off-centre).
import QtQuick
import QtQuick3D

Node {
    id: label
    property string text
    property color color: "#8f969e"
    property real size: 7
    property string family: "Segoe UI"
    property int weight: Font.DemiBold
    property bool italic: false
    property real spacing: 0
    property real dy: 0

    scale: Qt.vector3d(0.1, 0.1, 0.1)       // the text is drawn at 10 px per mm
    Text {
        text: label.text
        color: label.color
        font.family: label.family
        font.pixelSize: Math.round(label.size * 10)
        font.weight: label.weight
        font.italic: label.italic
        font.letterSpacing: label.spacing * label.size * 10
        x: -width / 2
        y: -height / 2 + label.dy * label.size * 10
    }
}
