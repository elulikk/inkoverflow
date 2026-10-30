// Ink in one tank (shaders/liquid.*), shared by every printer style. Bind `shownLevel`
// (0-1) and the level eases towards it.
import QtQuick
import QtQuick3D

CustomMaterial {
    shadingMode: CustomMaterial.Shaded
    vertexShader: "shaders/liquid.vert"
    fragmentShader: "shaders/liquid.frag"
    property color inkColor: "#1d1d1f"
    property real level: shownLevel
    property real time: 0
    property real slosh: 1.0
    property real glow: 1.0
    property real shownLevel: 0.72
    Behavior on shownLevel { NumberAnimation { duration: 1400; easing.type: Easing.OutCubic } }
}
