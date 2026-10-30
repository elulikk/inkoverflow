// Waste-ink felt with a stain that grows with `shownFill` (shaders/pad.*), shared by every
// printer style. `source` is the drip point and `reach` how far a full stain spreads, both
// in the pad mesh's own units (dm).
import QtQuick
import QtQuick3D

CustomMaterial {
    shadingMode: CustomMaterial.Shaded
    vertexShader: "shaders/pad.vert"
    fragmentShader: "shaders/pad.frag"
    property real fill: shownFill
    property real reach: 0.58
    property vector3d source: Qt.vector3d(0, 0, 0)
    property color inkTint: "#2b1733"
    property real highlight: 0.0
    property real shownFill: 0.0
    Behavior on shownFill { NumberAnimation { duration: 1800; easing.type: Easing.InOutCubic } }
}
