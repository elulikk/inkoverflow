// Plastic of the printer shell, shared by every printer style: it turns see-through while
// the scene shows the inside (bind `xray` to app.xray, 0-1). `seeThrough` is how much of
// it fades at full x-ray.
import QtQuick
import QtQuick3D

PrincipledMaterial {
    property real xray: 0
    property real seeThrough: 0.74
    opacity: 1 - seeThrough * xray
    alphaMode: xray > 0.01 ? PrincipledMaterial.Blend : PrincipledMaterial.Default
}
